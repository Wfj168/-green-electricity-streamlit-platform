from __future__ import annotations

from typing import Any

from src.application import ModelExecutionRequest, ModelKind, SimulationService, UnifiedModelService
from src.jobs.artifacts import LocalArtifactStore
from src.persistence import PlatformRepository


class JobRunner:
    def __init__(
        self,
        repository: PlatformRepository,
        artifact_store: LocalArtifactStore,
        simulation_service: SimulationService | None = None,
        model_service: UnifiedModelService | None = None,
    ) -> None:
        self.repository = repository
        self.artifact_store = artifact_store
        self.model_service = model_service or UnifiedModelService(simulation_service)

    def run_once(self) -> dict[str, Any] | None:
        job = self.repository.claim_next_job()
        if job is None:
            return None
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
            self.repository.complete_job(job["id"], summary, result.metrics, artifact_uri, checksum)
            self.repository.append_audit(
                job["created_by"], "job.succeeded", "job", job["id"], {"artifact_uri": artifact_uri}
            )
            return self.repository.get_job(job["id"])
        except Exception as exc:
            failed = self.repository.transition_job(
                job["id"], "failed", error_code="WORKER_ERROR", error_message=str(exc)
            )
            self.repository.append_audit(
                job["created_by"], "job.failed", "job", job["id"], {"error": "WORKER_ERROR"}
            )
            return failed
