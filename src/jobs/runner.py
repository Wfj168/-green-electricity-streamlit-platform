from __future__ import annotations

import os
import logging
import socket
from threading import Event, Thread
from typing import Any
from uuid import uuid4

from src.application import ModelExecutionRequest, ModelKind, SimulationService, UnifiedModelService
from src.jobs.artifacts import LocalArtifactStore
from src.persistence import PlatformRepository
from src.observability import configure_json_logging


class JobRunner:
    def __init__(
        self,
        repository: PlatformRepository,
        artifact_store: LocalArtifactStore,
        simulation_service: SimulationService | None = None,
        model_service: UnifiedModelService | None = None,
        worker_id: str | None = None,
        lease_seconds: int = 3600,
    ) -> None:
        configure_json_logging()
        self.repository = repository
        self.artifact_store = artifact_store
        self.model_service = model_service or UnifiedModelService(simulation_service)
        self.worker_id = worker_id or os.getenv(
            "PLATFORM_WORKER_ID", f"{socket.gethostname()}-{os.getpid()}-{uuid4().hex[:8]}"
        )
        self.lease_seconds = lease_seconds
        self.logger = logging.getLogger("platform.worker")

    def run_once(self) -> dict[str, Any] | None:
        self.repository.recover_expired_jobs()
        job = self.repository.claim_next_job(self.worker_id, self.lease_seconds)
        if job is None:
            return None
        self.logger.info(
            "job claimed",
            extra={"event": "job.claimed", "job_id": job["id"], "worker_id": self.worker_id},
        )
        heartbeat_stop = Event()
        heartbeat_thread = Thread(
            target=self._heartbeat_loop,
            args=(job["id"], heartbeat_stop),
            daemon=True,
            name=f"lease-{job['id'][:8]}",
        )
        heartbeat_thread.start()
        try:
            scenario = self.repository.get_scenario_version(job["scenario_version_id"])
            payload = dict(scenario["input"])
            request_overrides = dict(job["request"])
            model_kind = request_overrides.pop("model_kind", payload.get("model_kind", ModelKind.REALTIME_DISPATCH))
            result = self.model_service.run(
                ModelExecutionRequest(
                    model_kind=model_kind,
                    scenario_payload=payload,
                    request_overrides=request_overrides,
                )
            )
            if not result.success:
                error = result.error or {}
                failed = self.repository.transition_job(
                    job["id"],
                    "failed",
                    error_code=error.get("code", "MODEL_FAILED"),
                    error_message=result.message,
                    expected_worker_id=self.worker_id,
                )
                self.repository.append_audit(
                    job["created_by"], "job.failed", "job", job["id"], {"error": failed["error_code"]}
                )
                return failed

            if result.artifact_bytes is None:
                raise ValueError("成功任务缺少结果文件包")
            artifact_uri, checksum = self.artifact_store.write_result_bundle(job["id"], result.artifact_bytes)
            summary = dict(result.summary)
            summary.update({"message": result.message, "metadata": result.metadata})
            self.repository.complete_job(
                job["id"],
                summary,
                result.metrics,
                artifact_uri,
                checksum,
                expected_worker_id=self.worker_id,
            )
            self.repository.append_audit(
                job["created_by"], "job.succeeded", "job", job["id"], {"artifact_uri": artifact_uri}
            )
            self.logger.info(
                "job succeeded",
                extra={"event": "job.succeeded", "job_id": job["id"], "worker_id": self.worker_id},
            )
            return self.repository.get_job(job["id"])
        except Exception as exc:
            try:
                failed = self.repository.transition_job(
                    job["id"],
                    "failed",
                    error_code="WORKER_ERROR",
                    error_message=str(exc),
                    expected_worker_id=self.worker_id,
                )
                self.repository.append_audit(
                    job["created_by"], "job.failed", "job", job["id"], {"error": "WORKER_ERROR"}
                )
                self.logger.exception(
                    "job failed",
                    extra={
                        "event": "job.failed",
                        "job_id": job["id"],
                        "worker_id": self.worker_id,
                        "error_code": "WORKER_ERROR",
                    },
                )
                return failed
            except (KeyError, ValueError):
                return self.repository.get_job(job["id"])
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=2.0)

    def _heartbeat_loop(self, job_id: str, stop: Event) -> None:
        interval = max(min(self.lease_seconds / 3.0, 30.0), 0.2)
        while not stop.wait(interval):
            try:
                self.repository.heartbeat_job(job_id, self.worker_id, self.lease_seconds)
            except (KeyError, ValueError):
                return
