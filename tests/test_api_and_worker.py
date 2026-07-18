from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
from urllib.parse import unquote, urlparse
from zipfile import ZipFile

from fastapi.testclient import TestClient
import pytest

from src.application import get_model_spec
from src.api.main import create_app
from src.jobs import JobRunner
from src.jobs.artifacts import LocalArtifactStore
from src.persistence import Database, PlatformRepository
from src.version import REALTIME_MODEL_VERSION
from tests.test_realtime_regression import default_inputs


def test_api_project_scenario_job_and_cancel_flow(tmp_path) -> None:
    app = create_app(tmp_path / "api.db")
    client = TestClient(app)

    health_response = client.get("/health", headers={"X-Request-ID": "test-request-001"})
    assert health_response.json()["status"] == "ok"
    assert health_response.headers["X-Request-ID"] == "test-request-001"
    assert client.get("/ready").json()["status"] == "ready"
    assert 'platform_jobs{status="queued"}' in client.get("/metrics").text
    assert {item["kind"] for item in client.get("/api/v1/models").json()} == {
        "realtime_dispatch",
        "integrated_planning",
    }
    project = client.post("/api/v1/projects", json={"name": "API园区"}).json()
    scenario = client.post(
        f"/api/v1/projects/{project['id']}/scenarios",
        json={"name": "基准", "inputs": {"inputs": asdict(replace(default_inputs(), rolling_days=1))}},
    ).json()
    job_response = client.post(
        f"/api/v1/projects/{project['id']}/jobs",
        json={"scenario_version_id": scenario["id"], "request": {}},
    )
    assert job_response.status_code == 202
    job = job_response.json()
    assert client.get(f"/api/v1/jobs/{job['id']}").json()["status"] == "queued"
    assert job["request"]["model_kind"] == "realtime_dispatch"
    cancelled = client.post(f"/api/v1/jobs/{job['id']}/transition", json={"action": "cancel"})
    assert cancelled.json()["status"] == "cancelled"

    integrated_scenario = client.post(
        f"/api/v1/projects/{project['id']}/scenarios",
        json={"name": "S7综合规划", "inputs": {"scenario_key": "S7", "n_steps_per_hour": 1}},
    ).json()
    integrated_job = client.post(
        f"/api/v1/projects/{project['id']}/jobs",
        json={
            "scenario_version_id": integrated_scenario["id"],
            "model_kind": "integrated_planning",
            "request": {"seed": 42},
            "idempotency_key": "integrated-S7-request",
        },
    )
    assert integrated_job.status_code == 202
    assert integrated_job.json()["request"] == {
        "seed": 42,
        "model_kind": "integrated_planning",
    }
    repeated_job = client.post(
        f"/api/v1/projects/{project['id']}/jobs",
        json={
            "scenario_version_id": integrated_scenario["id"],
            "model_kind": "integrated_planning",
            "idempotency_key": "integrated-S7-request",
        },
    )
    assert repeated_job.json()["id"] == integrated_job.json()["id"]
    assert client.get("/api/v1/audit").status_code == 200


def test_worker_executes_queued_job_and_persists_artifact(tmp_path) -> None:
    repository = PlatformRepository(Database(tmp_path / "worker.db"))
    project = repository.create_project("Worker园区", "user-1")
    scenario = repository.create_scenario_version(
        project["id"],
        "实时场景",
        {"inputs": asdict(replace(default_inputs(), rolling_days=1))},
        "user-1",
    )
    model = repository.register_model_version("storemore", REALTIME_MODEL_VERSION, "scipy-highs", "test")
    job = repository.create_job(project["id"], scenario["id"], model["id"], {}, "user-1")

    completed = JobRunner(repository, LocalArtifactStore(tmp_path / "artifacts")).run_once()

    assert completed["id"] == job["id"]
    assert completed["status"] == "succeeded"
    result = repository.get_result(job["id"])
    assert result["summary"]["dispatch_rows"] == 24
    assert result["summary"]["rolling_windows"] == 1
    assert result["artifact_uri"].startswith("file:")
    artifact_path = Path(unquote(urlparse(result["artifact_uri"]).path.lstrip("/")))
    assert artifact_path.exists()
    assert len(result["checksum_sha256"]) == 64


@pytest.mark.parametrize("scenario_key", ["S0", "S4", "S7", "S8"])
def test_worker_persists_each_required_integrated_planning_scenario(tmp_path, scenario_key: str) -> None:
    repository = PlatformRepository(Database(tmp_path / f"{scenario_key}.db"))
    project = repository.create_project(f"{scenario_key}综合能源园区", "user-1")
    scenario = repository.create_scenario_version(
        project["id"],
        scenario_key,
        {"model_kind": "integrated_planning", "scenario_key": scenario_key, "n_steps_per_hour": 1, "seed": 42},
        "user-1",
    )
    spec = get_model_spec("integrated_planning")
    model = repository.register_model_version(spec.name, spec.version, spec.engine, "test")
    job = repository.create_job(
        project["id"],
        scenario["id"],
        model["id"],
        {"model_kind": "integrated_planning"},
        "user-1",
    )

    completed = JobRunner(repository, LocalArtifactStore(tmp_path / "artifacts")).run_once()

    assert completed["id"] == job["id"]
    assert completed["status"] == "succeeded"
    result = repository.get_result(job["id"])
    assert result["summary"]["scenario_key"] == scenario_key
    assert result["summary"]["metadata"]["model_kind"] == "integrated_planning"
    assert "Annual CO2 emissions" in result["metrics"]
    artifact_path = Path(unquote(urlparse(result["artifact_uri"]).path.lstrip("/")))
    with ZipFile(artifact_path) as archive:
        assert "data/dispatch.csv" in archive.namelist()


def test_api_rejects_unknown_model_kind(tmp_path) -> None:
    app = create_app(tmp_path / "invalid-model.db")
    client = TestClient(app)
    project = client.post("/api/v1/projects", json={"name": "模型校验园区"}).json()
    scenario = client.post(
        f"/api/v1/projects/{project['id']}/scenarios",
        json={"name": "基准", "inputs": {"scenario_key": "S4"}},
    ).json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/jobs",
        json={"scenario_version_id": scenario["id"], "model_kind": "unknown-model"},
    )
    assert response.status_code == 422


def test_token_authentication_enforces_roles(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PLATFORM_AUTH_MODE", "token")
    monkeypatch.setenv("PLATFORM_AUTH_SECRET", "s" * 32)
    monkeypatch.setenv("PLATFORM_BOOTSTRAP_KEY", "bootstrap-key-123456")
    app = create_app(tmp_path / "auth.db")
    client = TestClient(app)

    assert client.get("/api/v1/projects").status_code == 401
    viewer_token = client.post(
        "/api/v1/auth/token",
        json={"bootstrap_key": "bootstrap-key-123456", "user_id": "viewer-1", "role": "viewer"},
    ).json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    assert client.get("/api/v1/projects", headers=viewer_headers).status_code == 200
    assert client.post("/api/v1/projects", json={"name": "禁止创建"}, headers=viewer_headers).status_code == 403
    assert client.get("/api/v1/audit", headers=viewer_headers).status_code == 403

    engineer_token = client.post(
        "/api/v1/auth/token",
        json={"bootstrap_key": "bootstrap-key-123456", "user_id": "engineer-1", "role": "engineer"},
    ).json()["access_token"]
    engineer_headers = {"Authorization": f"Bearer {engineer_token}"}
    assert client.post("/api/v1/projects", json={"name": "允许创建"}, headers=engineer_headers).status_code == 201
    assert client.get("/api/v1/audit", headers=engineer_headers).status_code == 403

    admin_token = client.post(
        "/api/v1/auth/token",
        json={"bootstrap_key": "bootstrap-key-123456", "user_id": "admin-1", "role": "admin"},
    ).json()["access_token"]
    assert client.get("/api/v1/audit", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 200
