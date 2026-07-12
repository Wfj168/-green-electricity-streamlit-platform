from __future__ import annotations

import sqlite3

import pytest

from src.persistence import Database, PlatformRepository


@pytest.fixture
def repository(tmp_path) -> PlatformRepository:
    return PlatformRepository(Database(tmp_path / "platform-test.db"))


def test_database_migration_is_idempotent(tmp_path) -> None:
    database = Database(tmp_path / "migration.db")
    assert database.migrate() == ["001"]
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
    with pytest.raises(sqlite3.IntegrityError):
        repository.create_job("missing-project", scenario["id"], model["id"], {}, "user-1")
