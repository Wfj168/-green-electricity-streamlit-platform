from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class CarbonAnalysisResult:
    source_breakdown: pd.DataFrame
    accounting: pd.DataFrame
    boundary: pd.DataFrame
    annual_emissions_tco2: float
    carbon_intensity_kg_per_mwh: float
    annual_carbon_cost_cny: float
    target_emissions_tco2: float | None
    target_gap_tco2: float | None
    baseline_emissions_tco2: float | None
    reduction_vs_baseline_tco2: float | None
    reduction_vs_baseline_percent: float | None
    average_abatement_cost_cny_per_tco2: float | None


class CarbonAnalysisService:
    """Build a transparent operational-carbon ledger from one V17 execution."""

    def analyze(
        self,
        *,
        metrics: dict[str, Any],
        dispatch: pd.DataFrame,
        scenario: dict[str, Any],
        scenario_key: str,
        comparison: pd.DataFrame | None = None,
        time_step_hours: float = 1.0,
        baseline_emissions_tco2: float | None = None,
        target_emissions_tco2: float | None = None,
    ) -> CarbonAnalysisResult:
        annual_emissions = float(metrics.get("Annual CO2 emissions", 0.0) or 0.0)
        carbon_intensity = float(
            metrics.get("System carbon intensity per electric-service demand", 0.0) or 0.0
        )
        annual_carbon_cost = float(metrics.get("Carbon external cost", 0.0) or 0.0)
        grid_factor = float(scenario.get("grid_emission_factor", 0.55))
        gas_factor = float(scenario.get("gas_emission_factor", 0.20))

        required = {"P_grid_buy", "G_CHP", "G_GB"}
        if dispatch.empty or not required.issubset(dispatch.columns):
            grid_emissions = chp_emissions = boiler_emissions = 0.0
        else:
            dt = float(time_step_hours)
            weight_source = (
                dispatch["day_weight"]
                if "day_weight" in dispatch
                else pd.Series(1.0, index=dispatch.index)
            )
            weights = pd.to_numeric(weight_source, errors="coerce").fillna(1.0)
            grid_emissions = float((dispatch["P_grid_buy"] * grid_factor * dt * weights).sum())
            chp_emissions = float((dispatch["G_CHP"] * gas_factor * dt * weights).sum())
            boiler_emissions = float((dispatch["G_GB"] * gas_factor * dt * weights).sum())

        source_breakdown = pd.DataFrame(
            {
                "排放来源": ["电网购电", "燃气热电联产", "燃气锅炉"],
                "年度排放量/吨": [grid_emissions, chp_emissions, boiler_emissions],
                "排放因子": [grid_factor, gas_factor, gas_factor],
                "因子单位": ["吨/兆瓦时", "吨/兆瓦时燃气", "吨/兆瓦时燃气"],
            }
        )

        p2x_avoidance = float(metrics.get("Endogenous P2X CO2 avoidance", 0.0) or 0.0)
        accounting = pd.DataFrame(
            {
                "核算项目": [
                    "运营期核算排放",
                    "其中：排放来源分项合计",
                    "电转其他能源减排贡献（参考）",
                    "碳信用或抵消量",
                    "最终入账排放",
                ],
                "年度数量/吨": [
                    annual_emissions,
                    grid_emissions + chp_emissions + boiler_emissions,
                    p2x_avoidance,
                    0.0,
                    annual_emissions,
                ],
                "说明": [
                    "由购电和燃气消耗按典型日权重折算",
                    "用于检查排放来源是否能够与总量对账",
                    "已经体现在优化后的运行排放中，不再重复扣减",
                    "当前模型未纳入碳信用、绿证抵消或核证减排量",
                    "当前版本等于运营期核算排放",
                ],
            }
        )

        comparison_baseline, reduction, reduction_percent, abatement_cost = self._comparison_values(
            comparison, scenario_key
        )
        baseline_emissions = (
            float(baseline_emissions_tco2)
            if baseline_emissions_tco2 is not None
            else comparison_baseline
        )
        if baseline_emissions is not None and comparison_baseline is None:
            reduction = baseline_emissions - annual_emissions
            reduction_percent = (
                100.0 * reduction / baseline_emissions if baseline_emissions > 1e-9 else None
            )
        target = (
            float(target_emissions_tco2)
            if target_emissions_tco2 is not None
            else self._target_emissions(scenario, baseline_emissions)
        )
        gap = annual_emissions - target if target is not None else None

        boundary = pd.DataFrame(
            [
                ["核算对象", "园区综合能源系统运营期", "已纳入"],
                ["间接排放", "外购电对应排放", "已纳入"],
                ["直接排放", "热电联产和燃气锅炉燃气消耗", "已纳入"],
                ["减排贡献", "绿氢替代燃气供热", "单列贡献，不重复抵扣"],
                ["碳信用与绿证", "核证减排量、绿证抵消", "尚未纳入"],
                ["全生命周期", "设备制造、建设、运输和退役", "尚未纳入"],
            ],
            columns=["边界项目", "当前口径", "处理方式"],
        )

        return CarbonAnalysisResult(
            source_breakdown=source_breakdown,
            accounting=accounting,
            boundary=boundary,
            annual_emissions_tco2=annual_emissions,
            carbon_intensity_kg_per_mwh=carbon_intensity * 1000.0,
            annual_carbon_cost_cny=annual_carbon_cost,
            target_emissions_tco2=target,
            target_gap_tco2=gap,
            baseline_emissions_tco2=baseline_emissions,
            reduction_vs_baseline_tco2=reduction,
            reduction_vs_baseline_percent=reduction_percent,
            average_abatement_cost_cny_per_tco2=abatement_cost,
        )

    @staticmethod
    def _comparison_values(
        comparison: pd.DataFrame | None, scenario_key: str
    ) -> tuple[float | None, float | None, float | None, float | None]:
        required = {"场景", "是否成功", "年度二氧化碳排放/吨"}
        if comparison is None or comparison.empty or not required.issubset(comparison.columns):
            return None, None, None, None
        valid = comparison[comparison["是否成功"]]
        baseline = valid[valid["场景"].eq("S0")]
        current = valid[valid["场景"].eq(scenario_key)]
        if baseline.empty or current.empty:
            return None, None, None, None
        baseline_value = float(baseline.iloc[0]["年度二氧化碳排放/吨"])
        current_value = float(current.iloc[0]["年度二氧化碳排放/吨"])
        reduction = baseline_value - current_value
        reduction_percent = reduction / baseline_value * 100.0 if baseline_value > 1e-9 else None
        abatement = None
        if "平均减排成本/元每吨" in current and pd.notna(current.iloc[0]["平均减排成本/元每吨"]):
            abatement = float(current.iloc[0]["平均减排成本/元每吨"])
        return baseline_value, reduction, reduction_percent, abatement

    @staticmethod
    def _target_emissions(scenario: dict[str, Any], baseline: float | None) -> float | None:
        allowance = scenario.get("carbon_allowance_tco2_per_year")
        if allowance is not None and np.isfinite(float(allowance)):
            return float(allowance)
        if baseline is None or not scenario.get("enable_carbon_constraint", False):
            return None
        ratio = float(scenario.get("co2_cap_ratio_to_s0", 1.0))
        return baseline * ratio
