from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.application.agri_energy_flow_service import (
    AgriEnergyFlowRequest,
    AgriEnergyFlowResult,
    AgriEnergyFlowService,
)
from src.core.agri_parameter_registry import formal_readiness_gaps, phase1_parameter_value
from src.model.agri_zero_carbon_optimizer import (
    AgriOptimizationRequest,
    AgriOptimizationResult,
    AgriZeroCarbonOptimizer,
)


@dataclass(frozen=True, slots=True)
class AgriStrategyComparisonResult:
    comparison: pd.DataFrame
    baseline: AgriEnergyFlowResult
    green_direct: AgriEnergyFlowResult
    zero_carbon: AgriOptimizationResult


class AgriStrategyService:
    """在完全相同的农业负荷和经济口径下比较三种正式策略。"""

    def compare(self, profiles: pd.DataFrame) -> AgriStrategyComparisonResult:
        flow_service = AgriEnergyFlowService()
        baseline = flow_service.simulate(
            profiles,
            AgriEnergyFlowRequest(
                pv_capacity_mw=0.0,
                green_direct_capacity_mw=0.0,
                battery_power_mw=0.0,
                battery_energy_mwh=0.0,
                export_capacity_mw=0.0,
            ),
        )
        green_direct = flow_service.simulate(profiles, AgriEnergyFlowRequest())
        zero_carbon = AgriZeroCarbonOptimizer().optimize(
            profiles,
            AgriOptimizationRequest(target_physical_green_share=1.0, planning_interval_hours=1),
        )
        if not zero_carbon.success:
            raise RuntimeError(zero_carbon.status)
        comparison = pd.DataFrame(
            [
                self._physical_strategy_row(
                    "现状基准方案",
                    baseline,
                    {
                        "pv_capacity_mw": 0.0,
                        "green_direct_capacity_mw": 0.0,
                        "battery_power_mw": 0.0,
                        "battery_energy_mwh": 0.0,
                        "grid_peak_mw": float(baseline.dispatch["grid_to_load_mw"].max()),
                    },
                    direct_enabled=False,
                ),
                self._physical_strategy_row(
                    "绿电直连方案",
                    green_direct,
                    {
                        "pv_capacity_mw": phase1_parameter_value("pv.demo_installed_capacity_mw"),
                        "green_direct_capacity_mw": phase1_parameter_value(
                            "green_direct.demo_contract_capacity_mw"
                        ),
                        "battery_power_mw": phase1_parameter_value("battery.demo_power_mw"),
                        "battery_energy_mwh": phase1_parameter_value("battery.demo_energy_mwh"),
                        "grid_peak_mw": float(green_direct.dispatch["grid_to_load_mw"].max()),
                    },
                    direct_enabled=True,
                ),
                self._optimized_strategy_row(zero_carbon),
            ]
        )
        return AgriStrategyComparisonResult(comparison, baseline, green_direct, zero_carbon)

    @staticmethod
    def _time_step_hours(dispatch: pd.DataFrame) -> float:
        timestamps = pd.to_datetime(dispatch["timestamp"])
        if len(timestamps) > 1:
            return float(timestamps.diff().dropna().dt.total_seconds().median()) / 3600.0
        return 1.0

    def _physical_strategy_row(
        self,
        name: str,
        result: AgriEnergyFlowResult,
        capacities: dict[str, float],
        *,
        direct_enabled: bool,
    ) -> dict[str, float | str]:
        dispatch = result.dispatch.copy()
        dispatch["direct_curtailment_mw"] = dispatch["direct_green_curtailment_mw"]
        dispatch["direct_export_mw"] = dispatch["direct_green_export_mw"]
        optimizer = AgriZeroCarbonOptimizer()
        fixed_direct = 0.0
        if direct_enabled:
            fixed_direct = phase1_parameter_value("green_direct.base_fixed_cost_cny") * (
                optimizer._capital_recovery_factor() + phase1_parameter_value("finance.fixed_om_rate")
            )
        costs = optimizer._cost_breakdown(
            dispatch,
            capacities,
            self._time_step_hours(dispatch),
            fixed_direct,
        )
        return self._comparison_row(name, capacities, result.summary, sum(costs.values()))

    def _optimized_strategy_row(self, result: AgriOptimizationResult) -> dict[str, float | str]:
        return self._comparison_row(
            "零碳源网荷储协同方案",
            result.capacities,
            result.summary,
            result.summary["annual_total_cost_cny"],
        )

    @staticmethod
    def _comparison_row(
        name: str,
        capacities: dict[str, float],
        summary: dict[str, float],
        annual_cost: float,
    ) -> dict[str, float | str]:
        emissions = summary["annual_carbon_emissions_tco2"]
        balance_ok = summary["max_bus_balance_error_mw"] <= 1e-7
        numeric_zero = emissions <= phase1_parameter_value("carbon.zero_tolerance_tco2") and balance_ok
        if numeric_zero and not formal_readiness_gaps():
            conclusion = "零碳达标"
        elif numeric_zero:
            conclusion = "计算排放为零，演示参数待正式核验"
        else:
            conclusion = "零碳未达标"
        demand = summary["annual_demand_mwh"]
        return {
            "策略": name,
            "本地光伏/兆瓦": capacities["pv_capacity_mw"],
            "绿电直连/兆瓦": capacities["green_direct_capacity_mw"],
            "储能功率/兆瓦": capacities["battery_power_mw"],
            "储能容量/兆瓦时": capacities["battery_energy_mwh"],
            "电网最大需量/兆瓦": capacities["grid_peak_mw"],
            "年购普通电/兆瓦时": summary["annual_grid_import_mwh"],
            "物理绿电匹配率/%": summary["physical_green_match_rate_percent"],
            "运营碳排放/吨": emissions,
            "年总成本/万元": annual_cost / 10_000.0,
            "平均供能成本/元每兆瓦时": annual_cost / max(demand, 1e-9),
            "结论": conclusion,
        }
