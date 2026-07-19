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
                rows.append({"场景": key, "是否成功": False, "说明": execution.message})
                continue
            metrics = execution.metrics
            annual_emissions = metrics.get("Annual CO2 emissions")
            carbon_target = execution.summary.get("carbon_target_tco2_per_year")
            if carbon_target is None:
                carbon_constraint_status = "未启用"
                carbon_margin = None
            else:
                carbon_margin = float(carbon_target) - float(annual_emissions or 0.0)
                tolerance = max(1.0, 0.001 * float(carbon_target))
                carbon_constraint_status = (
                    "起作用" if abs(carbon_margin) <= tolerance else "未起作用（结果自然低于上限）"
                )
            rows.append(
                {
                    "场景": key,
                    "场景名称": execution.summary.get("scenario_name", key),
                    "是否成功": True,
                    "社会年度成本/万元": (metrics.get("Social total annual cost") or 0.0) / 10_000.0,
                    "年度二氧化碳排放/吨": annual_emissions,
                    "年度碳排目标/吨": carbon_target,
                    "碳目标余量/吨": carbon_margin,
                    "碳约束状态": carbon_constraint_status,
                    "年度电网购电量/兆瓦时": metrics.get("Annual grid import"),
                    "新能源弃电率/%": metrics.get("Renewable curtailment rate"),
                    "新能源综合利用率/%": metrics.get(
                        "Renewable utilization rate (including export)"
                    ),
                    "多能综合服务保障率/%": metrics.get("Total multi-energy service rate"),
                    "电池等效循环次数/次每年": metrics.get("Battery equivalent cycles"),
                    "电解槽规划容量/兆瓦": metrics.get("Electrolyzer capacity"),
                    "年度绿氢产量/吨": metrics.get("Endogenous green hydrogen production"),
                    "参数指纹": scenario_fingerprint(payload),
                    "模型版本": execution.metadata.get("model_version"),
                    "计算耗时/秒": execution.metadata.get("duration_seconds"),
                    "说明": execution.message,
                }
            )

        table = pd.DataFrame(rows)
        table = self._add_abatement_metrics(table)
        table = self._add_distinctness_diagnosis(table)
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
        if table.empty or "S0" not in set(table.get("场景", [])):
            return table
        output = table.copy()
        baseline = output[(output["场景"] == "S0") & (output["是否成功"])]
        if baseline.empty:
            return output
        baseline_co2 = float(baseline.iloc[0]["年度二氧化碳排放/吨"])
        baseline_cost = float(baseline.iloc[0]["社会年度成本/万元"])
        output["相对S0减排量/吨"] = baseline_co2 - pd.to_numeric(
            output["年度二氧化碳排放/吨"], errors="coerce"
        )
        output["相对S0减排率/%"] = (
            output["相对S0减排量/吨"] / baseline_co2 * 100.0
        )
        output["相对S0成本变化/万元"] = (
            pd.to_numeric(output["社会年度成本/万元"], errors="coerce") - baseline_cost
        )
        reductions = output["相对S0减排量/吨"]
        output["平均减排成本/元每吨"] = (
            output["相对S0成本变化/万元"].where(reductions > 1e-9) * 10_000.0
            / reductions.where(reductions > 1e-9)
        )
        return output

    @staticmethod
    def _add_distinctness_diagnosis(table: pd.DataFrame) -> pd.DataFrame:
        output = table.copy()
        output["场景差异状态"] = "有可辨识差异"
        output["差异说明"] = "核心成本、排放或运行指标与其他场景存在差异。"
        required = [
            "社会年度成本/万元",
            "年度二氧化碳排放/吨",
            "年度电网购电量/兆瓦时",
            "新能源弃电率/%",
            "电池等效循环次数/次每年",
            "电解槽规划容量/兆瓦",
        ]
        if output.empty or not set(required + ["是否成功", "场景"]).issubset(output.columns):
            return output
        valid = output[output["是否成功"]].copy()
        if valid.empty:
            return output
        signatures = valid[required].apply(pd.to_numeric, errors="coerce").round(4)
        for _, indices in signatures.groupby(required, dropna=False).groups.items():
            positions = list(indices)
            if len(positions) < 2:
                continue
            keys = output.loc[positions, "场景"].astype(str).tolist()
            key_text = "、".join(keys)
            output.loc[positions, "场景差异状态"] = "新增约束未改变核心结果"
            output.loc[positions, "差异说明"] = (
                f"{key_text}的核心结果一致，说明这些场景之间的新增约束在当前最优解处未起作用；"
                "不能据此宣称新增约束带来了额外收益。"
            )
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
