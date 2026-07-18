from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3
from typing import Any
from uuid import uuid4

from src.persistence.database import Database


ALLOWED_JOB_TRANSITIONS = {
    "queued": {"running", "cancelled"},
    "running": {"succeeded", "failed", "cancelled"},
    "succeeded": set(),
    "failed": set(),
    "cancelled": set(),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_after(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _decode_json_fields(record: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    for field in fields:
        if field in record and record[field] is not None:
            record[field.removesuffix("_json")] = json.loads(record.pop(field))
    return record


class PlatformRepository:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.database.migrate()

    def create_project(self, name: str, owner_id: str, description: str = "") -> dict[str, Any]:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("项目名称不能为空")
        project_id = str(uuid4())
        now = utc_now()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO projects(id, name, description, owner_id, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'active', ?, ?)
                """,
                (project_id, clean_name, description.strip(), owner_id, now, now),
            )
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> dict[str, Any]:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row is None:
            raise KeyError(f"项目不存在：{project_id}")
        return dict(row)

    def list_projects(self, owner_id: str | None = None) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            if owner_id is None:
                rows = connection.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM projects WHERE owner_id = ? ORDER BY created_at DESC", (owner_id,)
                ).fetchall()
        return [dict(row) for row in rows]

    def create_scenario_version(
        self,
        project_id: str,
        name: str,
        inputs: dict[str, Any],
        created_by: str,
    ) -> dict[str, Any]:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("场景名称不能为空")
        scenario_id = str(uuid4())
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) AS latest FROM scenario_versions WHERE project_id = ? AND name = ?",
                (project_id, clean_name),
            ).fetchone()
            version = int(row["latest"]) + 1
            connection.execute(
                """
                INSERT INTO scenario_versions(id, project_id, name, version, input_json, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (scenario_id, project_id, clean_name, version, _json(inputs), created_by, utc_now()),
            )
        return self.get_scenario_version(scenario_id)

    def get_scenario_version(self, scenario_id: str) -> dict[str, Any]:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM scenario_versions WHERE id = ?", (scenario_id,)).fetchone()
        if row is None:
            raise KeyError(f"场景版本不存在：{scenario_id}")
        return _decode_json_fields(dict(row), ("input_json",))

    def create_dataset_version(
        self,
        project_id: str,
        name: str,
        schema_version: str,
        checksum_sha256: str,
        storage_uri: str,
        metadata: dict[str, Any],
        created_by: str,
    ) -> dict[str, Any]:
        dataset_id = str(uuid4())
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) AS latest FROM dataset_versions WHERE project_id = ? AND name = ?",
                (project_id, name),
            ).fetchone()
            version = int(row["latest"]) + 1
            connection.execute(
                """
                INSERT INTO dataset_versions(
                    id, project_id, name, version, schema_version, checksum_sha256,
                    storage_uri, metadata_json, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset_id,
                    project_id,
                    name,
                    version,
                    schema_version,
                    checksum_sha256,
                    storage_uri,
                    _json(metadata),
                    created_by,
                    utc_now(),
                ),
            )
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM dataset_versions WHERE id = ?", (dataset_id,)).fetchone()
        return _decode_json_fields(dict(row), ("metadata_json",))

    def register_model_version(
        self,
        name: str,
        version: str,
        engine: str,
        code_commit: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM model_versions WHERE name = ? AND version = ?", (name, version)
            ).fetchone()
            if existing is not None:
                return dict(existing)
            model_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO model_versions(id, name, version, engine, code_commit, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (model_id, name, version, engine, code_commit, utc_now()),
            )
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM model_versions WHERE id = ?", (model_id,)).fetchone()
        return dict(row)

    def create_job(
        self,
        project_id: str,
        scenario_version_id: str,
        model_version_id: str,
        request: dict[str, Any],
        created_by: str,
        idempotency_key: str | None = None,
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        clean_idempotency_key = idempotency_key.strip() if idempotency_key else None
        if max_attempts <= 0:
            raise ValueError("max_attempts必须大于0")
        job_id = str(uuid4())
        with self.database.transaction() as connection:
            if clean_idempotency_key:
                existing = connection.execute(
                    "SELECT id FROM optimization_jobs WHERE project_id = ? AND idempotency_key = ?",
                    (project_id, clean_idempotency_key),
                ).fetchone()
                if existing is not None:
                    return self.get_job(existing["id"])
            scenario = connection.execute(
                "SELECT project_id FROM scenario_versions WHERE id = ?", (scenario_version_id,)
            ).fetchone()
            if scenario is None:
                raise KeyError(f"场景版本不存在：{scenario_version_id}")
            if scenario["project_id"] != project_id:
                raise ValueError("场景版本不属于指定项目")
            connection.execute(
                """
                INSERT INTO optimization_jobs(
                    id, project_id, scenario_version_id, model_version_id, status,
                    request_json, progress, created_by, created_at, idempotency_key, max_attempts
                ) VALUES (?, ?, ?, ?, 'queued', ?, 0, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    project_id,
                    scenario_version_id,
                    model_version_id,
                    _json(request),
                    created_by,
                    utc_now(),
                    clean_idempotency_key,
                    max_attempts,
                ),
            )
        return self.get_job(job_id)

    def list_jobs(self, project_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[str] = []
        if project_id is not None:
            clauses.append("project_id = ?")
            parameters.append(project_id)
        if status is not None:
            if status not in ALLOWED_JOB_TRANSITIONS:
                raise ValueError(f"不支持的任务状态：{status}")
            clauses.append("status = ?")
            parameters.append(status)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.database.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM optimization_jobs{where} ORDER BY created_at DESC", parameters
            ).fetchall()
        return [_decode_json_fields(dict(row), ("request_json",)) for row in rows]

    def claim_next_job(self, worker_id: str = "local-worker", lease_seconds: int = 3600) -> dict[str, Any] | None:
        clean_worker_id = worker_id.strip()
        if not clean_worker_id:
            raise ValueError("worker_id不能为空")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds必须大于0")
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT id FROM optimization_jobs
                WHERE status = 'queued' AND attempt_count < max_attempts
                ORDER BY created_at ASC LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            job_id = row["id"]
            now = utc_now()
            cursor = connection.execute(
                """
                UPDATE optimization_jobs
                SET status = 'running', progress = 1, started_at = COALESCE(started_at, ?),
                    worker_id = ?, lease_expires_at = ?, heartbeat_at = ?,
                    attempt_count = attempt_count + 1
                WHERE id = ? AND status = 'queued'
                """,
                (now, clean_worker_id, utc_after(lease_seconds), now, job_id),
            )
            if cursor.rowcount != 1:
                return None
        return self.get_job(job_id)

    def heartbeat_job(self, job_id: str, worker_id: str, lease_seconds: int = 3600) -> dict[str, Any]:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds必须大于0")
        now = utc_now()
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE optimization_jobs
                SET heartbeat_at = ?, lease_expires_at = ?
                WHERE id = ? AND status = 'running' AND worker_id = ?
                """,
                (now, utc_after(lease_seconds), job_id, worker_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("任务不在运行中或不属于当前Worker")
        return self.get_job(job_id)

    def recover_expired_jobs(self, now: str | None = None) -> dict[str, list[str]]:
        reference = now or utc_now()
        recovered: list[str] = []
        failed: list[str] = []
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT id, attempt_count, max_attempts FROM optimization_jobs
                WHERE status = 'running' AND lease_expires_at IS NOT NULL AND lease_expires_at < ?
                """,
                (reference,),
            ).fetchall()
            for row in rows:
                if int(row["attempt_count"]) >= int(row["max_attempts"]):
                    connection.execute(
                        """
                        UPDATE optimization_jobs
                        SET status = 'failed', progress = 100, error_code = 'WORKER_LEASE_EXPIRED',
                            error_message = 'Worker租约过期且已达到最大尝试次数', finished_at = ?,
                            lease_expires_at = NULL
                        WHERE id = ? AND status = 'running'
                        """,
                        (reference, row["id"]),
                    )
                    failed.append(row["id"])
                else:
                    connection.execute(
                        """
                        UPDATE optimization_jobs
                        SET status = 'queued', progress = 0, worker_id = NULL,
                            lease_expires_at = NULL, heartbeat_at = NULL,
                            error_code = NULL, error_message = NULL
                        WHERE id = ? AND status = 'running'
                        """,
                        (row["id"],),
                    )
                    recovered.append(row["id"])
        return {"recovered": recovered, "failed": failed}

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM optimization_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"优化任务不存在：{job_id}")
        return _decode_json_fields(dict(row), ("request_json",))

    def transition_job(
        self,
        job_id: str,
        new_status: str,
        *,
        progress: float | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        expected_worker_id: str | None = None,
    ) -> dict[str, Any]:
        if new_status not in ALLOWED_JOB_TRANSITIONS:
            raise ValueError(f"不支持的任务状态：{new_status}")
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT status, worker_id FROM optimization_jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"优化任务不存在：{job_id}")
            current_status = row["status"]
            if expected_worker_id is not None and row["worker_id"] != expected_worker_id:
                raise ValueError("任务不属于当前Worker")
            if new_status != current_status and new_status not in ALLOWED_JOB_TRANSITIONS[current_status]:
                raise ValueError(f"非法任务状态变更：{current_status} -> {new_status}")
            now = utc_now()
            started_at = now if new_status == "running" else None
            finished_at = now if new_status in {"succeeded", "failed", "cancelled"} else None
            final_progress = progress if progress is not None else (100.0 if new_status == "succeeded" else None)
            connection.execute(
                """
                UPDATE optimization_jobs
                SET status = ?,
                    progress = COALESCE(?, progress),
                    error_code = ?,
                    error_message = ?,
                    started_at = COALESCE(started_at, ?),
                    finished_at = COALESCE(?, finished_at),
                    lease_expires_at = CASE
                        WHEN ? IN ('succeeded', 'failed', 'cancelled') THEN NULL
                        ELSE lease_expires_at
                    END
                WHERE id = ?
                """,
                (
                    new_status,
                    final_progress,
                    error_code,
                    error_message,
                    started_at,
                    finished_at,
                    new_status,
                    job_id,
                ),
            )
        return self.get_job(job_id)

    def complete_job(
        self,
        job_id: str,
        summary: dict[str, Any],
        metrics: dict[str, Any],
        artifact_uri: str | None = None,
        checksum_sha256: str | None = None,
        expected_worker_id: str | None = None,
    ) -> dict[str, Any]:
        result_id = str(uuid4())
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT status, worker_id FROM optimization_jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"优化任务不存在：{job_id}")
            if row["status"] != "running":
                raise ValueError("只有运行中的任务可以写入成功结果")
            if expected_worker_id is not None and row["worker_id"] != expected_worker_id:
                raise ValueError("任务不属于当前Worker")
            now = utc_now()
            connection.execute(
                """
                INSERT INTO optimization_results(
                    id, job_id, summary_json, metrics_json, artifact_uri, checksum_sha256, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (result_id, job_id, _json(summary), _json(metrics), artifact_uri, checksum_sha256, now),
            )
            connection.execute(
                """
                UPDATE optimization_jobs
                SET status = 'succeeded', progress = 100, finished_at = ?, lease_expires_at = NULL
                WHERE id = ?
                """,
                (now, job_id),
            )
        return self.get_result(job_id)

    def get_result(self, job_id: str) -> dict[str, Any]:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM optimization_results WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"任务尚无结果：{job_id}")
        return _decode_json_fields(dict(row), ("summary_json", "metrics_json"))

    def job_status_counts(self) -> dict[str, int]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS count FROM optimization_jobs GROUP BY status"
            ).fetchall()
        counts = {status: 0 for status in ALLOWED_JOB_TRANSITIONS}
        counts.update({str(row["status"]): int(row["count"]) for row in rows})
        return counts

    def list_audit_logs(self, limit: int = 100, entity_type: str | None = None) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit必须在1至1000之间")
        with self.database.connect() as connection:
            if entity_type:
                rows = connection.execute(
                    """
                    SELECT * FROM audit_logs WHERE entity_type = ?
                    ORDER BY created_at DESC, id DESC LIMIT ?
                    """,
                    (entity_type, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM audit_logs ORDER BY created_at DESC, id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [_decode_json_fields(dict(row), ("details_json",)) for row in rows]

    def append_audit(
        self,
        actor_id: str,
        action: str,
        entity_type: str,
        entity_id: str,
        details: dict[str, Any] | None = None,
    ) -> int:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO audit_logs(actor_id, action, entity_type, entity_id, details_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (actor_id, action, entity_type, entity_id, _json(details or {}), utc_now()),
            )
            return int(cursor.lastrowid)
