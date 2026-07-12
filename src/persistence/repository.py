from __future__ import annotations

from datetime import datetime, timezone
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
    ) -> dict[str, Any]:
        job_id = str(uuid4())
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO optimization_jobs(
                    id, project_id, scenario_version_id, model_version_id, status,
                    request_json, progress, created_by, created_at
                ) VALUES (?, ?, ?, ?, 'queued', ?, 0, ?, ?)
                """,
                (job_id, project_id, scenario_version_id, model_version_id, _json(request), created_by, utc_now()),
            )
        return self.get_job(job_id)

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
    ) -> dict[str, Any]:
        if new_status not in ALLOWED_JOB_TRANSITIONS:
            raise ValueError(f"不支持的任务状态：{new_status}")
        with self.database.transaction() as connection:
            row = connection.execute("SELECT status FROM optimization_jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(f"优化任务不存在：{job_id}")
            current_status = row["status"]
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
                    finished_at = COALESCE(?, finished_at)
                WHERE id = ?
                """,
                (new_status, final_progress, error_code, error_message, started_at, finished_at, job_id),
            )
        return self.get_job(job_id)

    def complete_job(
        self,
        job_id: str,
        summary: dict[str, Any],
        metrics: dict[str, Any],
        artifact_uri: str | None = None,
        checksum_sha256: str | None = None,
    ) -> dict[str, Any]:
        result_id = str(uuid4())
        with self.database.transaction() as connection:
            row = connection.execute("SELECT status FROM optimization_jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(f"优化任务不存在：{job_id}")
            if row["status"] != "running":
                raise ValueError("只有运行中的任务可以写入成功结果")
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
                "UPDATE optimization_jobs SET status = 'succeeded', progress = 100, finished_at = ? WHERE id = ?",
                (now, job_id),
            )
        return self.get_result(job_id)

    def get_result(self, job_id: str) -> dict[str, Any]:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM optimization_results WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"任务尚无结果：{job_id}")
        return _decode_json_fields(dict(row), ("summary_json", "metrics_json"))

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
