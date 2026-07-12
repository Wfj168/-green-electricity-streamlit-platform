from __future__ import annotations

from dataclasses import fields
from typing import Any

import pandas as pd

from src.application import SimulationRequest, SimulationService
from src.core.schemas import StoreMoreInputs
from src.jobs.artifacts import LocalArtifactStore
from src.persistence import PlatformRepository
from src.storemore_engine import (
    default_capex_table,
    default_fuel_table,
    default_generator_table,
    default_storage_table,
)


INPUT_FIELDS = {field.name for field in fields(StoreMoreInputs)}


class JobRunner:
    def __init__(
        self,
        repository: PlatformRepository,
        artifact_store: LocalArtifactStore,
        simulation_service: SimulationService | None = None,
    ) -> None:
        self.repository = repository
        self.artifact_store = artifact_store
        self.simulation_service = simulation_service or SimulationService()

    def run_once(self) -> dict[str, Any] | None:
        job = self.repository.claim_next_job()
        if job is None:
            return None
        try:
            scenario = self.repository.get_scenario_version(job["scenario_version_id"])
            payload = dict(scenario["input"])
            request_overrides = dict(job["request"])
            base_inputs = dict(payload.get("inputs", payload))
            base_inputs.update(request_overrides.get("inputs", {}))
            clean_inputs = {name: value for name, value in base_inputs.items() if name in INPUT_FIELDS}
            inputs = StoreMoreInputs(**clean_inputs)

            result = self.simulation_service.run(
                SimulationRequest(
                    inputs=inputs,
                    generator_table=self._table(payload, "generator_table", default_generator_table()),
                    storage_table=self._table(payload, "storage_table", default_storage_table()),
                    fuel_table=self._table(payload, "fuel_table", default_fuel_table()),
                    capex_table=self._table(payload, "capex_table", default_capex_table()),
                )
            )
            if not result.get("success"):
                error = result.get("error") or {}
                failed = self.repository.transition_job(
                    job["id"],
                    "failed",
                    error_code=error.get("code", "MODEL_FAILED"),
                    error_message=result.get("message", "模型计算失败"),
                )
                self.repository.append_audit(
                    job["created_by"], "job.failed", "job", job["id"], {"error": failed["error_code"]}
                )
                return failed

            bundle = result["zip"]
            bundle.seek(0)
            artifact_uri, checksum = self.artifact_store.write_result_bundle(job["id"], bundle.read())
            metrics = dict(zip(result["metrics"]["Metric"], result["metrics"]["Value"]))
            summary = {
                "message": result["message"],
                "metadata": result["metadata"],
                "dispatch_rows": len(result["dispatch"]),
                "rolling_windows": len(result["rolling_log"]),
            }
            self.repository.complete_job(job["id"], summary, metrics, artifact_uri, checksum)
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

    @staticmethod
    def _table(payload: dict[str, Any], name: str, default: pd.DataFrame) -> pd.DataFrame:
        records = payload.get(name)
        return pd.DataFrame(records) if records is not None else default
