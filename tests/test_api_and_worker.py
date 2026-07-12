from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi.testclient import TestClient

from src.api.main import create_app
from src.jobs import JobRunner
from src.jobs.artifacts import LocalArtifactStore
from src.persistence import Database, PlatformRepository
from src.version import REALTIME_MODEL_VERSION
from tests.test_realtime_regression import default_inputs


def test_api_project_scenario_job_and_cancel_flow(tmp_path) -> None:
    app = create_app(tmp_path / "api.db")
    client = TestClient(app)

    assert client.get("/health").json()["status"] == "ok"
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
    cancelled = client.post(f"/api/v1/jobs/{job['id']}/transition", json={"action": "cancel"})
    assert cancelled.json()["status"] == "cancelled"


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

    engineer_token = client.post(
        "/api/v1/auth/token",
        json={"bootstrap_key": "bootstrap-key-123456", "user_id": "engineer-1", "role": "engineer"},
    ).json()["access_token"]
    engineer_headers = {"Authorization": f"Bearer {engineer_token}"}
    assert client.post("/api/v1/projects", json={"name": "允许创建"}, headers=engineer_headers).status_code == 201
