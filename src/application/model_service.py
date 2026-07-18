from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from enum import StrEnum
from io import BytesIO
import json
from time import perf_counter
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
import pandas as pd

from src.application.simulation_service import SimulationRequest, SimulationService
from src.core.schemas import StoreMoreInputs
from src.model_adapter import build_scenario, run_quick_trial
from src.storemore_engine import (
    default_capex_table,
    default_fuel_table,
    default_generator_table,
    default_storage_table,
)
from src.version import PLATFORM_VERSION, REALTIME_MODEL_VERSION, V17_MODEL_VERSION


class ModelKind(StrEnum):
    REALTIME_DISPATCH = "realtime_dispatch"
    INTEGRATED_PLANNING = "integrated_planning"


@dataclass(frozen=True, slots=True)
class ModelSpec:
    kind: ModelKind
    name: str
    display_name: str
    version: str
    engine: str
    description: str

    def to_dict(self) -> dict[str, str]:
        values = asdict(self)
        values["kind"] = self.kind.value
        return values


MODEL_CATALOG = {
    ModelKind.REALTIME_DISPATCH: ModelSpec(
        ModelKind.REALTIME_DISPATCH,
        "storemore",
        "快速电力滚动调度",
        REALTIME_MODEL_VERSION,
        "scipy-highs-lp",
        "48小时窗口滚动求解并保存前24小时调度结果。",
    ),
    ModelKind.INTEGRATED_PLANNING: ModelSpec(
        ModelKind.INTEGRATED_PLANNING,
        "integrated-energy-v17",
        "V17综合能源规划",
        V17_MODEL_VERSION,
        "scipy-highs-lp-milp",
        "电、热、冷、气、储能、柔性负荷、碳和P2X协同规划。",
    ),
}


def get_model_spec(model_kind: ModelKind | str) -> ModelSpec:
    try:
        kind = model_kind if isinstance(model_kind, ModelKind) else ModelKind(model_kind)
    except ValueError as exc:
        supported = "、".join(kind.value for kind in ModelKind)
        raise ValueError(f"不支持的模型类型：{model_kind}；可选值为{supported}") from exc
    return MODEL_CATALOG[kind]


def list_model_specs() -> list[dict[str, str]]:
    return [MODEL_CATALOG[kind].to_dict() for kind in ModelKind]


def list_integrated_scenarios() -> list[dict[str, str]]:
    scenarios = []
    for index in range(9):
        key = f"S{index}"
        scenario = build_scenario(key)
        scenarios.append(
            {
                "key": key,
                "name": str(scenario.get("name", key)),
                "description": str(scenario.get("description", "")),
            }
        )
    return scenarios


def get_integrated_scenario(scenario_key: str) -> dict[str, Any]:
    return build_scenario(scenario_key)


@dataclass(frozen=True, slots=True)
class ModelExecutionRequest:
    model_kind: ModelKind | str
    scenario_payload: dict[str, Any]
    request_overrides: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelExecutionResult:
    success: bool
    message: str
    error: dict[str, Any] | None
    metadata: dict[str, Any]
    summary: dict[str, Any]
    metrics: dict[str, Any]
    artifact_bytes: bytes | None
    tables: dict[str, pd.DataFrame] | None = None


STOREMORE_INPUT_FIELDS = {item.name for item in fields(StoreMoreInputs)}


class UnifiedModelService:
    def __init__(self, simulation_service: SimulationService | None = None) -> None:
        self.simulation_service = simulation_service or SimulationService()

    def run(self, request: ModelExecutionRequest) -> ModelExecutionResult:
        started_at = datetime.now(timezone.utc)
        started_counter = perf_counter()
        try:
            spec = get_model_spec(request.model_kind)
            if spec.kind == ModelKind.REALTIME_DISPATCH:
                result = self._run_realtime(request, spec)
            else:
                result = self._run_integrated_planning(request, spec)
        except Exception as exc:
            try:
                spec = get_model_spec(request.model_kind)
                model_metadata = self._base_metadata(spec)
            except ValueError:
                model_metadata = {
                    "platform_version": PLATFORM_VERSION,
                    "model_kind": str(request.model_kind),
                    "model_name": "unknown",
                    "model_version": "unknown",
                    "engine": "unknown",
                }
            result = ModelExecutionResult(
                success=False,
                message=f"模型执行失败：{exc}",
                error={"code": "MODEL_EXECUTION_ERROR", "message": str(exc), "issues": [], "details": {}},
                metadata=model_metadata,
                summary={},
                metrics={},
                artifact_bytes=None,
            )

        finished_at = datetime.now(timezone.utc)
        duration = perf_counter() - started_counter
        metadata = dict(result.metadata)
        metadata.update(
            {
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "duration_seconds": round(duration, 6),
            }
        )
        return ModelExecutionResult(
            success=result.success,
            message=result.message,
            error=result.error,
            metadata=metadata,
            summary=result.summary,
            metrics=result.metrics,
            artifact_bytes=result.artifact_bytes,
            tables=result.tables,
        )

    def _run_realtime(self, request: ModelExecutionRequest, spec: ModelSpec) -> ModelExecutionResult:
        payload = request.scenario_payload
        overrides = request.request_overrides
        base_inputs = dict(payload.get("inputs", payload))
        base_inputs.update(overrides.get("inputs", {}))
        clean_inputs = {name: value for name, value in base_inputs.items() if name in STOREMORE_INPUT_FIELDS}
        inputs = StoreMoreInputs(**clean_inputs)
        simulation = self.simulation_service.run(
            SimulationRequest(
                inputs=inputs,
                generator_table=self._table(payload, overrides, "generator_table", default_generator_table()),
                storage_table=self._table(payload, overrides, "storage_table", default_storage_table()),
                fuel_table=self._table(payload, overrides, "fuel_table", default_fuel_table()),
                capex_table=self._table(payload, overrides, "capex_table", default_capex_table()),
            )
        )
        metadata = self._base_metadata(spec)
        metadata.update(
            {
                "scenario_key": inputs.scenario_name,
                "input_summary": {
                    "scenario_name": inputs.scenario_name,
                    "rolling_days": inputs.rolling_days,
                    "total_demand_mwh": inputs.total_demand,
                },
            }
        )
        if not simulation.get("success"):
            return ModelExecutionResult(
                False,
                simulation.get("message", "快速调度失败"),
                simulation.get("error"),
                metadata,
                {},
                {},
                None,
            )

        metrics = self._metric_dict(simulation["metrics"])
        summary = {
            "scenario_key": inputs.scenario_name,
            "dispatch_rows": len(simulation["dispatch"]),
            "rolling_windows": len(simulation["rolling_log"]),
        }
        bundle = simulation["zip"]
        artifact_bytes = bundle.getvalue() if hasattr(bundle, "getvalue") else bundle.read()
        artifact_bytes = self._add_execution_manifest(artifact_bytes, metadata, summary)
        return ModelExecutionResult(
            True,
            simulation["message"],
            None,
            metadata,
            summary,
            metrics,
            artifact_bytes,
            {
                "dispatch": simulation["dispatch"],
                "metrics": simulation["metrics"],
                "investment": simulation["investment"],
                "rolling_log": simulation["rolling_log"],
            },
        )

    def _run_integrated_planning(self, request: ModelExecutionRequest, spec: ModelSpec) -> ModelExecutionResult:
        payload = request.scenario_payload
        request_values = request.request_overrides
        scenario_key = str(request_values.get("scenario_key", payload.get("scenario_key", "S4"))).upper().strip()
        scenario_overrides = dict(payload.get("overrides", {}))
        scenario_overrides.update(request_values.get("overrides", {}))
        n_steps_per_hour = int(request_values.get("n_steps_per_hour", payload.get("n_steps_per_hour", 1)))
        seed = int(request_values.get("seed", payload.get("seed", 42)))
        if n_steps_per_hour not in {1, 2, 4}:
            raise ValueError("n_steps_per_hour必须是1、2或4")

        trial = run_quick_trial(
            scenario_key,
            overrides=scenario_overrides,
            n_steps_per_hour=n_steps_per_hour,
            seed=seed,
        )
        metadata = self._base_metadata(spec)
        metadata.update(
            {
                "scenario_key": scenario_key,
                "input_summary": {
                    "scenario_key": scenario_key,
                    "n_steps_per_hour": n_steps_per_hour,
                    "seed": seed,
                    "override_fields": sorted(scenario_overrides),
                },
            }
        )
        if not trial.get("success") or not trial.get("result"):
            return ModelExecutionResult(
                False,
                trial.get("message", "综合能源规划失败"),
                {
                    "code": "MODEL_SOLVE_FAILED",
                    "message": trial.get("message", "综合能源规划失败"),
                    "issues": [],
                    "details": {"scenario_key": scenario_key},
                },
                metadata,
                {"scenario_key": scenario_key},
                {},
                None,
            )

        raw_result = trial["result"]
        metrics = self._metric_dict(raw_result["metrics"])
        summary = {
            "scenario_key": scenario_key,
            "scenario_name": trial["scenario"].get("name", scenario_key),
            "dispatch_rows": len(raw_result["dispatch"]),
            "solver_status": raw_result.get("solver_status"),
            "objective": self._json_value(raw_result.get("objective")),
            "annual_days": self._json_value(raw_result.get("annual_days")),
            "time_step_hours": self._json_value(raw_result.get("dt")),
        }
        artifact_bytes = self._v17_bundle(raw_result, trial["profiles"], trial["scenario"], metadata, summary)
        return ModelExecutionResult(
            True,
            trial.get("message", "综合能源规划完成"),
            None,
            metadata,
            summary,
            metrics,
            artifact_bytes,
            {
                key: value
                for key, value in raw_result.items()
                if isinstance(value, pd.DataFrame)
            }
            | {"profiles": trial["profiles"]},
        )

    @staticmethod
    def _table(
        payload: dict[str, Any],
        overrides: dict[str, Any],
        name: str,
        default: pd.DataFrame,
    ) -> pd.DataFrame:
        records = overrides.get(name, payload.get(name))
        return pd.DataFrame(records) if records is not None else default

    @staticmethod
    def _base_metadata(spec: ModelSpec) -> dict[str, Any]:
        return {
            "platform_version": PLATFORM_VERSION,
            "model_kind": spec.kind.value,
            "model_name": spec.name,
            "model_version": spec.version,
            "engine": spec.engine,
        }

    @classmethod
    def _metric_dict(cls, table: pd.DataFrame) -> dict[str, Any]:
        return {
            str(row["Metric"]): cls._json_value(row["Value"])
            for _, row in table.iterrows()
            if pd.notna(row["Metric"])
        }

    @staticmethod
    def _json_value(value: Any) -> Any:
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, (datetime, pd.Timestamp)):
            return value.isoformat()
        if pd.isna(value) if not isinstance(value, (dict, list, tuple, str)) else False:
            return None
        return value

    @classmethod
    def _add_execution_manifest(
        cls,
        content: bytes,
        metadata: dict[str, Any],
        summary: dict[str, Any],
    ) -> bytes:
        buffer = BytesIO(content)
        with ZipFile(buffer, "a", ZIP_DEFLATED) as archive:
            archive.writestr(
                "execution.json",
                json.dumps({"metadata": metadata, "summary": summary}, ensure_ascii=False, indent=2, default=str),
            )
        return buffer.getvalue()

    @classmethod
    def _v17_bundle(
        cls,
        result: dict[str, Any],
        profiles: pd.DataFrame,
        scenario: dict[str, Any],
        metadata: dict[str, Any],
        summary: dict[str, Any],
    ) -> bytes:
        buffer = BytesIO()
        with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
            for key in ("capacity", "dispatch", "cost", "carbon", "metrics", "diagnostics"):
                table = result.get(key)
                if isinstance(table, pd.DataFrame):
                    archive.writestr(f"data/{key}.csv", table.to_csv(index=False).encode("utf-8-sig"))
            if isinstance(profiles, pd.DataFrame):
                archive.writestr("data/input_profiles.csv", profiles.to_csv(index=False).encode("utf-8-sig"))
            archive.writestr(
                "metadata.json",
                json.dumps({"metadata": metadata, "summary": summary}, ensure_ascii=False, indent=2, default=str),
            )
            archive.writestr(
                "execution.json",
                json.dumps({"metadata": metadata, "summary": summary}, ensure_ascii=False, indent=2, default=str),
            )
            archive.writestr(
                "scenario.json",
                json.dumps(scenario, ensure_ascii=False, indent=2, default=cls._json_value),
            )
        return buffer.getvalue()
