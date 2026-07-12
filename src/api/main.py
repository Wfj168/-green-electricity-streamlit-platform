from __future__ import annotations

import os
from pathlib import Path
import sqlite3

from fastapi import FastAPI, Header, HTTPException, Query

from src.api.schemas import JobCreate, JobTransition, ProjectCreate, ScenarioCreate
from src.persistence import Database, PlatformRepository
from src.version import PLATFORM_VERSION, REALTIME_MODEL_VERSION


def create_app(database_path: str | Path | None = None) -> FastAPI:
    repository = PlatformRepository(Database(database_path))
    app = FastAPI(title="园区低碳优化平台 API", version=PLATFORM_VERSION)
    app.state.repository = repository

    @app.get("/health")
    def health() -> dict[str, str]:
        with repository.database.connect() as connection:
            connection.execute("SELECT 1").fetchone()
        return {"status": "ok", "version": PLATFORM_VERSION, "model_version": REALTIME_MODEL_VERSION}

    @app.post("/api/v1/projects", status_code=201)
    def create_project(payload: ProjectCreate, x_user_id: str = Header(default="local-user")):
        try:
            project = repository.create_project(payload.name, x_user_id, payload.description)
            repository.append_audit(x_user_id, "project.created", "project", project["id"])
            return project
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/projects")
    def list_projects(x_user_id: str = Header(default="local-user")):
        return repository.list_projects(owner_id=x_user_id)

    @app.post("/api/v1/projects/{project_id}/scenarios", status_code=201)
    def create_scenario(
        project_id: str,
        payload: ScenarioCreate,
        x_user_id: str = Header(default="local-user"),
    ):
        try:
            project = repository.get_project(project_id)
            if project["owner_id"] != x_user_id:
                raise HTTPException(status_code=403, detail="无权访问该项目")
            scenario = repository.create_scenario_version(project_id, payload.name, payload.inputs, x_user_id)
            repository.append_audit(x_user_id, "scenario.created", "scenario", scenario["id"])
            return scenario
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/projects/{project_id}/jobs", status_code=202)
    def create_job(
        project_id: str,
        payload: JobCreate,
        x_user_id: str = Header(default="local-user"),
    ):
        try:
            project = repository.get_project(project_id)
            if project["owner_id"] != x_user_id:
                raise HTTPException(status_code=403, detail="无权访问该项目")
            model = repository.register_model_version(
                "storemore", REALTIME_MODEL_VERSION, "scipy-highs", os.getenv("GIT_COMMIT", "development")
            )
            job = repository.create_job(
                project_id, payload.scenario_version_id, model["id"], payload.request, x_user_id
            )
            repository.append_audit(x_user_id, "job.queued", "job", job["id"])
            return job
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/jobs")
    def list_jobs(
        project_id: str | None = Query(default=None),
        status: str | None = Query(default=None),
        x_user_id: str = Header(default="local-user"),
    ):
        jobs = repository.list_jobs(project_id, status)
        return [job for job in jobs if job["created_by"] == x_user_id]

    @app.get("/api/v1/jobs/{job_id}")
    def get_job(job_id: str, x_user_id: str = Header(default="local-user")):
        try:
            job = repository.get_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if job["created_by"] != x_user_id:
            raise HTTPException(status_code=403, detail="无权访问该任务")
        return job

    @app.post("/api/v1/jobs/{job_id}/transition")
    def transition_job(job_id: str, payload: JobTransition, x_user_id: str = Header(default="local-user")):
        try:
            job = repository.get_job(job_id)
            if job["created_by"] != x_user_id:
                raise HTTPException(status_code=403, detail="无权访问该任务")
            if payload.action != "cancel":
                raise HTTPException(status_code=422, detail="当前仅支持cancel操作")
            return repository.transition_job(job_id, "cancelled")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/jobs/{job_id}/result")
    def get_result(job_id: str, x_user_id: str = Header(default="local-user")):
        try:
            job = repository.get_job(job_id)
            if job["created_by"] != x_user_id:
                raise HTTPException(status_code=403, detail="无权访问该任务")
            return repository.get_result(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app


app = create_app()
