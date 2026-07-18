from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import json
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

from src.application.model_service import (
    ModelExecutionRequest,
    ModelExecutionResult,
    ModelKind,
    UnifiedModelService,
)
from src.core import scenario_fingerprint
from src.version import PLATFORM_VERSION, V17_MODEL_VERSION


@dataclass(frozen=True, slots=True)
class ScenarioComparisonResult:
    success: bool
    table: pd.DataFrame
    errors: dict[str, str]
    metadata: dict[str, Any]
    artifact_bytes: bytes
    executions: dict[str, ModelExecutionResult]


class ScenarioComparisonService:
    def __init__(self, model_service: UnifiedModelService | None = None) -> None:
        self.model_service = model_service or UnifiedModelService()

    def run(
        self,
        scenario_keys: list[str] | tuple[str, ...],
        *,
        n_steps_per_hour: int = 1,
        seed: int = 42,
    ) -> ScenarioComparisonResult:
        normalized = list(dict.fromkeys(str(key).upper().strip() for key in scenario_keys))
        if not normalized:
            raise ValueError("至少选择一个对比场景")
        invalid = [key for key in normalized if key not in {f"S{index}" for index in range(9)}]
        if invalid:
            raise ValueError(f"不支持的对比场景：{','.join(invalid)}")

        executions: dict[str, ModelExecutionResult] = {}
        errors: dict[str, str] = {}
        rows: list[dict[str, Any]] = []
        payloads: dict[str, dict[str, Any]] = {}
        for key in normalized:
            payload = {
                "schema_version": "integrated-planning-v1",
                "model_kind": ModelKind.INTEGRATED_PLANNING.value,
                "scenario_key": key,
                "n_steps_per_hour": n_steps_per_hour,
                "seed": seed,
                "overrides": {},
            }
            payloads[key] = payload
            execution = self.model_service.run(
                ModelExecutionRequest(ModelKind.INTEGRATED_PLANNING, payload)
            )
            executions[key] = execution
            if not execution.success:
                errors[key] = execution.message
                rows.append({"Scenario": key, "Success": False, "Message": execution.message})
                continue
            metrics = execution.metrics
            rows.append(
                {
                    "Scenario": key,
                    "Name": execution.summary.get("scenario_name", key),
                    "Success": True,
                    "Social annual cost [EUR/year]": metrics.get("Social total annual cost"),
                    "Annual CO2 [tCO2/year]": metrics.get("Annual CO2 emissions"),
                    "Annual grid import [MWh/year]": metrics.get("Annual grid import"),
                    "Renewable curtailment rate [%]": metrics.get("Renewable curtailment rate"),
                    "Renewable utilization rate [%]": metrics.get(
                        "Renewable utilization rate (including export)"
                    ),
                    "Multi-energy service rate [%]": metrics.get("Total multi-energy service rate"),
                    "Battery cycles [cycles/year]": metrics.get("Battery equivalent cycles"),
                    "Electrolyzer capacity [MW]": metrics.get("Electrolyzer capacity"),
                    "Green hydrogen [tH2/year]": metrics.get("Endogenous green hydrogen production"),
                    "Parameter fingerprint": scenario_fingerprint(payload),
                    "Model version": execution.metadata.get("model_version"),
                    "Duration [s]": execution.metadata.get("duration_seconds"),
                    "Message": execution.message,
                }
            )

        table = pd.DataFrame(rows)
        table = self._add_abatement_metrics(table)
        metadata = {
            "schema_version": "scenario-comparison-v1",
            "platform_version": PLATFORM_VERSION,
            "model_version": V17_MODEL_VERSION,
            "scenario_keys": normalized,
            "n_steps_per_hour": n_steps_per_hour,
            "seed": seed,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        artifact = self._build_artifact(table, metadata, payloads, executions, errors)
        return ScenarioComparisonResult(not errors, table, errors, metadata, artifact, executions)

    @staticmethod
    def _add_abatement_metrics(table: pd.DataFrame) -> pd.DataFrame:
        if table.empty or "S0" not in set(table.get("Scenario", [])):
            return table
        output = table.copy()
        baseline = output[(output["Scenario"] == "S0") & (output["Success"])]
        if baseline.empty:
            return output
        baseline_co2 = float(baseline.iloc[0]["Annual CO2 [tCO2/year]"])
        baseline_cost = float(baseline.iloc[0]["Social annual cost [EUR/year]"])
        output["CO2 reduction vs S0 [tCO2/year]"] = baseline_co2 - pd.to_numeric(
            output["Annual CO2 [tCO2/year]"], errors="coerce"
        )
        output["CO2 reduction vs S0 [%]"] = (
            output["CO2 reduction vs S0 [tCO2/year]"] / baseline_co2 * 100.0
        )
        output["Cost change vs S0 [EUR/year]"] = (
            pd.to_numeric(output["Social annual cost [EUR/year]"], errors="coerce") - baseline_cost
        )
        reductions = output["CO2 reduction vs S0 [tCO2/year]"]
        output["Average abatement cost [EUR/tCO2]"] = output["Cost change vs S0 [EUR/year]"].where(
            reductions > 1e-9
        ) / reductions.where(reductions > 1e-9)
        return output

    @staticmethod
    def _build_artifact(
        table: pd.DataFrame,
        metadata: dict[str, Any],
        payloads: dict[str, dict[str, Any]],
        executions: dict[str, ModelExecutionResult],
        errors: dict[str, str],
    ) -> bytes:
        buffer = BytesIO()
        with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
            archive.writestr("scenario_comparison.csv", table.to_csv(index=False).encode("utf-8-sig"))
            archive.writestr(
                "comparison_manifest.json",
                json.dumps(
                    {"metadata": metadata, "payloads": payloads, "errors": errors},
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
            )
            for key, execution in executions.items():
                if execution.artifact_bytes:
                    archive.writestr(f"scenarios/{key}_result.zip", execution.artifact_bytes)
        return buffer.getvalue()
