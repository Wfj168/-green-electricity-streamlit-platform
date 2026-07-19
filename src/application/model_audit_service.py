from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class ModelAuditResult:
    checks: pd.DataFrame
    overall_status: str
    passed_count: int
    notice_count: int
    review_count: int


class ModelAuditService:
    """Audit V17 inputs and outputs without hiding demonstration-data limitations."""

    def analyze(
        self,
        *,
        metrics: dict[str, Any],
        tables: dict[str, pd.DataFrame],
        scenario: dict[str, Any],
    ) -> ModelAuditResult:
        rows: list[dict[str, str]] = []
        profiles = tables.get("profiles", pd.DataFrame())
        dispatch = tables.get("dispatch", pd.DataFrame())
        diagnostics = tables.get("diagnostics", pd.DataFrame())
        capacity = tables.get("capacity", pd.DataFrame())
        diagnostic_values = self._key_value(diagnostics, "Diagnostic")

        self._range_check(
            rows, "输入假设", "光伏单位投资", scenario.get("capex_pv"), 2_500_000, 6_000_000,
            "元/兆瓦", "公开项目造价筛查区间；正式交付以属地询价为准。",
        )
        self._range_check(
            rows, "输入假设", "风电单位投资", scenario.get("capex_wt"), 4_000_000, 10_000_000,
            "元/兆瓦", "行业公开成本筛查区间；不包含具体场址差异。",
        )
        self._range_check(
            rows, "输入假设", "电池单位能量投资", scenario.get("capex_bat_e"), 500_000, 2_000_000,
            "元/兆瓦时", "需与功率侧投资合并理解。",
        )
        self._range_check(
            rows, "输入假设", "碳市场价格", scenario.get("carbon_market_price_cny_per_tco2"), 0, 500,
            "元/吨", "演示价格不代表实际履约成交价。",
        )

        average_buy_price = self._weighted_average(profiles, "electricity_buy_price")
        average_gas_price = self._weighted_average(profiles, "gas_price")
        self._range_check(
            rows, "输入假设", "年加权平均购电价", average_buy_price, 200, 1_200,
            "元/兆瓦时", "用于识别数量级错误，实际执行电价需按当地规则分解。",
        )
        self._range_check(
            rows, "输入假设", "年加权平均燃气价", average_gas_price, 150, 600,
            "元/兆瓦时燃气", "当前为热值口径，项目接入数据库时需同步保存原始计价单位。",
        )

        annual_days = self._annual_days(profiles)
        self._relation_check(
            rows,
            "数据完整性",
            "典型日年度权重",
            annual_days,
            abs(annual_days - 365.0) <= 1e-9,
            "应等于365天",
            "权重用于将典型日结果折算为年度结果。",
        )
        source_types = (
            sorted(profiles["data_source_type"].dropna().astype(str).unique().tolist())
            if "data_source_type" in profiles
            else []
        )
        rows.append(
            {
                "类别": "数据完整性",
                "检查项目": "输入数据来源",
                "实际值": "、".join(source_types) if source_types else "未标注",
                "合理范围或关系": "正式项目应标明来源、版本和时间范围",
                "状态": "提示",
                "说明": "当前V17使用特征化合成典型日，只能用于模型方法和方案筛查，不能表述为实测线路数据。",
            }
        )

        for label, key in [
            ("最大电力平衡误差", "Maximum electric balance error"),
            ("最大热力平衡误差", "Maximum heat balance error"),
            ("最大冷量平衡误差", "Maximum cooling balance error"),
        ]:
            value = abs(float(diagnostic_values.get(key, 0.0) or 0.0))
            self._relation_check(
                rows, "物理一致性", label, value, value <= 1e-6, "不大于0.000001兆瓦",
                "数值误差超过阈值时需核查平衡方程或求解容差。",
            )

        private_total = float(metrics.get("Private total annual cost", 0.0) or 0.0)
        private_parts = sum(
            float(metrics.get(key, 0.0) or 0.0)
            for key in ["Annualized capital cost", "Fixed O&M cost", "Variable operating annual cost"]
        )
        private_error = private_total - private_parts
        self._relation_check(
            rows, "经济性", "项目年度成本对账", private_error, abs(private_error) <= 1e-4,
            "总额等于年化投资、固定运维和可变运行之和", "实际值为对账差额，单位为元。",
        )
        social_total = float(metrics.get("Social total annual cost", 0.0) or 0.0)
        social_error = social_total - private_total - float(metrics.get("Carbon external cost", 0.0) or 0.0)
        self._relation_check(
            rows, "经济性", "社会年度成本对账", social_error, abs(social_error) <= 1e-4,
            "社会成本等于项目成本加碳成本", "实际值为对账差额，单位为元。",
        )

        annual_service = self._annual_service(dispatch)
        unit_service_cost = social_total / annual_service if annual_service > 1e-9 else np.nan
        self._range_check(
            rows, "经济性", "单位多能服务社会成本", unit_service_cost, 100, 3_000,
            "元/兆瓦时服务量", "用于发现成本数量级异常，不作为项目收益率结论。",
        )

        source_emissions = self._source_emissions(dispatch, scenario)
        emissions_error = source_emissions - float(metrics.get("Annual CO2 emissions", 0.0) or 0.0)
        self._relation_check(
            rows, "低碳", "排放来源对账", emissions_error, abs(emissions_error) <= 1e-4,
            "购电、热电联产与燃气锅炉排放之和等于总排放", "实际值为对账差额，单位为吨。",
        )

        service_rate = float(metrics.get("Total multi-energy service rate", 0.0) or 0.0)
        self._relation_check(
            rows, "可靠性", "多能服务保障率", service_rate, service_rate >= 99.9,
            "不低于99.9%", "保障率过高并不自动等于项目真实可靠性，仍需停电与故障压力测试。",
        )
        overlap = max(
            float(metrics.get(key, 0.0) or 0.0)
            for key in [
                "Grid import-export overlap",
                "Battery simultaneous overlap",
                "Thermal-storage simultaneous overlap",
            ]
        )
        self._relation_check(
            rows, "物理一致性", "互斥运行重叠量", overlap, overlap <= 1e-6,
            "不大于0.000001兆瓦时/年", "检查同时购售电和储能同时充放。",
        )

        utilization = float(metrics.get("Renewable utilization rate (including export)", 0.0) or 0.0)
        self._range_check(
            rows, "新能源", "新能源综合利用率", utilization, 80, 100, "%",
            "低于筛查区间时应核查容量过建、外送和储能配置。", soft=True,
        )
        curtailment = float(metrics.get("Renewable curtailment rate", 0.0) or 0.0)
        self._range_check(
            rows, "新能源", "新能源弃电率", curtailment, 0, 20, "%",
            "该范围用于演示结果筛查，不是政策承诺值。", soft=True,
        )

        upper_bounds = (
            int(pd.to_numeric(capacity["Upper bound binding"], errors="coerce").fillna(0).astype(bool).sum())
            if "Upper bound binding" in capacity
            else 0
        )
        rows.append(
            {
                "类别": "规划边界",
                "检查项目": "触及容量搜索上限的设备数",
                "实际值": str(upper_bounds),
                "合理范围或关系": "建议为0；大于0时扩大搜索上限复算",
                "状态": "通过" if upper_bounds == 0 else "提示",
                "说明": "触及上限不代表结果错误，但可能意味着规划空间被人为截断。",
            }
        )

        checks = pd.DataFrame(rows)
        passed = int(checks["状态"].eq("通过").sum())
        notices = int(checks["状态"].eq("提示").sum())
        reviews = int(checks["状态"].eq("需核查").sum())
        overall = "需核查" if reviews else ("通过（含提示）" if notices else "通过")
        return ModelAuditResult(checks, overall, passed, notices, reviews)

    @staticmethod
    def _key_value(table: pd.DataFrame, key_column: str) -> dict[str, Any]:
        if table.empty or key_column not in table or "Value" not in table:
            return {}
        return table.set_index(key_column)["Value"].to_dict()

    @staticmethod
    def _weighted_average(profiles: pd.DataFrame, column: str) -> float:
        if profiles.empty or column not in profiles:
            return float("nan")
        weights = pd.to_numeric(profiles.get("day_weight", 1.0), errors="coerce").fillna(1.0)
        if "dt" in profiles:
            weights = weights * pd.to_numeric(profiles["dt"], errors="coerce").fillna(1.0)
        values = pd.to_numeric(profiles[column], errors="coerce")
        valid = values.notna() & weights.notna()
        return float(np.average(values[valid], weights=weights[valid])) if valid.any() else float("nan")

    @staticmethod
    def _annual_days(profiles: pd.DataFrame) -> float:
        if profiles.empty or "day_weight" not in profiles:
            return 0.0
        if "day_id" in profiles:
            return float(profiles.groupby("day_id")["day_weight"].first().sum())
        return float(pd.to_numeric(profiles["day_weight"], errors="coerce").fillna(0.0).sum())

    @staticmethod
    def _annual_service(dispatch: pd.DataFrame) -> float:
        required = {"electric_load", "heat_load", "cooling_load"}
        if dispatch.empty or not required.issubset(dispatch.columns):
            return 0.0
        weights = pd.to_numeric(dispatch.get("day_weight", 1.0), errors="coerce").fillna(1.0)
        dt = pd.to_numeric(dispatch.get("dt", 1.0), errors="coerce").fillna(1.0)
        loads = sum(pd.to_numeric(dispatch[column], errors="coerce").fillna(0.0) for column in required)
        return float((loads * dt * weights).sum())

    @staticmethod
    def _source_emissions(dispatch: pd.DataFrame, scenario: dict[str, Any]) -> float:
        required = {"P_grid_buy", "G_CHP", "G_GB"}
        if dispatch.empty or not required.issubset(dispatch.columns):
            return 0.0
        weights = pd.to_numeric(dispatch.get("day_weight", 1.0), errors="coerce").fillna(1.0)
        dt = pd.to_numeric(dispatch.get("dt", 1.0), errors="coerce").fillna(1.0)
        grid = pd.to_numeric(dispatch["P_grid_buy"], errors="coerce").fillna(0.0)
        gas = (
            pd.to_numeric(dispatch["G_CHP"], errors="coerce").fillna(0.0)
            + pd.to_numeric(dispatch["G_GB"], errors="coerce").fillna(0.0)
        )
        rate = grid * float(scenario.get("grid_emission_factor", 0.55))
        rate += gas * float(scenario.get("gas_emission_factor", 0.20))
        return float((rate * dt * weights).sum())

    @staticmethod
    def _range_check(
        rows: list[dict[str, str]],
        category: str,
        name: str,
        value: Any,
        minimum: float,
        maximum: float,
        unit: str,
        note: str,
        *,
        soft: bool = False,
    ) -> None:
        number = float(value) if value is not None else float("nan")
        passed = bool(np.isfinite(number) and minimum <= number <= maximum)
        rows.append(
            {
                "类别": category,
                "检查项目": name,
                "实际值": f"{number:,.4g} {unit}" if np.isfinite(number) else "缺失",
                "合理范围或关系": f"{minimum:,.4g}—{maximum:,.4g} {unit}",
                "状态": "通过" if passed else ("提示" if soft else "需核查"),
                "说明": note,
            }
        )

    @staticmethod
    def _relation_check(
        rows: list[dict[str, str]],
        category: str,
        name: str,
        value: float,
        passed: bool,
        relation: str,
        note: str,
    ) -> None:
        rows.append(
            {
                "类别": category,
                "检查项目": name,
                "实际值": f"{value:,.6g}",
                "合理范围或关系": relation,
                "状态": "通过" if passed else "需核查",
                "说明": note,
            }
        )
