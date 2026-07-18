from __future__ import annotations

import os
from pathlib import Path
import sqlite3

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from src.application import get_model_spec, list_model_specs
from src.api.schemas import JobCreate, JobTransition, ProjectCreate, ScenarioCreate, TokenRequest
from src.persistence import Database, PlatformRepository
from src.security import AuthService, Principal
from src.security.auth import AuthError
from src.version import PLATFORM_VERSION, REALTIME_MODEL_VERSION


def create_app(database_path: str | Path | None = None) -> FastAPI:
    repository = PlatformRepository(Database(database_path))
    auth_service = AuthService.from_env()
    app = FastAPI(title="园区低碳优化平台 API", version=PLATFORM_VERSION)
    app.state.repository = repository
    app.state.auth_service = auth_service

    def current_principal(
        authorization: str | None = Header(default=None),
        x_user_id: str = Header(default="local-user"),
    ) -> Principal:
        try:
            return auth_service.authenticate(authorization, x_user_id)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc), headers={"WWW-Authenticate": "Bearer"}) from exc

    def require_roles(*allowed_roles: str):
        def dependency(principal: Principal = Depends(current_principal)) -> Principal:
            if principal.role not in allowed_roles:
                raise HTTPException(status_code=403, detail="当前角色无权执行该操作")
            return principal

        return dependency

    @app.get("/health")
    def health() -> dict[str, object]:
        with repository.database.connect() as connection:
            connection.execute("SELECT 1").fetchone()
        return {
            "status": "ok",
            "version": PLATFORM_VERSION,
            "model_version": REALTIME_MODEL_VERSION,
            "models": list_model_specs(),
        }

    @app.get("/api/v1/models")
    def list_models(principal: Principal = Depends(current_principal)):
        return list_model_specs()

    @app.post("/api/v1/auth/token")
    def issue_token(payload: TokenRequest):
        try:
            token = auth_service.issue_token(payload.bootstrap_key, payload.user_id, payload.role)
            return {"access_token": token, "token_type": "bearer", "expires_in": auth_service.token_ttl_seconds}
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    @app.post("/api/v1/projects", status_code=201)
    def create_project(payload: ProjectCreate, principal: Principal = Depends(require_roles("admin", "engineer"))):
        try:
            project = repository.create_project(payload.name, principal.user_id, payload.description)
            repository.append_audit(principal.user_id, "project.created", "project", project["id"])
            return project
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/projects")
    def list_projects(principal: Principal = Depends(current_principal)):
        return repository.list_projects(owner_id=principal.user_id)

    @app.post("/api/v1/projects/{project_id}/scenarios", status_code=201)
    def create_scenario(
        project_id: str,
        payload: ScenarioCreate,
        principal: Principal = Depends(require_roles("admin", "engineer")),
    ):
        try:
            project = repository.get_project(project_id)
            if project["owner_id"] != principal.user_id:
                raise HTTPException(status_code=403, detail="无权访问该项目")
            scenario = repository.create_scenario_version(project_id, payload.name, payload.inputs, principal.user_id)
            repository.append_audit(principal.user_id, "scenario.created", "scenario", scenario["id"])
            return scenario
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/projects/{project_id}/jobs", status_code=202)
    def create_job(
        project_id: str,
        payload: JobCreate,
        principal: Principal = Depends(require_roles("admin", "engineer")),
    ):
        try:
            project = repository.get_project(project_id)
            if project["owner_id"] != principal.user_id:
                raise HTTPException(status_code=403, detail="无权访问该项目")
            model_spec = get_model_spec(payload.model_kind)
            model = repository.register_model_version(
                model_spec.name,
                model_spec.version,
                model_spec.engine,
                os.getenv("GIT_COMMIT", "development"),
            )
            job_request = dict(payload.request)
            job_request["model_kind"] = model_spec.kind.value
            job = repository.create_job(
                project_id, payload.scenario_version_id, model["id"], job_request, principal.user_id
            )
            repository.append_audit(principal.user_id, "job.queued", "job", job["id"])
            return job
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/jobs")
    def list_jobs(
        project_id: str | None = Query(default=None),
        status: str | None = Query(default=None),
        principal: Principal = Depends(current_principal),
    ):
        jobs = repository.list_jobs(project_id, status)
        return [job for job in jobs if job["created_by"] == principal.user_id]

    @app.get("/api/v1/jobs/{job_id}")
    def get_job(job_id: str, principal: Principal = Depends(current_principal)):
        try:
            job = repository.get_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if job["created_by"] != principal.user_id:
            raise HTTPException(status_code=403, detail="无权访问该任务")
        return job

    @app.post("/api/v1/jobs/{job_id}/transition")
    def transition_job(
        job_id: str,
        payload: JobTransition,
        principal: Principal = Depends(require_roles("admin", "engineer")),
    ):
        try:
            job = repository.get_job(job_id)
            if job["created_by"] != principal.user_id:
                raise HTTPException(status_code=403, detail="无权访问该任务")
            if payload.action != "cancel":
                raise HTTPException(status_code=422, detail="当前仅支持cancel操作")
            return repository.transition_job(job_id, "cancelled")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/jobs/{job_id}/result")
    def get_result(job_id: str, principal: Principal = Depends(current_principal)):
        try:
            job = repository.get_job(job_id)
            if job["created_by"] != principal.user_id:
                raise HTTPException(status_code=403, detail="无权访问该任务")
            return repository.get_result(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app


app = create_app()
