from __future__ import annotations

import os
from pathlib import Path
import logging
from time import perf_counter
import sqlite3
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from src.application import SystemStatusService, V2ModelFacade, get_model_spec, list_model_specs
from src.api.schemas import JobCreate, JobTransition, LoginRequest, ProjectCreate, ScenarioCreate, TokenRequest
from src.persistence import Database, PlatformRepository
from src.observability import configure_json_logging
from src.security import AuthService, Principal
from src.security.auth import AuthError
from src.version import PLATFORM_VERSION, REALTIME_MODEL_VERSION


def create_app(database_path: str | Path | None = None) -> FastAPI:
    configure_json_logging()
    logger = logging.getLogger("platform.api")
    repository = PlatformRepository(Database(database_path))
    auth_service = AuthService.from_env()
    app = FastAPI(title="园区低碳优化平台 API", version=PLATFORM_VERSION)
    allowed_origins = [
        origin.strip()
        for origin in os.getenv(
            "PLATFORM_CORS_ORIGINS",
            "http://127.0.0.1:4173,http://127.0.0.1:5173,http://localhost:4173,http://localhost:5173",
        ).split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-User-ID"],
    )
    app.state.repository = repository
    app.state.auth_service = auth_service
    app.state.v2_model_facade = V2ModelFacade()
    app.state.system_status_service = SystemStatusService(repository, auth_service)

    @app.middleware("http")
    async def request_observability(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))[:128]
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request failed",
                extra={
                    "event": "api.request.failed",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round((perf_counter() - started) * 1000, 3),
                },
            )
            raise
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request completed",
            extra={
                "event": "api.request.completed",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 3),
            },
        )
        return response

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

    @app.get("/ready")
    def ready() -> dict[str, str]:
        with repository.database.connect() as connection:
            connection.execute("SELECT 1").fetchone()
        return {"status": "ready"}

    @app.get("/metrics", response_class=Response)
    def metrics() -> Response:
        counts = repository.job_status_counts()
        lines = [
            "# HELP platform_jobs Number of optimization jobs by status",
            "# TYPE platform_jobs gauge",
        ]
        lines.extend(f'platform_jobs{{status="{status}"}} {count}' for status, count in sorted(counts.items()))
        return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")

    @app.get("/api/v1/models")
    def list_models(principal: Principal = Depends(current_principal)):
        return list_model_specs()

    @app.post("/api/v1/auth/login")
    def login(payload: LoginRequest, request: Request):
        try:
            token, principal, display_name = auth_service.login(payload.username, payload.password)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        repository.append_audit(
            principal.user_id,
            "auth.login",
            "account",
            principal.user_id,
            {"role": principal.role, "client_ip": request.client.host if request.client else "unknown"},
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": auth_service.token_ttl_seconds,
            "user": {"userId": principal.user_id, "displayName": display_name, "role": principal.role},
        }

    @app.get("/api/v1/auth/me")
    def auth_me(principal: Principal = Depends(current_principal)):
        account = next((item for item in auth_service.safe_accounts() if item["username"] == principal.user_id), None)
        return {
            "userId": principal.user_id,
            "displayName": account["displayName"] if account else principal.user_id,
            "role": principal.role,
            "authMode": auth_service.mode,
        }

    @app.get("/api/v2/overview")
    def v2_overview(
        year: int = Query(default=2025, ge=2020, le=2100),
        resolution_minutes: int = Query(default=60),
        principal: Principal = Depends(current_principal),
    ):
        try:
            return app.state.v2_model_facade.overview(
                year=year,
                resolution_minutes=resolution_minutes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v2/parameters")
    def v2_parameters(principal: Principal = Depends(current_principal)):
        return app.state.v2_model_facade.parameters()

    @app.get("/api/v2/strategies")
    def v2_strategies(
        year: int = Query(default=2025, ge=2020, le=2100),
        principal: Principal = Depends(current_principal),
    ):
        try:
            return app.state.v2_model_facade.strategies(year=year)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v2/stress-tests")
    def v2_stress_tests(
        year: int = Query(default=2025, ge=2020, le=2100),
        principal: Principal = Depends(current_principal),
    ):
        try:
            return app.state.v2_model_facade.stress_tests(year=year)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v2/green-direct-benefits")
    def v2_green_direct_benefits(
        year: int = Query(default=2025, ge=2020, le=2100),
        principal: Principal = Depends(current_principal),
    ):
        try:
            return app.state.v2_model_facade.green_direct_benefits(year=year)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v2/forecasts")
    def v2_forecasts(
        year: int = Query(default=2025, ge=2020, le=2100),
        principal: Principal = Depends(current_principal),
    ):
        try:
            return app.state.v2_model_facade.forecast_center(year=year)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v2/assets")
    def v2_assets(principal: Principal = Depends(current_principal)):
        return app.state.v2_model_facade.asset_register()

    @app.get("/api/v2/system-status")
    def v2_system_status(principal: Principal = Depends(require_roles("admin", "auditor"))):
        return app.state.system_status_service.snapshot(principal)

    @app.get("/api/v1/audit")
    def list_audit(
        limit: int = Query(default=100, ge=1, le=1000),
        entity_type: str | None = Query(default=None),
        principal: Principal = Depends(require_roles("admin")),
    ):
        return repository.list_audit_logs(limit=limit, entity_type=entity_type)

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
                project_id,
                payload.scenario_version_id,
                model["id"],
                job_request,
                principal.user_id,
                idempotency_key=payload.idempotency_key,
                max_attempts=payload.max_attempts,
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
