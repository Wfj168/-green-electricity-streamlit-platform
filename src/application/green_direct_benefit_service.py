from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

import numpy as np
import pandas as pd

from src.application.agri_energy_flow_service import (
    AgriEnergyFlowRequest,
    AgriEnergyFlowResult,
    AgriEnergyFlowService,
)
from src.core.agri_parameter_registry import phase1_parameter_value
from src.model.agri_zero_carbon_optimizer import (
    AgriOptimizationRequest,
    AgriOptimizationResult,
    AgriZeroCarbonOptimizer,
)


@dataclass(frozen=True, slots=True)
class GreenDirectBenefitRequest:
    target_physical_green_share: float = 1.0
    outage_duration_hours: int = 4


@dataclass(frozen=True, slots=True)
class GreenDirectBenefitResult:
    schemes: pd.DataFrame
    attribution: pd.DataFrame
    contract_terms: dict[str, float]
    methodology: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _EvaluatedScheme:
    code: str
    name: str
    dispatch: pd.DataFrame
    capacities: dict[str, float]
    summary: dict[str, float]
    cost_breakdown: dict[str, float]

    @property
    def annual_cost_cny(self) -> float:
        return float(sum(self.cost_breakdown.values()))


class GreenDirectBenefitService:
    """按统一负荷、价格和碳口径评估绿电直连方案及其收益。

    页面展示的五类方案均由全年时序计算得到。收益归因使用顺序增量瀑布法，
    明确披露顺序依赖，不将其包装为统计因果或概率结果。
    """

    def evaluate(
        self,
        profiles: pd.DataFrame,
        request: GreenDirectBenefitRequest | None = None,
    ) -> GreenDirectBenefitResult:
        request = request or GreenDirectBenefitRequest()
        if not 0.0 <= request.target_physical_green_share <= 1.0:
            raise ValueError("物理绿电匹配目标必须位于0至1之间")
        if request.outage_duration_hours not in {1, 2, 4, 6, 8, 12, 24}:
            raise ValueError("停电压力时长只支持1、2、4、6、8、12或24小时")

        pv_demo = phase1_parameter_value("pv.demo_installed_capacity_mw")
        direct_demo = phase1_parameter_value("green_direct.demo_contract_capacity_mw")
        battery_power_demo = phase1_parameter_value("battery.demo_power_mw")
        battery_energy_demo = phase1_parameter_value("battery.demo_energy_mwh")

        baseline = self._fixed_scheme(
            "G0",
            "纯公共电网基准",
            profiles,
            pv_mw=0.0,
            direct_mw=0.0,
            battery_power_mw=0.0,
            battery_energy_mwh=0.0,
        )
        pv_only = self._fixed_scheme(
            "G1",
            "园区光伏",
            profiles,
            pv_mw=pv_demo,
            direct_mw=0.0,
            battery_power_mw=0.0,
            battery_energy_mwh=0.0,
        )
        direct_only = self._fixed_scheme(
            "G2",
            "绿电直连",
            profiles,
            pv_mw=0.0,
            direct_mw=direct_demo,
            battery_power_mw=0.0,
            battery_energy_mwh=0.0,
        )
        direct_storage = self._fixed_scheme(
            "G3",
            "绿电直连加储能",
            profiles,
            pv_mw=0.0,
            direct_mw=direct_demo,
            battery_power_mw=battery_power_demo,
            battery_energy_mwh=battery_energy_demo,
        )
        optimized = AgriZeroCarbonOptimizer().optimize(
            profiles,
            AgriOptimizationRequest(
                target_physical_green_share=request.target_physical_green_share,
                planning_interval_hours=1,
            ),
        )
        if not optimized.success:
            raise RuntimeError(optimized.status)
        joint = self._optimized_scheme("G4", "源网荷储农业柔性联合优化", optimized)

        displayed = [baseline, pv_only, direct_only, direct_storage, joint]
        outage_slice = self._peak_outage_slice(baseline.dispatch, request.outage_duration_hours)
        baseline_outage_mwh = self._outage_shortfall(baseline.dispatch, outage_slice)
        baseline_emissions = float(baseline.summary["annual_carbon_emissions_tco2"])
        baseline_annual_cost = baseline.annual_cost_cny
        scheme_rows = [
            self._scheme_row(
                scheme,
                baseline_cost_cny=baseline_annual_cost,
                baseline_emissions_tco2=baseline_emissions,
                baseline_outage_mwh=baseline_outage_mwh,
                outage_slice=outage_slice,
            )
            for scheme in displayed
        ]

        final_capacities = joint.capacities
        pv_counterfactual = self._fixed_scheme(
            "A1",
            "归因中间态：加入本地光伏",
            profiles,
            pv_mw=final_capacities["pv_capacity_mw"],
            direct_mw=0.0,
            battery_power_mw=0.0,
            battery_energy_mwh=0.0,
        )
        pv_direct_counterfactual = self._fixed_scheme(
            "A2",
            "归因中间态：加入绿电直连",
            profiles,
            pv_mw=final_capacities["pv_capacity_mw"],
            direct_mw=final_capacities["green_direct_capacity_mw"],
            battery_power_mw=0.0,
            battery_energy_mwh=0.0,
        )
        fixed_combo = self._fixed_scheme(
            "A3",
            "归因中间态：加入储能",
            profiles,
            pv_mw=final_capacities["pv_capacity_mw"],
            direct_mw=final_capacities["green_direct_capacity_mw"],
            battery_power_mw=final_capacities["battery_power_mw"],
            battery_energy_mwh=final_capacities["battery_energy_mwh"],
        )
        attribution_rows = self._attribution_rows(
            baseline,
            pv_counterfactual,
            pv_direct_counterfactual,
            fixed_combo,
            joint,
        )
        outage_start = pd.Timestamp(baseline.dispatch.iloc[outage_slice.start]["timestamp"])
        outage_end = pd.Timestamp(baseline.dispatch.iloc[outage_slice.stop - 1]["timestamp"])
        methodology = {
            "baseline": "纯公共电网承担同一组农业负荷",
            "comparisonPrinciple": "同一年度、同一农业负荷、同一分时电价、同一排放因子",
            "benefitAttribution": "顺序增量瀑布法：本地光伏→绿电直连→储能→农业柔性联合调度；结果具有顺序依赖",
            "outageScenario": {
                "selection": "自动选择基准方案公共电网需求最大的连续窗口",
                "start": outage_start.isoformat(),
                "end": outage_end.isoformat(),
                "durationHours": request.outage_duration_hours,
            },
            "uncertainty": "尚未取得概率分布，不展示P10、P50、P90，避免制造虚假精度",
            "carbonBoundary": "仅计园区运行期购入普通电范围二排放；物理绿电与绿证分开，当前未使用绿证抵扣",
            "dataStatus": "演示参数待项目资料替换",
        }
        return GreenDirectBenefitResult(
            pd.DataFrame(scheme_rows),
            pd.DataFrame(attribution_rows),
            self._contract_terms(),
            methodology,
        )

    def _fixed_scheme(
        self,
        code: str,
        name: str,
        profiles: pd.DataFrame,
        *,
        pv_mw: float,
        direct_mw: float,
        battery_power_mw: float,
        battery_energy_mwh: float,
    ) -> _EvaluatedScheme:
        flow = AgriEnergyFlowService().simulate(
            profiles,
            AgriEnergyFlowRequest(
                pv_capacity_mw=pv_mw,
                green_direct_capacity_mw=direct_mw,
                battery_power_mw=battery_power_mw,
                battery_energy_mwh=battery_energy_mwh,
                battery_initial_soc=phase1_parameter_value("battery.soc_min"),
            ),
        )
        capacities = {
            "pv_capacity_mw": pv_mw,
            "green_direct_capacity_mw": direct_mw,
            "battery_power_mw": battery_power_mw,
            "battery_energy_mwh": battery_energy_mwh,
            "grid_peak_mw": float(flow.dispatch["grid_to_load_mw"].max()),
        }
        dispatch = flow.dispatch.copy()
        dispatch["direct_export_mw"] = dispatch["direct_green_export_mw"]
        dispatch["direct_curtailment_mw"] = dispatch["direct_green_curtailment_mw"]
        dt = self._time_step_hours(dispatch)
        optimizer = AgriZeroCarbonOptimizer()
        fixed_direct_annual = self._direct_fixed_annual(optimizer, direct_mw)
        costs = optimizer._cost_breakdown(dispatch, capacities, dt, fixed_direct_annual)
        costs.update(self._contract_settlement(dispatch, direct_mw, dt))
        return _EvaluatedScheme(code, name, dispatch, capacities, flow.summary, costs)

    def _optimized_scheme(
        self,
        code: str,
        name: str,
        result: AgriOptimizationResult,
    ) -> _EvaluatedScheme:
        dispatch = result.dispatch.copy()
        dt = self._time_step_hours(dispatch)
        costs = dict(result.cost_breakdown)
        costs.update(
            self._contract_settlement(
                dispatch,
                result.capacities["green_direct_capacity_mw"],
                dt,
            )
        )
        summary = dict(result.summary)
        summary["annual_total_cost_cny"] = float(sum(costs.values()))
        return _EvaluatedScheme(code, name, dispatch, dict(result.capacities), summary, costs)

    @staticmethod
    def _time_step_hours(dispatch: pd.DataFrame) -> float:
        timestamps = pd.to_datetime(dispatch["timestamp"])
        if len(timestamps) <= 1:
            return 1.0
        return float(timestamps.diff().dropna().dt.total_seconds().median()) / 3600.0

    @staticmethod
    def _direct_fixed_annual(optimizer: AgriZeroCarbonOptimizer, direct_mw: float) -> float:
        if direct_mw <= 1e-9:
            return 0.0
        return phase1_parameter_value("green_direct.base_fixed_cost_cny") * (
            optimizer._capital_recovery_factor()
            + phase1_parameter_value("finance.fixed_om_rate")
        )

    @staticmethod
    def _contract_terms() -> dict[str, float]:
        codes = {
            "transmissionFeeCnyPerMwh": "green_direct.transmission_fee_cny_per_mwh",
            "auxiliaryFeeCnyPerMwh": "green_direct.auxiliary_fee_cny_per_mwh",
            "capacityFeeCnyPerMwYear": "green_direct.capacity_fee_cny_per_mw_year",
            "minimumTakeRatio": "green_direct.minimum_take_ratio",
            "deviationToleranceRatio": "green_direct.deviation_tolerance_ratio",
            "deviationPenaltyCnyPerMwh": "green_direct.deviation_penalty_cny_per_mwh",
            "availabilityTarget": "green_direct.availability_target",
        }
        return {name: phase1_parameter_value(code) for name, code in codes.items()}

    def _contract_settlement(
        self,
        dispatch: pd.DataFrame,
        direct_capacity_mw: float,
        dt: float,
    ) -> dict[str, float]:
        terms = self._contract_terms()
        if direct_capacity_mw <= 1e-9:
            return {
                "直连输配费用/元": 0.0,
                "直连辅助服务费用/元": 0.0,
                "直连通道容量费/元": 0.0,
                "最低消纳不足费用/元": 0.0,
                "超限偏差考核/元": 0.0,
            }
        injected = float(dispatch["direct_green_injected_mw"].sum() * dt)
        line_loss = float(dispatch["direct_green_line_loss_mw"].sum() * dt)
        delivered = max(injected - line_loss, 0.0)
        annual_hours = len(dispatch) * dt
        minimum_take = direct_capacity_mw * annual_hours * terms["minimumTakeRatio"]
        minimum_take_shortfall = max(minimum_take - injected, 0.0)
        # 未接入合同计划曲线前，以模型可用曲线作为计划，因此不虚构偏差费用。
        deviation_penalty = 0.0
        return {
            "直连输配费用/元": delivered * terms["transmissionFeeCnyPerMwh"],
            "直连辅助服务费用/元": delivered * terms["auxiliaryFeeCnyPerMwh"],
            "直连通道容量费/元": direct_capacity_mw * terms["capacityFeeCnyPerMwYear"],
            "最低消纳不足费用/元": minimum_take_shortfall
            * phase1_parameter_value("green_direct.base_lcoe_cny_per_mwh"),
            "超限偏差考核/元": deviation_penalty,
        }

    @staticmethod
    def _peak_outage_slice(dispatch: pd.DataFrame, duration_hours: int) -> slice:
        dt = GreenDirectBenefitService._time_step_hours(dispatch)
        intervals = max(1, int(round(duration_hours / dt)))
        rolling = dispatch["grid_to_load_mw"].rolling(intervals).sum()
        stop = int(rolling.idxmax()) + 1
        return slice(max(0, stop - intervals), stop)

    @staticmethod
    def _outage_shortfall(dispatch: pd.DataFrame, outage_slice: slice) -> float:
        dt = GreenDirectBenefitService._time_step_hours(dispatch)
        return float(dispatch.iloc[outage_slice]["grid_to_load_mw"].sum() * dt)

    def _scheme_row(
        self,
        scheme: _EvaluatedScheme,
        *,
        baseline_cost_cny: float,
        baseline_emissions_tco2: float,
        baseline_outage_mwh: float,
        outage_slice: slice,
    ) -> dict[str, Any]:
        cost = scheme.annual_cost_cny
        savings = baseline_cost_cny - cost
        emissions = float(scheme.summary["annual_carbon_emissions_tco2"])
        outage_shortfall = self._outage_shortfall(scheme.dispatch, outage_slice)
        avoided_outage = baseline_outage_mwh - outage_shortfall
        capex = self._upfront_capex(scheme.capacities)
        crf = AgriZeroCarbonOptimizer()._capital_recovery_factor()
        annual_cash_savings = baseline_cost_cny - (cost - capex * crf)
        planning_years = int(phase1_parameter_value("finance.planning_years"))
        discount_rate = phase1_parameter_value("finance.discount_rate")
        npv = -capex + sum(
            annual_cash_savings / (1.0 + discount_rate) ** year
            for year in range(1, planning_years + 1)
        )
        direct_injected = float(scheme.summary.get("annual_direct_green_injected_mwh", 0.0))
        direct_loss = float(scheme.summary.get("annual_direct_green_line_loss_mwh", 0.0))
        if direct_loss == 0.0 and "direct_green_line_loss_mw" in scheme.dispatch:
            direct_loss = float(
                scheme.dispatch["direct_green_line_loss_mw"].sum()
                * self._time_step_hours(scheme.dispatch)
            )
        return {
            "方案编号": scheme.code,
            "方案": scheme.name,
            "本地光伏/兆瓦": scheme.capacities["pv_capacity_mw"],
            "绿电直连/兆瓦": scheme.capacities["green_direct_capacity_mw"],
            "储能功率/兆瓦": scheme.capacities["battery_power_mw"],
            "储能容量/兆瓦时": scheme.capacities["battery_energy_mwh"],
            "年总成本/元": cost,
            "相对基准年节省/元": savings,
            "相对基准节省率/%": 100.0 * savings / max(baseline_cost_cny, 1e-9),
            "初始投资/元": capex,
            "净现值/元": npv,
            "内部收益率/%": self._irr_percent(capex, annual_cash_savings, planning_years),
            "静态回收期/年": capex / annual_cash_savings if annual_cash_savings > 1e-9 else None,
            "年购普通电/兆瓦时": float(scheme.summary["annual_grid_import_mwh"]),
            "物理绿电匹配率/%": float(scheme.summary["physical_green_match_rate_percent"]),
            "运营碳排放/吨": emissions,
            "相对基准减排/吨": baseline_emissions_tco2 - emissions,
            "直连送端注入/兆瓦时": direct_injected,
            "直连受端送达/兆瓦时": max(direct_injected - direct_loss, 0.0),
            "直连线路损耗/兆瓦时": direct_loss,
            "最大电网需量/兆瓦": scheme.capacities["grid_peak_mw"],
            "停电窗口缺供/兆瓦时": outage_shortfall,
            "相对基准避免缺供/兆瓦时": avoided_outage,
            "停电损失避免/元": avoided_outage
            * phase1_parameter_value("reliability.outage_loss_cny_per_mwh"),
            "停电窗口生产供能率/%": 100.0
            * (baseline_outage_mwh - outage_shortfall)
            / max(baseline_outage_mwh, 1e-9),
            "最大母线平衡误差/兆瓦": float(scheme.summary["max_bus_balance_error_mw"]),
            "结论": (
                "对照基准：全部农业用电由公共电网供应"
                if scheme.code == "G0"
                else self._conclusion(savings, emissions, scheme.summary)
            ),
        }

    @staticmethod
    def _upfront_capex(capacities: dict[str, float]) -> float:
        pv = capacities["pv_capacity_mw"] * phase1_parameter_value("pv.capex_cny_per_mw")
        battery = (
            capacities["battery_power_mw"]
            * phase1_parameter_value("battery.capex_power_cny_per_mw")
            + capacities["battery_energy_mwh"]
            * phase1_parameter_value("battery.capex_energy_cny_per_mwh")
        )
        direct = (
            phase1_parameter_value("green_direct.base_fixed_cost_cny")
            if capacities["green_direct_capacity_mw"] > 1e-9
            else 0.0
        )
        return pv + battery + direct

    @staticmethod
    def _irr_percent(capex: float, annual_cash_savings: float, years: int) -> float | None:
        if capex <= 1e-9:
            return None
        if annual_cash_savings <= 1e-9:
            return None

        def npv(rate: float) -> float:
            return -capex + sum(annual_cash_savings / (1.0 + rate) ** year for year in range(1, years + 1))

        low, high = -0.99, 10.0
        if npv(low) * npv(high) > 0:
            return None
        for _ in range(120):
            middle = (low + high) / 2.0
            value = npv(middle)
            if value > 0:
                low = middle
            else:
                high = middle
        result = 100.0 * (low + high) / 2.0
        return result if isfinite(result) else None

    @staticmethod
    def _conclusion(
        savings_cny: float,
        emissions_tco2: float,
        summary: dict[str, float],
    ) -> str:
        zero = emissions_tco2 <= phase1_parameter_value("carbon.zero_tolerance_tco2")
        balanced = summary["max_bus_balance_error_mw"] <= 1e-7
        if zero and balanced and savings_cny >= 0:
            return "计算上实现零碳且年化成本不高于基准，正式参数仍待核验"
        if zero and balanced:
            return "计算上实现零碳，但年化成本高于基准"
        if savings_cny >= 0:
            return "具有经济节省，但尚未实现零碳"
        return "当前演示参数下成本和零碳目标均无优势"

    @staticmethod
    def _attribution_rows(
        baseline: _EvaluatedScheme,
        pv: _EvaluatedScheme,
        pv_direct: _EvaluatedScheme,
        fixed_combo: _EvaluatedScheme,
        joint: _EvaluatedScheme,
    ) -> list[dict[str, float | str]]:
        stages = [
            ("本地光伏", baseline, pv),
            ("绿电直连", pv, pv_direct),
            ("储能", pv_direct, fixed_combo),
            ("农业柔性与联合优化", fixed_combo, joint),
        ]
        total = baseline.annual_cost_cny - joint.annual_cost_cny
        return [
            {
                "贡献环节": name,
                "增量年成本节省/元": before.annual_cost_cny - after.annual_cost_cny,
                "占最终净节省/%": (
                    100.0 * (before.annual_cost_cny - after.annual_cost_cny) / total
                    if abs(total) > 1e-9
                    else 0.0
                ),
                "说明": "负值表示该环节增加年化成本；归因结果受加入顺序影响",
            }
            for name, before, after in stages
        ]
