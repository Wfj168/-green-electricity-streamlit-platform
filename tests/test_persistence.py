from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from src.persistence import Database, PlatformRepository


@pytest.fixture
def repository(tmp_path) -> PlatformRepository:
    return PlatformRepository(Database(tmp_path / "platform-test.db"))


def test_database_migration_is_idempotent(tmp_path) -> None:
    database = Database(tmp_path / "migration.db")
    assert database.migrate() == ["001", "002"]
    assert database.migrate() == []
    with database.connect() as connection:
        tables = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
    assert {
        "projects",
        "scenario_versions",
        "dataset_versions",
        "model_versions",
        "optimization_jobs",
        "optimization_results",
        "audit_logs",
    }.issubset(tables)
    with database.connect() as connection:
        job_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(optimization_jobs)").fetchall()
        }
    assert {"worker_id", "lease_expires_at", "attempt_count", "max_attempts", "idempotency_key"}.issubset(
        job_columns
    )


def test_project_scenario_and_dataset_versions_are_persistent(repository: PlatformRepository) -> None:
    project = repository.create_project("示范园区", "user-1", "低碳优化试点")
    scenario_v1 = repository.create_scenario_version(project["id"], "基准场景", {"rps": 35}, "user-1")
    scenario_v2 = repository.create_scenario_version(project["id"], "基准场景", {"rps": 45}, "user-1")
    dataset = repository.create_dataset_version(
        project["id"],
        "源荷数据",
        "profiles-v1",
        "abc123",
        "file:///profiles.csv",
        {"rows": 8760},
        "user-1",
    )

    assert repository.get_project(project["id"])["name"] == "示范园区"
    assert scenario_v1["version"] == 1
    assert scenario_v2["version"] == 2
    assert scenario_v2["input"] == {"rps": 45}
    assert dataset["version"] == 1
    assert dataset["metadata"] == {"rows": 8760}


def test_model_job_result_and_audit_lifecycle(repository: PlatformRepository) -> None:
    project = repository.create_project("工业园区", "user-1")
    scenario = repository.create_scenario_version(project["id"], "S8", {"scenario": "S8"}, "user-1")
    model = repository.register_model_version("storemore", "1.0", "highs", "2fdfaee")
    same_model = repository.register_model_version("storemore", "1.0", "highs", "different")
    assert same_model["id"] == model["id"]

    job = repository.create_job(project["id"], scenario["id"], model["id"], {"rolling_days": 3}, "user-1")
    assert job["status"] == "queued"
    running = repository.transition_job(job["id"], "running", progress=10)
    assert running["status"] == "running"
    result = repository.complete_job(
        job["id"],
        {"message": "MODEL SOLVED"},
        {"co2": 100.0},
        "file:///result.zip",
        "def456",
    )

    assert repository.get_job(job["id"])["status"] == "succeeded"
    assert result["summary"] == {"message": "MODEL SOLVED"}
    assert result["metrics"] == {"co2": 100.0}
    assert repository.append_audit("user-1", "job.completed", "job", job["id"], {"status": "succeeded"}) > 0


def test_job_state_machine_rejects_invalid_transition(repository: PlatformRepository) -> None:
    project = repository.create_project("状态机测试", "user-1")
    scenario = repository.create_scenario_version(project["id"], "baseline", {}, "user-1")
    model = repository.register_model_version("storemore", "1.0", "highs", "commit")
    job = repository.create_job(project["id"], scenario["id"], model["id"], {}, "user-1")

    with pytest.raises(ValueError, match="非法任务状态变更"):
        repository.transition_job(job["id"], "succeeded")
    with pytest.raises(ValueError, match="场景版本不属于指定项目"):
        repository.create_job("missing-project", scenario["id"], model["id"], {}, "user-1")


def test_job_idempotency_returns_the_original_job(repository: PlatformRepository) -> None:
    project = repository.create_project("幂等任务", "user-1")
    scenario = repository.create_scenario_version(project["id"], "S4", {}, "user-1")
    model = repository.register_model_version("integrated", "1.0", "highs", "commit")
    first = repository.create_job(
        project["id"], scenario["id"], model["id"], {}, "user-1", idempotency_key="request-001"
    )
    repeated = repository.create_job(
        project["id"], scenario["id"], model["id"], {"different": True}, "user-1", idempotency_key="request-001"
    )
    assert repeated["id"] == first["id"]
    assert repeated["request"] == {}


def test_concurrent_workers_cannot_claim_the_same_job(tmp_path) -> None:
    database = Database(tmp_path / "concurrent.db")
    repository = PlatformRepository(database)
    project = repository.create_project("并发任务", "user-1")
    scenario = repository.create_scenario_version(project["id"], "S4", {}, "user-1")
    model = repository.register_model_version("integrated", "1.0", "highs", "commit")
    job = repository.create_job(project["id"], scenario["id"], model["id"], {}, "user-1")

    def claim(worker_id: str):
        return PlatformRepository(database).claim_next_job(worker_id, lease_seconds=60)

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(claim, ["worker-a", "worker-b"]))
    claimed = [item for item in claims if item is not None]
    assert len(claimed) == 1
    assert claimed[0]["id"] == job["id"]
    assert claimed[0]["attempt_count"] == 1


def test_expired_lease_is_recovered_and_old_worker_cannot_complete(repository: PlatformRepository) -> None:
    project = repository.create_project("租约恢复", "user-1")
    scenario = repository.create_scenario_version(project["id"], "S4", {}, "user-1")
    model = repository.register_model_version("integrated", "1.0", "highs", "commit")
    job = repository.create_job(project["id"], scenario["id"], model["id"], {}, "user-1", max_attempts=2)
    repository.claim_next_job("worker-a", lease_seconds=60)
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

    recovered = repository.recover_expired_jobs(future)
    assert recovered == {"recovered": [job["id"]], "failed": []}
    second_claim = repository.claim_next_job("worker-b", lease_seconds=60)
    assert second_claim["attempt_count"] == 2
    with pytest.raises(ValueError, match="不属于当前Worker"):
        repository.complete_job(job["id"], {}, {}, expected_worker_id="worker-a")
    repository.complete_job(job["id"], {"ok": True}, {}, expected_worker_id="worker-b")
    assert repository.get_job(job["id"])["status"] == "succeeded"


def test_expired_lease_fails_after_maximum_attempts(repository: PlatformRepository) -> None:
    project = repository.create_project("租约失败", "user-1")
    scenario = repository.create_scenario_version(project["id"], "S4", {}, "user-1")
    model = repository.register_model_version("integrated", "1.0", "highs", "commit")
    job = repository.create_job(project["id"], scenario["id"], model["id"], {}, "user-1", max_attempts=1)
    repository.claim_next_job("worker-a", lease_seconds=60)
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

    recovered = repository.recover_expired_jobs(future)
    assert recovered == {"recovered": [], "failed": [job["id"]]}
    failed = repository.get_job(job["id"])
    assert failed["status"] == "failed"
    assert failed["error_code"] == "WORKER_LEASE_EXPIRED"
