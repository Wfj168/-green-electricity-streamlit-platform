from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.model.agri_zero_carbon_optimizer import (
    AgriOptimizationRequest,
    AgriOptimizationResult,
    AgriZeroCarbonOptimizer,
)


@dataclass(frozen=True, slots=True)
class AgriReferenceCapacities:
    pv_capacity_mw: float
    green_direct_capacity_mw: float
    battery_power_mw: float
    battery_energy_mwh: float


@dataclass(frozen=True, slots=True)
class AgriStressTestResult:
    table: pd.DataFrame
    scenario_results: dict[str, AgriOptimizationResult]


class AgriStressTestService:
    """用固定推荐容量检查六类压力条件，不允许压力测试偷偷扩容。"""

    def evaluate(
        self,
        profiles: pd.DataFrame,
        capacities: AgriReferenceCapacities,
        *,
        planning_interval_hours: int = 3,
    ) -> AgriStressTestResult:
        scenarios = {
            "BASE": ("推荐方案基准", self._copy(profiles)),
            "STRESS-PV": ("低光伏出力年（下降30%）", self._low_pv(profiles)),
            "STRESS-IRR": ("春灌负荷增长（增加25%）", self._irrigation_growth(profiles)),
            "STRESS-PROC": ("秋收集中加工（负荷增加20%）", self._processing_concentration(profiles)),
            "STRESS-DIRECT": ("绿电直连受限（出力下降40%）", self._direct_restriction(profiles)),
            "STRESS-PRICE": ("电价与设备投资上浮20%", self._copy(profiles)),
            "STRESS-GRID": ("公共电网晚峰连续七日限电", self._grid_restriction(profiles)),
        }
        optimizer = AgriZeroCarbonOptimizer()
        results: dict[str, AgriOptimizationResult] = {}
        rows: list[dict[str, float | str | bool]] = []
        base_cost = 0.0
        for scenario_id, (name, scenario_profiles) in scenarios.items():
            result = optimizer.optimize(
                scenario_profiles,
                AgriOptimizationRequest(
                    target_physical_green_share=0.0,
                    planning_interval_hours=planning_interval_hours,
                    fixed_pv_capacity_mw=capacities.pv_capacity_mw,
                    fixed_green_direct_capacity_mw=capacities.green_direct_capacity_mw,
                    fixed_battery_power_mw=capacities.battery_power_mw,
                    fixed_battery_energy_mwh=capacities.battery_energy_mwh,
                ),
            )
            results[scenario_id] = result
            if not result.success:
                rows.append(
                    {
                        "压力编号": scenario_id,
                        "压力条件": name,
                        "是否可行": False,
                        "零碳是否保持": False,
                        "年购普通电/兆瓦时": np.nan,
                        "物理绿电匹配率/%": np.nan,
                        "运营碳排放/吨": np.nan,
                        "年总成本/万元": np.nan,
                        "相对基准成本变化/%": np.nan,
                        "最大母线误差/兆瓦": np.nan,
                        "最大日任务误差/兆瓦时": np.nan,
                        "结论": f"容量配置不可行：{result.status}",
                    }
                )
                continue
            annual_cost = result.summary["annual_total_cost_cny"]
            if scenario_id == "STRESS-PRICE":
                annual_cost = self._price_investment_stress_cost(result.cost_breakdown)
            if scenario_id == "BASE":
                base_cost = annual_cost
            zero_maintained = (
                result.summary["annual_grid_import_mwh"] <= 1e-6
                and result.summary["max_bus_balance_error_mw"] <= 1e-7
                and result.summary["max_daily_production_task_energy_error_mwh"] <= 1e-7
            )
            rows.append(
                {
                    "压力编号": scenario_id,
                    "压力条件": name,
                    "是否可行": True,
                    "零碳是否保持": zero_maintained,
                    "年购普通电/兆瓦时": result.summary["annual_grid_import_mwh"],
                    "物理绿电匹配率/%": result.summary["physical_green_match_rate_percent"],
                    "运营碳排放/吨": result.summary["annual_carbon_emissions_tco2"],
                    "年总成本/万元": annual_cost / 10_000.0,
                    "相对基准成本变化/%": (
                        0.0 if scenario_id == "BASE" else 100.0 * (annual_cost - base_cost) / max(base_cost, 1e-9)
                    ),
                    "最大母线误差/兆瓦": result.summary["max_bus_balance_error_mw"],
                    "最大日任务误差/兆瓦时": result.summary[
                        "max_daily_production_task_energy_error_mwh"
                    ],
                    "结论": "压力下仍保持零碳" if zero_maintained else "压力下失去零碳，需要扩容或备用策略",
                }
            )
        return AgriStressTestResult(pd.DataFrame(rows), results)

    @staticmethod
    def _copy(profiles: pd.DataFrame) -> pd.DataFrame:
        return profiles.copy().reset_index(drop=True)

    @staticmethod
    def _recalculate_total(data: pd.DataFrame) -> pd.DataFrame:
        data["total_meter_load_mw"] = data[
            [
                "irrigation_load_mw",
                "grain_processing_load_mw",
                "storage_cold_chain_load_mw",
                "public_auxiliary_load_mw",
            ]
        ].sum(axis=1)
        return data

    def _low_pv(self, profiles: pd.DataFrame) -> pd.DataFrame:
        data = self._copy(profiles)
        data["pv_availability_pu"] *= 0.70
        return data

    def _irrigation_growth(self, profiles: pd.DataFrame) -> pd.DataFrame:
        data = self._copy(profiles)
        data["irrigation_load_mw"] *= 1.25
        return self._recalculate_total(data)

    def _processing_concentration(self, profiles: pd.DataFrame) -> pd.DataFrame:
        data = self._copy(profiles)
        timestamp = pd.to_datetime(data["timestamp"])
        harvest = (timestamp.dt.month * 100 + timestamp.dt.day).between(915, 1130)
        data.loc[harvest, "grain_processing_load_mw"] *= 1.20
        return self._recalculate_total(data)

    def _direct_restriction(self, profiles: pd.DataFrame) -> pd.DataFrame:
        data = self._copy(profiles)
        data["direct_green_available_mw"] *= 0.60
        return data

    def _grid_restriction(self, profiles: pd.DataFrame) -> pd.DataFrame:
        data = self._copy(profiles)
        timestamp = pd.to_datetime(data["timestamp"])
        restricted = timestamp.dt.strftime("%m-%d").between("10-01", "10-07") & timestamp.dt.hour.between(17, 20)
        data["grid_import_availability_pu"] = 1.0
        data.loc[restricted, "grid_import_availability_pu"] = 0.0
        return data

    @staticmethod
    def _price_investment_stress_cost(cost_breakdown: dict[str, float]) -> float:
        sensitive = {
            "光伏年化投资运维/元",
            "储能年化投资运维/元",
            "直连固定工程年化/元",
            "直连绿电购电/元",
            "公共电网电量费/元",
            "公共电网需量费/元",
        }
        return sum(value * (1.20 if name in sensitive else 1.0) for name, value in cost_breakdown.items())
