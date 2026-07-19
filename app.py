from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.application import (
    CarbonAnalysisService,
    GreenDirectRequest,
    GreenDirectService,
    ForecastService,
    IntradayRollingRequest,
    IntradayRollingService,
    ModelExecutionRequest,
    ModelExecutionResult,
    ModelAuditService,
    ModelKind,
    ScenarioComparisonResult,
    ScenarioComparisonService,
    SimulationRequest,
    SimulationService,
    UnifiedModelService,
    get_integrated_scenario,
    list_integrated_scenarios,
)
from src.api.client import ApiClientError, PlatformApiClient
from src.core import (
    FifteenMinuteDataContract,
    IntegratedPlanningConfig,
    TimeSeriesValidationResult,
    sample_15min_data,
    scenario_fingerprint,
)
from src.core.schemas import StoreMoreInputs
from src.presentation import localize_v17_table
from src.storemore_engine import (
    csv_template,
    default_capex_table,
    default_fuel_table,
    default_generator_table,
    default_storage_table,
)
from src.ui_components import (
    badge,
    empty_hint,
    inject_global_css,
    metric_card,
    page_title,
    pills,
    section_label,
    status_box,
)


st.set_page_config(
    page_title="园区低碳规划与绿电直连优化平台",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_css()


REALTIME_PAGES = [
    "平台概览",
    "参数配置与运行",
    "运行分析",
    "绿电决策",
]

INTEGRATED_PAGES = [
    "平台概览",
    "参数配置与运行",
    "运行分析",
    "场景与决策",
]

MODEL_LABELS = {
    ModelKind.REALTIME_DISPATCH.value: "快速电力滚动调度",
    ModelKind.INTEGRATED_PLANNING.value: "V17综合能源规划",
}


def init_state() -> None:
    defaults: dict[str, Any] = {
        "simulation_result": None,
        "simulation_inputs": None,
        "generator_table": default_generator_table(),
        "storage_table": default_storage_table(),
        "fuel_table": default_fuel_table(),
        "capex_table": default_capex_table(),
        "model_kind": ModelKind.REALTIME_DISPATCH.value,
        "integrated_result": None,
        "integrated_payload": None,
        "scenario_comparison_result": None,
        "timeseries_validation": None,
        "forecast_evaluation": None,
        "day_ahead_forecast": None,
        "intraday_plan": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def result() -> dict[str, Any] | None:
    value = st.session_state.get("simulation_result")
    return value if isinstance(value, dict) and value.get("success") else None


def integrated_result() -> ModelExecutionResult | None:
    value = st.session_state.get("integrated_result")
    return value if isinstance(value, ModelExecutionResult) and value.success else None


def current_model_kind() -> str:
    value = str(st.session_state.get("model_kind", ModelKind.REALTIME_DISPATCH.value))
    return value if value in MODEL_LABELS else ModelKind.REALTIME_DISPATCH.value


def scenario_comparison_result() -> ScenarioComparisonResult | None:
    value = st.session_state.get("scenario_comparison_result")
    return value if isinstance(value, ScenarioComparisonResult) else None


def metrics_dict(simulation: dict[str, Any]) -> dict[str, float]:
    metrics = simulation["metrics"]
    return dict(zip(metrics["Metric"], metrics["Value"]))


def input_dict() -> dict[str, Any]:
    inputs = st.session_state.get("simulation_inputs")
    if inputs is None:
        return {}
    if hasattr(inputs, "__dataclass_fields__"):
        return asdict(inputs)
    return dict(inputs)


def fmt(value: float | int | None, digits: int = 2) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if abs(number) >= 1000:
        return f"{number:,.{digits}f}"
    return f"{number:.{digits}f}"


def build_inputs(
    scenario_name: str,
    total_demand: float,
    service_life: int,
    import_price: float,
    export_price: float,
    import_export_capacity: float,
    rps_constraint: bool,
    min_res_share: float,
    co2_constraint: bool,
    max_co2: float,
    ceep_constraint: bool,
    max_ceep: float,
    optimize_capacity: bool,
    restrict_investments: bool,
    rolling_days: int,
    country_code: str,
) -> StoreMoreInputs:
    return StoreMoreInputs(
        scenario_name=scenario_name,
        total_demand=total_demand,
        service_life=service_life,
        import_price=import_price,
        export_price=export_price,
        import_export_capacity=import_export_capacity,
        rps_constraint=rps_constraint,
        min_res_share=min_res_share,
        co2_constraint=co2_constraint,
        max_co2=max_co2,
        ceep_constraint=ceep_constraint,
        max_ceep=max_ceep,
        optimize_capacity=optimize_capacity,
        restrict_investments=restrict_investments,
        rolling_days=rolling_days,
        country_code=country_code,
    )


def run_scenario(
    inputs: StoreMoreInputs,
    generator_df: pd.DataFrame,
    storage_df: pd.DataFrame,
    fuel_df: pd.DataFrame,
    capex_df: pd.DataFrame,
    uploaded_csv=None,
) -> dict[str, Any]:
    simulation = SimulationService().run(
        SimulationRequest(
            inputs=inputs,
            generator_table=generator_df,
            storage_table=storage_df,
            fuel_table=fuel_df,
            capex_table=capex_df,
            uploaded_csv=uploaded_csv,
        )
    )
    if simulation.get("success"):
        st.session_state["simulation_result"] = simulation
        st.session_state["simulation_inputs"] = inputs
        st.session_state["generator_table"] = generator_df
        st.session_state["storage_table"] = storage_df
        st.session_state["fuel_table"] = fuel_df
        st.session_state["capex_table"] = capex_df
    return simulation


def run_default_scenario() -> None:
    inputs = build_inputs(
        scenario_name="默认园区实时场景",
        total_demand=1_000_000.0,
        service_life=25,
        import_price=450.0,
        export_price=350.0,
        import_export_capacity=500.0,
        rps_constraint=True,
        min_res_share=35.0,
        co2_constraint=False,
        max_co2=100_000.0,
        ceep_constraint=False,
        max_ceep=20.0,
        optimize_capacity=True,
        restrict_investments=False,
        rolling_days=3,
        country_code="CN",
    )
    simulation = run_scenario(
        inputs,
        default_generator_table(),
        default_storage_table(),
        default_fuel_table(),
        default_capex_table(),
    )
    if not simulation.get("success"):
        st.error(f"默认场景计算失败：{simulation.get('message')}")


def require_result(message: str = "请先在“参数配置与运行”页面完成一次实时优化。") -> dict[str, Any] | None:
    simulation = result()
    if simulation is None:
        empty_hint("尚未生成实时结果", message)
        if st.button("运行默认场景", type="primary"):
            with st.spinner("正在计算默认场景..."):
                run_default_scenario()
            st.rerun()
        return None
    return simulation


def require_integrated_result() -> ModelExecutionResult | None:
    execution = integrated_result()
    if execution is None:
        empty_hint("尚未生成综合规划结果", "请先在“参数配置与运行”页面选择S0—S8场景并完成综合能源规划。")
        return None
    return execution


def plot_layout(fig: go.Figure, height: int = 430) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=20, r=20, t=54, b=36),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08, x=0),
    )
    return fig


def generation_figure(dispatch: pd.DataFrame) -> go.Figure:
    series = {
        "Solar": ("光伏出力", "#f59e0b"),
        "Wind": ("风电出力", "#22c55e"),
        "Gas": ("燃气发电", "#f97316"),
        "Import": ("电网购电", "#2563eb"),
        "Storage discharge": ("储能放电", "#8b5cf6"),
    }
    fig = go.Figure()
    for column, (label, color) in series.items():
        fig.add_trace(
            go.Scatter(
                x=dispatch["Period"],
                y=dispatch[column],
                mode="lines",
                stackgroup="supply",
                name=label,
                line=dict(width=1.5, color=color),
            )
        )
    fig.add_trace(
        go.Scatter(
            x=dispatch["Period"],
            y=dispatch["Demand"],
            mode="lines",
            name="电力负荷",
            line=dict(width=3, color="#111827"),
        )
    )
    fig.update_xaxes(title="滚动小时")
    fig.update_yaxes(title="功率 / 兆瓦")
    fig.update_layout(title="电力平衡实时计算结果")
    return plot_layout(fig)


def storage_figure(dispatch: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=dispatch["Period"],
            y=-dispatch["Storage charge"],
            name="储能充电",
            marker_color="#38bdf8",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(
            x=dispatch["Period"],
            y=dispatch["Storage discharge"],
            name="储能放电",
            marker_color="#a855f7",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=dispatch["Period"],
            y=dispatch["SOC"],
            name="储能荷电状态",
            line=dict(color="#16a34a", width=3),
        ),
        secondary_y=True,
    )
    fig.update_layout(title="储能充放电与荷电状态")
    fig.update_xaxes(title="滚动小时")
    fig.update_yaxes(title_text="充放电功率 / 兆瓦", secondary_y=False)
    fig.update_yaxes(title_text="储能量 / 兆瓦时", secondary_y=True)
    return plot_layout(fig)


def balance_figure(dispatch: pd.DataFrame) -> go.Figure:
    total_supply = dispatch[["Solar", "Wind", "Gas", "Import", "Storage discharge"]].sum(axis=1)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dispatch["Period"], y=dispatch["Demand"], mode="lines", name="电力负荷", line=dict(color="#111827", width=3)))
    fig.add_trace(go.Scatter(x=dispatch["Period"], y=total_supply, mode="lines", name="总供电", line=dict(color="#0ea5e9", width=3)))
    fig.add_trace(go.Bar(x=dispatch["Period"], y=dispatch["Excess"], name="富余电量", marker_color="#f59e0b"))
    fig.add_trace(go.Bar(x=dispatch["Period"], y=dispatch["Unmet"], name="未满足电量", marker_color="#ef4444"))
    fig.update_layout(title="供需校核、弃电与缺电", barmode="group")
    fig.update_xaxes(title="滚动小时")
    fig.update_yaxes(title="平均功率 / 兆瓦")
    return plot_layout(fig)


def price_dispatch_figure(dispatch: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=dispatch["Period"], y=dispatch["Import price"], name="购电价格", line=dict(color="#2563eb", width=2)), secondary_y=True)
    fig.add_trace(go.Scatter(x=dispatch["Period"], y=dispatch["Export price"], name="售电价格", line=dict(color="#64748b", width=2, dash="dot")), secondary_y=True)
    fig.add_trace(go.Bar(x=dispatch["Period"], y=dispatch["Import"], name="购电功率", marker_color="#93c5fd"), secondary_y=False)
    fig.add_trace(go.Bar(x=dispatch["Period"], y=-dispatch["Export"], name="售电功率", marker_color="#fbbf24"), secondary_y=False)
    fig.update_layout(title="电价驱动的购售电行为")
    fig.update_xaxes(title="滚动小时")
    fig.update_yaxes(title_text="购售电功率 / 兆瓦", secondary_y=False)
    fig.update_yaxes(title_text="价格 / 元每兆瓦时", secondary_y=True)
    return plot_layout(fig)


def metrics_bar_figure(metrics: dict[str, float]) -> go.Figure:
    selected = {
        "Renewable share [%]": "绿电占比",
        "CEEP share [%]": "弃电率",
        "CO2 emissions [tCO2]": "碳排放",
        "Total cost proxy [CNY]": "综合成本",
    }
    values = [float(metrics.get(key, 0.0)) for key in selected]
    fig = go.Figure(
        go.Bar(
            x=list(selected.values()),
            y=values,
            marker_color=["#16a34a", "#f59e0b", "#ef4444", "#2563eb"],
            text=[fmt(v) for v in values],
            textposition="outside",
        )
    )
    fig.update_layout(title="关键指标实时汇总")
    fig.update_yaxes(title="指标值")
    return plot_layout(fig, height=380)


def rolling_figure(rolling_log: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=rolling_log["Rolling day"],
            y=rolling_log["Objective value of 48h window"],
            name="48小时窗口目标值",
            marker_color="#0ea5e9",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=rolling_log["Rolling day"],
            y=rolling_log["Final SOC after saved horizon [MWh]"],
            name="保存时段末端储能量",
            yaxis="y2",
            line=dict(color="#22c55e", width=3),
        )
    )
    fig.update_layout(
        title="滚动优化窗口状态",
        yaxis=dict(title="目标函数值"),
        yaxis2=dict(title="末端储能量 / 兆瓦时", overlaying="y", side="right"),
    )
    fig.update_xaxes(title="滚动日")
    return plot_layout(fig, height=380)


def green_cost_figure(costs: dict[str, float]) -> go.Figure:
    colors = ["#16a34a", "#2563eb", "#9333ea"]
    fig = go.Figure(
        go.Bar(
            x=list(costs.keys()),
            y=list(costs.values()),
            marker_color=colors,
            text=[f"{v:.1f}" for v in costs.values()],
            textposition="outside",
        )
    )
    fig.update_layout(title="绿电直连方案成本对比")
    fig.update_yaxes(title="规划期成本 / 万元")
    return plot_layout(fig, height=380)


def integrated_electric_figure(dispatch: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    colors = {
        "P_PV": "#f59e0b",
        "P_WT": "#22c55e",
        "P_CHP": "#f97316",
        "P_grid_buy": "#2563eb",
        "P_BAT_dis": "#8b5cf6",
    }
    labels = {
        "P_PV": "光伏",
        "P_WT": "风电",
        "P_CHP": "热电联产发电",
        "P_grid_buy": "电网购电",
        "P_BAT_dis": "储能放电",
    }
    for column in labels:
        if column in dispatch:
            fig.add_trace(
                go.Scatter(
                    x=dispatch["hour"],
                    y=dispatch[column],
                    name=labels[column],
                    mode="lines",
                    stackgroup="electric_supply",
                    line=dict(width=1.5, color=colors[column]),
                )
            )
    consumption = dispatch.get("electric_load_adjusted", dispatch.get("electric_load", 0)).copy()
    for column in ("P_HP", "P_EC", "P_ELZ", "P_BAT_ch", "P_grid_sell"):
        if column in dispatch:
            consumption = consumption + dispatch[column]
    fig.add_trace(
        go.Scatter(
            x=dispatch["hour"],
            y=consumption,
            name="电力总需求",
            mode="lines",
            line=dict(width=3, color="#111827"),
        )
    )
    fig.update_layout(title="电力供需与转换用电")
    fig.update_xaxes(title="典型日时刻 / 小时")
    fig.update_yaxes(title="功率 / 兆瓦")
    return plot_layout(fig)


def integrated_heat_figure(dispatch: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    columns = {
        "H_CHP": ("热电联产供热", "#f97316"),
        "H_HP": ("热泵供热", "#0ea5e9"),
        "H_GB": ("燃气锅炉供热", "#64748b"),
        "H_H2": ("绿氢供热", "#10b981"),
        "H_TS_dis": ("蓄热放热", "#8b5cf6"),
    }
    for column, (label, color) in columns.items():
        if column in dispatch:
            fig.add_trace(
                go.Scatter(
                    x=dispatch["hour"], y=dispatch[column], name=label, mode="lines",
                    stackgroup="heat_supply", line=dict(width=1.5, color=color),
                )
            )
    heat_demand = dispatch.get("heat_load", 0).copy()
    if "H_TS_ch" in dispatch:
        heat_demand = heat_demand + dispatch["H_TS_ch"]
    fig.add_trace(
        go.Scatter(
            x=dispatch["hour"], y=heat_demand, name="热力总需求", mode="lines",
            line=dict(width=3, color="#111827"),
        )
    )
    fig.update_layout(title="热力供需与绿氢替代")
    fig.update_xaxes(title="典型日时刻 / 小时")
    fig.update_yaxes(title="热功率 / 兆瓦热")
    return plot_layout(fig)


def integrated_cooling_figure(dispatch: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if "C_EC_out" in dispatch:
        fig.add_trace(
            go.Scatter(
                x=dispatch["hour"], y=dispatch["C_EC_out"], name="电制冷供冷",
                fill="tozeroy", line=dict(width=2, color="#0ea5e9"),
            )
        )
    if "cooling_load" in dispatch:
        fig.add_trace(
            go.Scatter(
                x=dispatch["hour"], y=dispatch["cooling_load"], name="冷负荷",
                line=dict(width=3, color="#111827"),
            )
        )
    fig.update_layout(title="冷量供需")
    fig.update_xaxes(title="典型日时刻 / 小时")
    fig.update_yaxes(title="冷功率 / 兆瓦冷")
    return plot_layout(fig, height=380)


def integrated_storage_figure(dispatch: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if "SOC_BAT" in dispatch:
        fig.add_trace(
            go.Scatter(x=dispatch["hour"], y=dispatch["SOC_BAT"], name="电储能量", line=dict(width=3))
        )
    if "SOC_TS" in dispatch:
        fig.add_trace(
            go.Scatter(x=dispatch["hour"], y=dispatch["SOC_TS"], name="蓄热量", line=dict(width=3))
        )
    fig.update_layout(title="电/热储能状态")
    fig.update_xaxes(title="典型日时刻 / 小时")
    fig.update_yaxes(title="储能量 / 兆瓦时")
    return plot_layout(fig, height=380)


def integrated_capacity_figure(capacity: pd.DataFrame) -> go.Figure:
    data = localize_v17_table("capacity", capacity)
    if data.empty:
        return plot_layout(go.Figure(), height=380)
    data = data[pd.to_numeric(data["规划容量"], errors="coerce").fillna(0) > 1e-8].copy()
    fig = go.Figure(
        go.Bar(
            x=data["设备"],
            y=data["规划容量"],
            marker_color="#16a34a",
            text=data["规划容量"].round(2),
            textposition="outside",
        )
    )
    fig.update_layout(title="规划容量配置")
    fig.update_xaxes(title="设备")
    fig.update_yaxes(title="容量 / 兆瓦或兆瓦时")
    return plot_layout(fig, height=420)


def integrated_cost_figure(cost: pd.DataFrame) -> go.Figure:
    data = localize_v17_table("cost", cost)
    if data.empty:
        return plot_layout(go.Figure(), height=420)
    excluded = {"年度可变运行成本", "项目年度总成本", "社会年度总成本", "优化目标年度成本"}
    data = data[~data["成本项目"].isin(excluded)].copy()
    data.loc[data["成本项目"].eq("上网售电收入"), "数值"] *= -1.0
    data = data[pd.to_numeric(data["数值"], errors="coerce").abs() > 1e-8]
    colors = ["#16a34a" if value < 0 else "#2563eb" for value in data["数值"]]
    fig = go.Figure(
        go.Bar(
            x=data["数值"],
            y=data["成本项目"],
            orientation="h",
            marker_color=colors,
            text=data["数值"].round(1),
            textposition="outside",
        )
    )
    fig.update_layout(title="年度成本构成", showlegend=False)
    fig.update_xaxes(title="金额 / 万元每年")
    fig.update_yaxes(title="")
    return plot_layout(fig, height=520)


def integrated_energy_summary_figure(metrics: dict[str, Any]) -> go.Figure:
    labels = ["本地消纳新能源", "新能源外送", "电网购电", "新能源弃电"]
    values = [
        float(metrics.get("Annual renewable local absorption", 0) or 0),
        float(metrics.get("Annual renewable export", 0) or 0),
        float(metrics.get("Annual grid import", 0) or 0),
        float(metrics.get("Annual renewable curtailment", 0) or 0),
    ]
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=["#16a34a", "#0ea5e9", "#f59e0b", "#ef4444"],
            text=[f"{value:,.0f}" for value in values],
            textposition="outside",
        )
    )
    fig.update_layout(title="年度电量结构")
    fig.update_xaxes(title="")
    fig.update_yaxes(title="电量 / 兆瓦时每年")
    return plot_layout(fig, height=420)


def carbon_source_figure(source_breakdown: pd.DataFrame) -> go.Figure:
    fig = go.Figure(
        go.Bar(
            x=source_breakdown["排放来源"],
            y=source_breakdown["年度排放量/吨"],
            marker_color=["#2563eb", "#f59e0b", "#ef4444"],
            text=source_breakdown["年度排放量/吨"].round(1),
            textposition="outside",
        )
    )
    fig.update_layout(title="年度碳排放来源")
    fig.update_xaxes(title="")
    fig.update_yaxes(title="排放量 / 吨二氧化碳每年")
    return plot_layout(fig, height=420)


def carbon_target_figure(
    baseline: float | None,
    target: float | None,
    actual: float,
) -> go.Figure:
    labels = []
    values = []
    colors = []
    if baseline is not None:
        labels.append("S0基准排放")
        values.append(baseline)
        colors.append("#64748b")
    if target is not None:
        labels.append("当前减排目标")
        values.append(target)
        colors.append("#16a34a")
    labels.append("当前方案排放")
    values.append(actual)
    colors.append("#ef4444" if target is not None and actual > target else "#0ea5e9")
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[f"{value:,.0f}" for value in values],
            textposition="outside",
        )
    )
    fig.update_layout(title="基准、目标与当前排放")
    fig.update_xaxes(title="")
    fig.update_yaxes(title="排放量 / 吨二氧化碳每年")
    return plot_layout(fig, height=420)


def integrated_quality_checks(execution: ModelExecutionResult) -> pd.DataFrame:
    metrics = execution.metrics
    diagnostics = (execution.tables or {}).get("diagnostics", pd.DataFrame())
    diagnostic_values = (
        diagnostics.set_index("Diagnostic")["Value"].to_dict()
        if {"Diagnostic", "Value"}.issubset(diagnostics.columns)
        else {}
    )

    checks = [
        ("电力服务保障率", float(metrics.get("Electric service rate", 0) or 0), 99.9, ">=", "%"),
        ("供热服务保障率", float(metrics.get("Heat service rate", 0) or 0), 99.9, ">=", "%"),
        ("供冷服务保障率", float(metrics.get("Cooling service rate", 0) or 0), 99.9, ">=", "%"),
        ("未供能比例", float(metrics.get("Unserved energy ratio", 0) or 0), 0.1, "<=", "%"),
        (
            "最大电力平衡误差",
            abs(float(diagnostic_values.get("Maximum electric balance error", 0) or 0)),
            1e-6,
            "<=",
            "兆瓦",
        ),
        (
            "最大热力平衡误差",
            abs(float(diagnostic_values.get("Maximum heat balance error", 0) or 0)),
            1e-6,
            "<=",
            "兆瓦",
        ),
        (
            "最大冷量平衡误差",
            abs(float(diagnostic_values.get("Maximum cooling balance error", 0) or 0)),
            1e-6,
            "<=",
            "兆瓦",
        ),
        ("同时购售电量", float(metrics.get("Grid import-export overlap", 0) or 0), 1e-6, "<=", "兆瓦时/年"),
        ("电池同时充放电量", float(metrics.get("Battery simultaneous overlap", 0) or 0), 1e-6, "<=", "兆瓦时/年"),
        (
            "蓄热同时充放量",
            float(metrics.get("Thermal-storage simultaneous overlap", 0) or 0),
            1e-6,
            "<=",
            "兆瓦时/年",
        ),
    ]
    rows = []
    for name, actual, threshold, operator, unit in checks:
        passed = actual >= threshold if operator == ">=" else actual <= threshold
        rows.append(
            {
                "检查项目": name,
                "平台检查线": f"{operator} {threshold:g} {unit}",
                "计算结果": f"{actual:,.6g} {unit}",
                "状态": "通过" if passed else "需关注",
            }
        )
    return pd.DataFrame(rows)


def integrated_cost_reconciliation(execution: ModelExecutionResult) -> pd.DataFrame:
    metrics = execution.metrics
    capital = float(metrics.get("Annualized capital cost", 0) or 0)
    fixed = float(metrics.get("Fixed O&M cost", 0) or 0)
    variable = float(metrics.get("Variable operating annual cost", 0) or 0)
    private_total = float(metrics.get("Private total annual cost", 0) or 0)
    carbon = float(metrics.get("Carbon external cost", 0) or 0)
    social_total = float(metrics.get("Social total annual cost", 0) or 0)
    rows = [
        {
            "对账关系": "项目年度总成本 = 年化建设投资 + 固定运维 + 可变运行",
            "账面值/万元": private_total / 10_000.0,
            "分项合计/万元": (capital + fixed + variable) / 10_000.0,
            "差额/元": private_total - capital - fixed - variable,
        },
        {
            "对账关系": "社会年度总成本 = 项目年度总成本 + 碳排放成本",
            "账面值/万元": social_total / 10_000.0,
            "分项合计/万元": (private_total + carbon) / 10_000.0,
            "差额/元": social_total - private_total - carbon,
        },
    ]
    output = pd.DataFrame(rows)
    output["状态"] = output["差额/元"].abs().le(1e-4).map({True: "通过", False: "需核查"})
    return output


def scenario_cost_carbon_figure(table: pd.DataFrame) -> go.Figure:
    valid = table[table["是否成功"]].copy()
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=valid["场景"],
            y=valid["社会年度成本/万元"],
            name="社会年成本",
            marker_color="#2563eb",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=valid["场景"],
            y=valid["年度二氧化碳排放/吨"],
            name="年度碳排放",
            mode="lines+markers",
            line=dict(width=3, color="#ef4444"),
        ),
        secondary_y=True,
    )
    fig.update_layout(title="S0—S8成本与碳排放")
    fig.update_yaxes(title_text="社会年度成本 / 万元", secondary_y=False)
    fig.update_yaxes(title_text="年度二氧化碳排放 / 吨", secondary_y=True)
    return plot_layout(fig)


def abatement_frontier_figure(table: pd.DataFrame) -> go.Figure:
    valid = table[table["是否成功"]].copy()
    fig = go.Figure(
        go.Scatter(
            x=valid["年度二氧化碳排放/吨"],
            y=valid["社会年度成本/万元"],
            text=valid["场景"],
            mode="markers+text",
            textposition="top center",
            marker=dict(
                size=14,
                color=valid["相对S0减排率/%"],
                colorscale="Viridis",
                showscale=True,
                colorbar=dict(title="减排/%"),
            ),
        )
    )
    fig.update_layout(title="成本—碳排权衡前沿")
    fig.update_xaxes(title="年度二氧化碳排放 / 吨")
    fig.update_yaxes(title="社会年度成本 / 万元")
    return plot_layout(fig, height=420)


def render_result_cards(simulation: dict[str, Any]) -> None:
    metrics = metrics_dict(simulation)
    cols = st.columns(4)
    with cols[0]:
        metric_card("模拟期用电量", fmt(metrics.get("Total electricity demand [MWh]", 0)), "兆瓦时", "blue", "E")
    with cols[1]:
        metric_card("绿电占比", fmt(metrics.get("Renewable share [%]", 0)), "%", "green", "R")
    with cols[2]:
        metric_card("二氧化碳排放量", fmt(metrics.get("CO2 emissions [tCO2]", 0)), "吨", "orange", "C")
    with cols[3]:
        metric_card("综合成本", fmt(metrics.get("Total cost proxy [CNY]", 0) / 10_000.0), "万元", "purple", "¥")


def render_integrated_result_cards(execution: ModelExecutionResult) -> None:
    metrics = execution.metrics
    cols = st.columns(4)
    with cols[0]:
        metric_card("年度碳排放", fmt(metrics.get("Annual CO2 emissions", 0)), "吨", "orange", "C")
    with cols[1]:
        metric_card("年度电网购电", fmt(metrics.get("Annual grid import", 0)), "兆瓦时", "blue", "G")
    with cols[2]:
        metric_card("新能源弃电率", fmt(metrics.get("Renewable curtailment rate", 0)), "%", "green", "R")
    with cols[3]:
        metric_card("多能服务率", fmt(metrics.get("Total multi-energy service rate", 0)), "%", "purple", "S")


def sidebar() -> str:
    with st.sidebar:
        st.markdown(
            """
            <div class="brand-card">
              <div class="brand-logo">G</div>
              <div>
                <div class="brand-name">绿电向导</div>
                <div class="brand-subtitle">实时低碳规划与调度优化</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        selected_model_label = st.selectbox(
            "模型模式",
            options=list(MODEL_LABELS.values()),
            index=list(MODEL_LABELS).index(current_model_kind()),
            help="快速调度用于小时级电力运行；V17用于电、热、冷、气、储能、柔性负荷、碳与电转其他能源协同规划。",
        )
        st.session_state["model_kind"] = next(
            key for key, label in MODEL_LABELS.items() if label == selected_model_label
        )
        pages = list(
            INTEGRATED_PAGES
            if current_model_kind() == ModelKind.INTEGRATED_PLANNING.value
            else REALTIME_PAGES
        )
        platform_client = PlatformApiClient()
        if platform_client.configured and not platform_client.configuration_error:
            pages.append("项目中心")
        selected = st.radio("功能导航", pages, label_visibility="collapsed")
        if platform_client.configuration_error:
            st.caption("后台配置无效，项目中心已隐藏。")
        elif platform_client.configured:
            st.caption("项目中心已启用，可保存场景并提交后台任务。")
        else:
            st.caption("当前为单机演示模式；部署后台服务后自动显示项目中心。")
        st.divider()
        if current_model_kind() == ModelKind.INTEGRATED_PLANNING.value:
            execution = integrated_result()
            if execution is None:
                status_box("当前状态", "尚未完成综合能源规划，请先配置场景并运行模型。", ok=False)
            else:
                status_box(
                    "当前状态",
                    f"已完成场景：{execution.summary.get('scenario_name', execution.summary.get('scenario_key', '-'))}",
                    ok=True,
                )
        elif result() is None:
            status_box("当前状态", "尚未完成实时计算，请先配置参数并运行模型。", ok=False)
        else:
            inputs = input_dict()
            status_box(
                "当前状态",
                f"已完成场景：{inputs.get('scenario_name', '当前场景')}",
                ok=True,
            )
        mode_note = (
            "综合规划结果来自当前S0—S8场景和参数覆盖项。修改设备、储能、柔性负荷、碳或电转其他能源参数后需要重新运行。"
            if current_model_kind() == ModelKind.INTEGRATED_PLANNING.value
            else "图表和指标来自当前参数下的滚动线性优化结果。修改参数后需要重新运行。"
        )
        st.markdown(f'<div class="sidebar-note">{mode_note}</div>', unsafe_allow_html=True)
    return selected


def overview_page() -> None:
    page_title("园区低碳规划与绿电直连优化平台", "面向园区综合能源系统的参数建模、实时优化、指标分析与绿电直连决策支持。")
    badge(MODEL_LABELS[current_model_kind()])
    st.markdown(
        """
        <div class="overview-panel">
          <div class="overview-title">平台定位</div>
          <div class="overview-text">
            平台以综合能源系统线性规划和滚动调度为核心，将源荷预测、设备容量、储能约束、绿电占比、
            碳排约束、弃电约束和绿电直连成本测算组织成一个连续的工程流程。用户修改参数后重新运行模型，
            后续图表、指标和方案对比都会基于本次计算结果刷新。
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    simulation = result()
    planning = integrated_result()
    if current_model_kind() == ModelKind.INTEGRATED_PLANNING.value and planning is not None:
        section_label("当前综合规划结果")
        render_integrated_result_cards(planning)
    elif current_model_kind() == ModelKind.REALTIME_DISPATCH.value and simulation is not None:
        section_label("当前快速调度结果")
        render_result_cards(simulation)
    else:
        empty_hint("尚未运行当前模型", "进入“参数配置与运行”页面后，完成当前模型模式的参数配置和第一次计算。")

    section_label("业务流程")
    cols = st.columns(4)
    cards = [
        ("1 模型选型", "按业务目标选择快速电力调度或V17综合能源规划。"),
        ("2 系统配置", "配置设备、储能、柔性负荷、碳、绿电直连和电转其他能源参数。"),
        ("3 优化求解", "通过统一模型服务执行线性规划、滚动优化或综合规划。"),
        ("4 决策交付", "保存场景版本、比较指标并导出可追溯成果包。"),
    ]
    for col, (title, body) in zip(cols, cards):
        with col:
            st.markdown(f'<div class="feature-card"><b>{title}</b><span>{body}</span></div>', unsafe_allow_html=True)

    section_label("核心模型能力")
    pills(["双模型目录", "滚动时域调度", "电热冷气协同", "储能与柔性负荷", "碳约束", "绿电直连", "电转其他能源与绿氢"])


def project_task_page() -> None:
    page_title("项目中心", "保存版本化场景、提交后台优化任务，并查看可追溯的历史结果。")
    client = PlatformApiClient()
    if client.configuration_error:
        status_box("后台地址配置无效", client.configuration_error, ok=False)
        st.info("平台已停止调用错误地址；其他实时计算与结果页面仍可正常使用。")
        return
    if not client.configured:
        status_box("当前为单机演示模式", "实时优化、图表、指标和结果导出均可使用。", ok=True)
        st.info("项目版本、后台任务和历史结果需要连接平台后台服务后启用。")
        with st.expander("部署人员：查看后台连接配置"):
            st.code("PLATFORM_API_URL=http://127.0.0.1:8000", language="text")
        return

    try:
        health = client.health()
        status_box(
            "后台服务已连接",
            f"平台版本 {health.get('version', '未知')} · 已接入项目数据库与后台计算服务",
            ok=True,
        )
        st.caption("项目、场景版本、任务状态、结果摘要和成果校验信息均由后台持久化保存。")
        projects = client.list_projects()
    except ApiClientError as exc:
        status_box("后台服务不可用", str(exc), ok=False)
        return

    section_label("项目管理")
    with st.form("create_project_form"):
        c1, c2 = st.columns([1, 2])
        project_name = c1.text_input("项目名称", placeholder="例如：示范工业园区")
        project_description = c2.text_input("项目说明", placeholder="数据范围、目标或客户名称")
        create_project_clicked = st.form_submit_button("创建项目", type="primary")
    if create_project_clicked:
        try:
            client.create_project(project_name, project_description)
            st.success("项目已创建。")
            st.rerun()
        except ApiClientError as exc:
            st.error(str(exc))

    if not projects:
        empty_hint("暂无项目", "请先创建一个项目，再保存场景并提交优化任务。")
        return

    project_labels = {project["id"]: project["name"] for project in projects}
    project_id = st.selectbox(
        "当前项目",
        options=list(project_labels),
        format_func=lambda value: project_labels[value],
    )

    section_label("提交当前参数")
    model_kind = current_model_kind()
    if model_kind == ModelKind.INTEGRATED_PLANNING.value:
        scenario_payload = st.session_state.get("integrated_payload")
        if not isinstance(scenario_payload, dict):
            st.info("尚未运行综合规划，将使用S4默认配置创建后台任务。")
            scenario_payload = IntegratedPlanningConfig.from_scenario(
                "S4", get_integrated_scenario("S4")
            ).to_payload()
        default_scenario_name = str(scenario_payload.get("scenario_key", "S4"))
    else:
        current_inputs = input_dict()
        if not current_inputs:
            st.info("尚未运行当前会话参数，将使用默认实时场景参数创建后台任务。")
            default_input = build_inputs(
                "默认项目场景", 1_000_000.0, 25, 450.0, 350.0, 500.0,
                True, 35.0, False, 100_000.0, False, 20.0, True, False, 3, "CN",
            )
            current_inputs = asdict(default_input)
        scenario_payload = {
            "schema_version": "realtime-dispatch-v1",
            "model_kind": ModelKind.REALTIME_DISPATCH.value,
            "inputs": current_inputs,
            "generator_table": st.session_state["generator_table"].to_dict(orient="records"),
            "storage_table": st.session_state["storage_table"].to_dict(orient="records"),
            "fuel_table": st.session_state["fuel_table"].to_dict(orient="records"),
            "capex_table": st.session_state["capex_table"].to_dict(orient="records"),
        }
        default_scenario_name = str(current_inputs.get("scenario_name", "实时调度场景"))
    fingerprint = scenario_fingerprint(scenario_payload)
    st.caption(f"模型：{MODEL_LABELS[model_kind]} · 参数指纹：{fingerprint[:12]}")
    with st.form("submit_project_job_form"):
        scenario_name = st.text_input("场景版本名称", value=default_scenario_name)
        submit_job_clicked = st.form_submit_button("保存场景并提交后台计算", type="primary")
    if submit_job_clicked:
        try:
            scenario = client.create_scenario(project_id, scenario_name, scenario_payload)
            job = client.create_job(project_id, scenario["id"], model_kind=model_kind)
            st.success(f"任务已进入队列：{job['id']}")
            st.rerun()
        except ApiClientError as exc:
            st.error(str(exc))

    section_label("任务记录")
    try:
        jobs = client.list_jobs(project_id)
    except ApiClientError as exc:
        st.error(str(exc))
        return
    if not jobs:
        empty_hint("暂无任务", "保存当前参数并提交后台计算后，任务会显示在这里。")
        return
    job_table = pd.DataFrame(jobs)
    visible_columns = ["id", "status", "progress", "created_at", "started_at", "finished_at", "error_message"]
    display_jobs = job_table[[column for column in visible_columns if column in job_table]].copy()
    display_jobs["status"] = display_jobs["status"].map(
        {
            "queued": "排队中",
            "running": "计算中",
            "succeeded": "已完成",
            "failed": "失败",
            "cancelled": "已取消",
        }
    ).fillna(display_jobs["status"])
    display_jobs = display_jobs.rename(
        columns={
            "id": "任务编号",
            "status": "状态",
            "progress": "进度/%",
            "created_at": "创建时间",
            "started_at": "开始时间",
            "finished_at": "完成时间",
            "error_message": "错误说明",
        }
    )
    st.dataframe(display_jobs, hide_index=True, use_container_width=True)
    selected_job_id = st.selectbox("查看任务", options=[job["id"] for job in jobs])
    selected_job = next(job for job in jobs if job["id"] == selected_job_id)
    if selected_job["status"] in {"queued", "running"} and st.button("取消所选任务"):
        try:
            client.cancel_job(selected_job_id)
            st.rerun()
        except ApiClientError as exc:
            st.error(str(exc))
    if selected_job["status"] == "succeeded" and st.button("读取所选任务结果"):
        try:
            persisted_result = client.get_result(selected_job_id)
            st.success("历史计算结果已读取，摘要、指标和成果地址可继续追溯。")
            result_summary = persisted_result.get("summary", {})
            st.dataframe(
                pd.DataFrame(
                    {
                        "项目": ["结果编号", "成果位置", "成果校验值", "生成时间"],
                        "内容": [
                            persisted_result.get("id", "-"),
                            persisted_result.get("artifact_uri", "-"),
                            persisted_result.get("checksum_sha256", "-"),
                            persisted_result.get("created_at", "-"),
                        ],
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )
            with st.expander("查看工程追溯数据"):
                st.json({"计算摘要": result_summary, "指标": persisted_result.get("metrics", {})})
        except ApiClientError as exc:
            st.error(str(exc))


def integrated_parameter_run_page(*, embedded: bool = False) -> None:
    if not embedded:
        page_title(
            "综合能源系统配置与运行",
            "选择S0—S8场景，配置电、热、冷、储能、柔性负荷、碳、绿电直连和电转其他能源参数。",
        )
    else:
        section_label("V17综合能源规划参数")
    scenario_catalog = list_integrated_scenarios()
    scenario_labels = {item["key"]: item["name"] for item in scenario_catalog}
    scenario_key = st.selectbox(
        "规划场景模板",
        options=list(scenario_labels),
        index=4,
        format_func=lambda key: scenario_labels[key],
        help="模板定义技术组合与政策目标；页面中的参数会作为可追溯覆盖项写入场景版本。",
    )
    scenario_definition = get_integrated_scenario(scenario_key)
    base = IntegratedPlanningConfig.from_scenario(scenario_key, scenario_definition)
    st.info(str(scenario_definition.get("description", "")))

    key_prefix = f"v17_{scenario_key.lower()}"
    with st.form(f"integrated_configuration_{scenario_key}"):
        section_label("运行口径")
        c1, c2, c3 = st.columns(3)
        resolution = c1.selectbox(
            "时间分辨率",
            options=[1, 2, 4],
            index=[1, 2, 4].index(base.n_steps_per_hour),
            format_func=lambda value: {1: "60分钟", 2: "30分钟", 4: "15分钟"}[value],
            key=f"{key_prefix}_resolution",
        )
        seed = int(
            c2.number_input(
                "可复现随机种子",
                min_value=0,
                max_value=1_000_000,
                value=base.seed,
                step=1,
                key=f"{key_prefix}_seed",
            )
        )
        c3.text_input("参数模式", value="场景模板 + 页面覆盖项", disabled=True)

        equipment_tab, storage_tab, flexible_tab, carbon_tab, green_tab, p2x_tab = st.tabs(
            ["设备", "储能", "柔性负荷", "碳约束", "绿电直连", "电转其他能源与绿氢"]
        )
        with equipment_tab:
            st.caption("容量均为规划上限；0表示不允许新增该技术。")
            c1, c2, c3 = st.columns(3)
            max_pv = c1.number_input("光伏上限 / 兆瓦", 0.0, 2000.0, base.max_pv_capacity, 10.0)
            max_wt = c2.number_input("风电上限 / 兆瓦", 0.0, 2000.0, base.max_wt_capacity, 10.0)
            max_chp = c3.number_input("热电联产上限 / 兆瓦", 0.0, 1000.0, base.max_chp_capacity, 5.0)
            c4, c5, c6 = st.columns(3)
            max_hp = c4.number_input("热泵上限 / 兆瓦热", 0.0, 1000.0, base.max_hp_capacity, 5.0)
            max_ec = c5.number_input("电制冷上限 / 兆瓦冷", 0.0, 1000.0, base.max_ec_capacity, 5.0)
            max_gb = c6.number_input("燃气锅炉上限 / 兆瓦热", 0.0, 1000.0, base.max_gb_capacity, 5.0)

        with storage_tab:
            c1, c2 = st.columns(2)
            enable_battery = c1.checkbox("启用电化学储能", value=base.enable_battery)
            enable_thermal_storage = c2.checkbox("启用蓄热储能", value=base.enable_thermal_storage)
            c3, c4, c5, c6 = st.columns(4)
            battery_energy = c3.number_input(
                "电储能能量上限 / 兆瓦时", 0.0, 3000.0, base.max_battery_energy_capacity, 10.0,
                disabled=not enable_battery,
            )
            battery_power = c4.number_input(
                "电储能功率上限 / 兆瓦", 0.0, 1000.0, base.max_battery_power_capacity, 5.0,
                disabled=not enable_battery,
            )
            thermal_energy = c5.number_input(
                "蓄热能量上限 / 兆瓦时热", 0.0, 3000.0, base.max_thermal_storage_energy_capacity, 10.0,
                disabled=not enable_thermal_storage,
            )
            thermal_power = c6.number_input(
                "蓄热功率上限 / 兆瓦热", 0.0, 1000.0, base.max_thermal_storage_power_capacity, 5.0,
                disabled=not enable_thermal_storage,
            )

        with flexible_tab:
            c1, c2 = st.columns(2)
            enable_flexible = c1.checkbox("启用日内可转移负荷", value=base.enable_flexible_load)
            shift_ratio = c1.slider(
                "日内最大可转移电量 / %", 0.0, 30.0, 100.0 * base.max_daily_shift_energy_ratio, 1.0,
                disabled=not enable_flexible,
            )
            enable_interruptible = c2.checkbox("启用可中断负荷", value=base.enable_interruptible_load)
            interruptible_ratio = c2.slider(
                "最大可中断负荷比例 / %", 0.0, 20.0, 100.0 * base.interruptible_load_ratio, 0.5,
                disabled=not enable_interruptible,
            )

        with carbon_tab:
            c1, c2 = st.columns(2)
            enable_carbon = c1.checkbox("启用碳排放上限", value=base.enable_carbon_constraint)
            internalize_carbon = c2.checkbox("在目标函数中计入碳成本", value=base.internalize_carbon_price)
            c3, c4 = st.columns(2)
            carbon_cap_ratio = c3.slider(
                "相对S0基准碳排上限 / %", 1.0, 100.0, 100.0 * base.co2_cap_ratio_to_s0, 1.0,
                disabled=not enable_carbon,
            )
            carbon_price = c4.number_input(
                "碳市场价格 / 元每吨二氧化碳", 0.0, 2000.0, base.carbon_market_price_cny_per_tco2, 10.0,
            )

        with green_tab:
            c1, c2, c3 = st.columns(3)
            park_green_share = c1.slider(
                "园区最低绿电覆盖 / %", 0.0, 100.0,
                100.0 * base.min_industrial_park_green_electricity_share, 1.0,
            )
            green_direct_share = c2.slider(
                "绿电直连目标覆盖 / %", 0.0, 100.0, 100.0 * base.green_direct_target_share, 1.0,
            )
            renewable_utilization = c3.slider(
                "最低新能源利用率 / %", 0.0, 100.0, 100.0 * base.min_renewable_utilization_rate, 1.0,
            )

        with p2x_tab:
            enable_p2x = st.checkbox("启用电转其他能源与绿氢内生优化", value=base.enable_endogenous_p2x)
            c1, c2, c3 = st.columns(3)
            p2x_heat_share = c1.slider(
                "最低工艺热替代 / %", 0.0, 100.0,
                100.0 * base.p2x_min_process_heat_substitution_share, 1.0,
                disabled=not enable_p2x,
            )
            electrolyzer_capacity = c2.number_input(
                "电解槽容量上限 / 兆瓦", 0.0, 1000.0, base.max_electrolyzer_capacity, 5.0,
                disabled=not enable_p2x,
            )
            p2x_power_share = c3.slider(
                "电转其他能源最多使用新能源电量 / %", 0.0, 100.0,
                100.0 * base.max_p2x_electricity_share_of_renewable_generation, 1.0,
                disabled=not enable_p2x,
            )

        submit_integrated = st.form_submit_button("开始综合能源规划", type="primary", use_container_width=True)

    config = IntegratedPlanningConfig(
        scenario_key=scenario_key,
        n_steps_per_hour=int(resolution),
        seed=seed,
        max_pv_capacity=max_pv,
        max_wt_capacity=max_wt,
        max_chp_capacity=max_chp,
        max_hp_capacity=max_hp,
        max_ec_capacity=max_ec,
        max_gb_capacity=max_gb,
        enable_battery=enable_battery,
        enable_thermal_storage=enable_thermal_storage,
        max_battery_energy_capacity=battery_energy,
        max_battery_power_capacity=battery_power,
        max_thermal_storage_energy_capacity=thermal_energy,
        max_thermal_storage_power_capacity=thermal_power,
        enable_flexible_load=enable_flexible,
        max_daily_shift_energy_ratio=shift_ratio / 100.0,
        enable_interruptible_load=enable_interruptible,
        interruptible_load_ratio=interruptible_ratio / 100.0,
        enable_carbon_constraint=enable_carbon,
        internalize_carbon_price=internalize_carbon,
        co2_cap_ratio_to_s0=carbon_cap_ratio / 100.0,
        carbon_market_price_cny_per_tco2=carbon_price,
        min_industrial_park_green_electricity_share=park_green_share / 100.0,
        green_direct_target_share=green_direct_share / 100.0,
        min_renewable_utilization_rate=renewable_utilization / 100.0,
        enable_endogenous_p2x=enable_p2x,
        p2x_min_process_heat_substitution_share=p2x_heat_share / 100.0,
        max_electrolyzer_capacity=electrolyzer_capacity,
        max_p2x_electricity_share_of_renewable_generation=p2x_power_share / 100.0,
    )
    payload = config.to_payload()
    issues = config.validate()
    st.caption(f"参数结构：综合规划参数版本1 · 参数指纹：{scenario_fingerprint(payload)[:12]}")
    if issues:
        for issue in issues:
            st.error(f"{issue.field}：{issue.message}")
    if submit_integrated and not issues:
        with st.spinner("正在构建V17综合能源规划模型并求解..."):
            execution = UnifiedModelService().run(
                ModelExecutionRequest(ModelKind.INTEGRATED_PLANNING, payload)
            )
        st.session_state["integrated_result"] = execution
        st.session_state["integrated_payload"] = payload
        if execution.success:
            st.success("综合能源规划完成，结果已保存到当前会话，可继续提交后台任务。")
            render_integrated_result_cards(execution)
        else:
            st.error(execution.message)
    elif submit_integrated:
        st.warning("请先修正上述参数问题，再启动模型。")


def parameter_run_page() -> None:
    page_title(
        "参数配置与运行",
        "在一个页面内完成模型参数、源荷数据、质量校验、预测和优化运行。",
    )
    configuration_tab, data_tab = st.tabs(["模型参数与运行", "数据校验与预测"])
    with configuration_tab:
        if current_model_kind() == ModelKind.INTEGRATED_PLANNING.value:
            integrated_parameter_run_page(embedded=True)
        else:
            realtime_parameter_run_page(embedded=True)
    with data_tab:
        data_forecast_page(embedded=True)


def realtime_parameter_run_page(*, embedded: bool = False) -> None:
    if not embedded:
        page_title("参数配置与运行", "先建立园区系统边界，再运行实时优化，后续页面全部读取本次计算结果。")
    else:
        section_label("快速电力调度参数")

    with st.container():
        section_label("基础场景")
        c1, c2, c3, c4 = st.columns(4)
        scenario_name = c1.text_input("场景名称", value="默认园区实时场景")
        total_demand = c2.number_input("年用电需求 / 兆瓦时", min_value=10_000.0, max_value=10_000_000.0, value=1_000_000.0, step=50_000.0)
        service_life = c3.number_input("规划周期 / 年", min_value=1, max_value=50, value=25, step=1)
        rolling_days = c4.slider("滚动优化天数", min_value=1, max_value=14, value=3)

        c5, c6, c7, c8 = st.columns(4)
        import_price = c5.number_input("购电均价 / 元每兆瓦时", min_value=1.0, max_value=1500.0, value=450.0, step=10.0)
        export_price = c6.number_input("售电均价 / 元每兆瓦时", min_value=0.0, max_value=1500.0, value=350.0, step=10.0)
        import_export_capacity = c7.number_input("购售电容量上限 / 兆瓦", min_value=1.0, max_value=5000.0, value=500.0, step=20.0)
        country_code = c8.text_input("电价分布国家代码", value="CN")

    section_label("约束与运行策略")
    c1, c2, c3 = st.columns(3)
    with c1:
        rps_constraint = st.checkbox("启用绿电占比约束", value=True)
        min_res_share = st.slider("最低绿电占比 / %", 0.0, 95.0, 35.0, 1.0)
    with c2:
        co2_constraint = st.checkbox("启用二氧化碳排放约束", value=False)
        max_co2 = st.number_input("年度二氧化碳排放上限 / 吨", min_value=1000.0, max_value=5_000_000.0, value=100_000.0, step=10_000.0)
    with c3:
        ceep_constraint = st.checkbox("启用弃电率约束", value=False)
        max_ceep = st.slider("最大弃电率 / %", 0.0, 80.0, 20.0, 1.0)

    c4, c5 = st.columns(2)
    optimize_capacity = c4.checkbox("允许自动规划光伏、风电和储能增量", value=True)
    restrict_investments = c5.checkbox("限制新增投资规模", value=False)

    section_label("设备与价格参数")
    tab1, tab2, tab3, tab4 = st.tabs(["电源参数", "储能参数", "燃料价格", "投资成本"])
    with tab1:
        generator_df = st.data_editor(st.session_state["generator_table"], use_container_width=True, num_rows="fixed", key="editor_generator")
    with tab2:
        storage_df = st.data_editor(st.session_state["storage_table"], use_container_width=True, num_rows="fixed", key="editor_storage")
    with tab3:
        fuel_df = st.data_editor(st.session_state["fuel_table"], use_container_width=True, num_rows="fixed", key="editor_fuel")
    with tab4:
        capex_df = st.data_editor(st.session_state["capex_table"], use_container_width=True, num_rows="fixed", key="editor_capex")

    section_label("源荷时序数据")
    st.caption("可上传完整时序数据文件（CSV格式），也可以不上传，由平台根据总需求、典型日内曲线和随机扰动生成计算用数据。")
    template = csv_template(total_demand=total_demand, import_price=import_price, export_price=export_price)
    st.download_button(
        "下载8760小时数据模板",
        data=template.to_csv(index=False).encode("utf-8-sig"),
        file_name="profile_template.csv",
        mime="text/csv",
    )
    uploaded_csv = st.file_uploader("上传源荷或电价数据文件（CSV格式）", type=["csv"])

    section_label("开始优化")
    inputs = build_inputs(
        scenario_name=scenario_name,
        total_demand=total_demand,
        service_life=int(service_life),
        import_price=import_price,
        export_price=export_price,
        import_export_capacity=import_export_capacity,
        rps_constraint=rps_constraint,
        min_res_share=min_res_share,
        co2_constraint=co2_constraint,
        max_co2=max_co2,
        ceep_constraint=ceep_constraint,
        max_ceep=max_ceep,
        optimize_capacity=optimize_capacity,
        restrict_investments=restrict_investments,
        rolling_days=int(rolling_days),
        country_code=country_code.strip() or "CN",
    )
    if st.button("开始实时优化调度", type="primary", use_container_width=True):
        with st.spinner("正在构建线性规划模型并滚动求解..."):
            simulation = run_scenario(inputs, generator_df, storage_df, fuel_df, capex_df, uploaded_csv)
        if simulation.get("success"):
            st.success("模型计算完成，结果已同步到后续页面。")
            render_result_cards(simulation)
        else:
            st.error(f"模型计算失败：{simulation.get('message')}")
            st.info("可以适当放宽绿电占比、二氧化碳排放上限或弃电率约束，也可以提高购售电容量上限后重新运行。")


def data_forecast_page(*, embedded: bool = False) -> None:
    if not embedded:
        page_title("15分钟数据与预测", "校验源荷与价格数据，比较预测基准，生成日前96点预测和日内滚动请求。")
    else:
        section_label("15分钟数据质量与预测")
        st.caption("该区域用于上传真实源荷与价格数据、检查质量并生成日前和日内预测。")
    sample = sample_15min_data(days=14, seed=42)
    c1, c2 = st.columns([1, 2])
    with c1:
        st.download_button(
            "下载15分钟数据模板",
            data=sample.head(96).to_csv(index=False).encode("utf-8-sig"),
            file_name="15min_data_template.csv",
            mime="text/csv",
            use_container_width=True,
        )
        load_sample = st.button("加载14天示例数据并检查", use_container_width=True)
    with c2:
        uploaded = st.file_uploader(
            "上传15分钟数据文件（CSV格式）",
            type=["csv"],
            help="必填列：timestamp、electric_load_mw、pv_available_mw、wind_available_mw、electricity_price_cny_per_mwh。",
        )

    source = None
    if load_sample:
        source = sample
    elif uploaded is not None:
        try:
            source = pd.read_csv(uploaded)
        except (ValueError, pd.errors.ParserError, UnicodeDecodeError) as exc:
            st.error(f"数据文件读取失败：{exc}")
    if source is not None:
        st.session_state["timeseries_validation"] = FifteenMinuteDataContract().validate(source)
        st.session_state["forecast_evaluation"] = None
        st.session_state["day_ahead_forecast"] = None
        st.session_state["intraday_plan"] = None

    validation = st.session_state.get("timeseries_validation")
    if not isinstance(validation, TimeSeriesValidationResult):
        empty_hint("尚未加载15分钟数据", "可上传数据文件，或使用示例数据完成数据质量和预测流程演示。")
        return

    summary = validation.summary
    cols = st.columns(4)
    with cols[0]:
        metric_card("数据点", str(summary["rows"]), "条", "blue", "N")
    with cols[1]:
        metric_card("时间间隔", str(summary["frequency_minutes"]), "分钟", "green", "T")
    with cols[2]:
        metric_card("错误", str(summary["error_count"]), "项", "orange", "E")
    with cols[3]:
        metric_card("质量状态", "通过" if validation.valid else "未通过", "", "purple", "Q")
    if validation.issues:
        section_label("数据质量问题")
        issue_view = validation.issues_frame().rename(
            columns={
                "code": "问题代码",
                "severity": "级别",
                "field": "字段",
                "row": "文件行号",
                "timestamp": "时间戳",
                "message": "说明",
            }
        )
        issue_view["级别"] = issue_view["级别"].replace({"error": "错误", "warning": "提示"})
        st.dataframe(issue_view, use_container_width=True, hide_index=True)
    if not validation.valid:
        st.warning("必须修正全部错误后才能进入预测和滚动运行。错误已定位到字段、文件行号和时间戳。")
        return

    data = validation.data
    section_label("数据预览")
    preview = data.head(7 * 96)
    fig = go.Figure()
    for column, label, color in (
        ("electric_load_mw", "电负荷", "#111827"),
        ("pv_available_mw", "光伏可用", "#f59e0b"),
        ("wind_available_mw", "风电可用", "#22c55e"),
    ):
        fig.add_trace(go.Scatter(x=preview["timestamp"], y=preview[column], name=label, line=dict(color=color)))
    fig.update_layout(title="前7天源荷数据")
    fig.update_yaxes(title="功率 / 兆瓦")
    st.plotly_chart(plot_layout(fig, height=380), use_container_width=True)

    if st.button("评估基准并生成日前96点预测", type="primary", use_container_width=True):
        try:
            service = ForecastService()
            evaluation = service.evaluate_baselines(data, validation_points=7 * 96)
            forecast = service.day_ahead(data, evaluation)
            st.session_state["forecast_evaluation"] = evaluation
            st.session_state["day_ahead_forecast"] = forecast
            st.session_state["intraday_plan"] = None
        except ValueError as exc:
            st.error(str(exc))

    evaluation = st.session_state.get("forecast_evaluation")
    forecast = st.session_state.get("day_ahead_forecast")
    if evaluation is None or forecast is None:
        return
    section_label("预测基准评估")
    model_labels = {"seasonal_naive": "同一时刻历史值", "recent_mean": "最近一天均值"}
    evaluation_view = evaluation.metrics.rename(
        columns={
            "model": "预测方法",
            "MAE": "平均绝对误差",
            "RMSE": "均方根误差",
            "sMAPE [%]": "对称平均绝对百分比误差/%",
            "validation_points": "验证点数",
        }
    ).copy()
    evaluation_view["预测方法"] = evaluation_view["预测方法"].replace(model_labels)
    st.dataframe(evaluation_view, use_container_width=True, hide_index=True)
    st.info(
        f"按验证集平均绝对误差自动选择“{model_labels.get(evaluation.best_model, evaluation.best_model)}”。训练截止 {evaluation.training_end}，"
        f"验证区间 {evaluation.validation_start} 至 {evaluation.validation_end}。"
    )
    history = data[["timestamp", "electric_load_mw"]].tail(96)
    forecast_column = f"forecast_{forecast.target}"
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=history["timestamp"], y=history["electric_load_mw"], name="最近实际负荷", line=dict(width=2))
    )
    fig.add_trace(
        go.Scatter(
            x=forecast.data["timestamp"], y=forecast.data[forecast_column], name="日前预测负荷",
            line=dict(width=3, dash="dash", color="#ef4444"),
        )
    )
    fig.update_layout(title="日前96点负荷预测")
    fig.update_yaxes(title="电负荷 / 兆瓦")
    st.plotly_chart(plot_layout(fig, height=380), use_container_width=True)
    st.caption(f"预测版本：{forecast.version_id} · 算法：{model_labels.get(forecast.model_name, forecast.model_name)}")
    st.download_button(
        "下载日前96点预测",
        data=forecast.data.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{forecast.version_id}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    section_label("日内15分钟滚动请求")
    with st.form("intraday_plan_form"):
        c1, c2, c3, c4 = st.columns(4)
        operation_scenario = c1.selectbox("运行场景", ["R0", "R1", "R2", "R3", "R4"], index=4)
        horizon = int(c2.number_input("滚动窗口 / 15分钟点", 1, 96, 16, 1))
        battery_soc = c3.slider("最新电储能荷电状态 / %", 0.0, 100.0, 50.0, 1.0)
        thermal_soc = c4.slider("最新蓄热储能状态 / %", 0.0, 100.0, 50.0, 1.0)
        build_plan = st.form_submit_button("生成日内滚动请求", use_container_width=True)
    if build_plan:
        try:
            plan = IntradayRollingService().build_plan(
                IntradayRollingRequest(
                    forecast=forecast,
                    scenario_key=operation_scenario,
                    horizon_intervals=horizon,
                    battery_soc_fraction=battery_soc / 100.0,
                    thermal_soc_fraction=thermal_soc / 100.0,
                )
            )
            st.session_state["intraday_plan"] = plan
        except ValueError as exc:
            st.error(str(exc))
    plan = st.session_state.get("intraday_plan")
    if plan is not None:
        st.success(
            f"已生成请求 {plan.run_id}，继承预测版本 {plan.forecast_version} 和最新电、热储能状态。"
        )
        st.json(
            {
                "请求编号": plan.run_id,
                "运行场景": plan.scenario_key,
                "时间间隔（分钟）": plan.interval_minutes,
                "滚动点数": plan.horizon_intervals,
                "预测版本": plan.forecast_version,
                "继承状态": plan.inherited_state,
            }
        )
        st.download_button(
            "下载日内滚动请求文件",
            data=json.dumps(plan.model_payload, ensure_ascii=False, indent=2, default=str),
            file_name=f"{plan.run_id}.json",
            mime="application/json",
            use_container_width=True,
        )


def integrated_analysis_page() -> None:
    page_title(
        "V17综合能源运行分析",
        "从容量、电量、成本、多能协同、可靠性和约束执行六个角度解释本次规划结果。",
    )
    execution = require_integrated_result()
    if execution is None:
        return
    tables = execution.tables or {}
    metrics = execution.metrics

    st.download_button(
        "下载本次规划成果包",
        data=execution.artifact_bytes or b"",
        file_name=f"V17综合能源规划_{execution.summary.get('scenario_key', '场景')}.zip",
        mime="application/zip",
        type="primary",
    )

    first_row = st.columns(4)
    with first_row[0]:
        metric_card(
            "社会年度总成本",
            fmt(float(metrics.get("Social total annual cost", 0) or 0) / 10_000.0),
            "万元/年",
            "purple",
            "¥",
        )
    with first_row[1]:
        metric_card("年度二氧化碳排放", fmt(metrics.get("Annual CO2 emissions", 0)), "吨/年", "orange", "C")
    with first_row[2]:
        metric_card(
            "本地绿电覆盖率",
            fmt(metrics.get("Renewable local share of electric-service demand", 0)),
            "%",
            "green",
            "R",
        )
    with first_row[3]:
        metric_card(
            "新能源综合利用率",
            fmt(metrics.get("Renewable utilization rate (including export)", 0)),
            "%",
            "green",
            "U",
        )

    second_row = st.columns(4)
    with second_row[0]:
        metric_card("多能服务保障率", fmt(metrics.get("Total multi-energy service rate", 0)), "%", "blue", "S")
    with second_row[1]:
        metric_card(
            "外购电占比",
            fmt(metrics.get("Grid import share of electric-service demand", 0)),
            "%",
            "blue",
            "G",
        )
    with second_row[2]:
        carbon_intensity = float(metrics.get("System carbon intensity per electric-service demand", 0) or 0)
        metric_card("电力服务碳强度", fmt(carbon_intensity * 1000.0), "千克/兆瓦时", "orange", "I")
    with second_row[3]:
        solver_status = execution.summary.get("solver_status", "-")
        metric_card("求解状态", str(solver_status), "", "purple", "✓")

    dashboard_tab, operation_tab, economy_tab, carbon_tab, reliability_tab, detail_tab = st.tabs(
        ["综合看板", "多能运行", "经济性", "低碳分析", "可靠性与约束", "数据明细"]
    )

    with dashboard_tab:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(
                integrated_capacity_figure(tables.get("capacity", pd.DataFrame())),
                use_container_width=True,
            )
        with c2:
            st.plotly_chart(integrated_energy_summary_figure(metrics), use_container_width=True)
        section_label("成本对账")
        st.dataframe(integrated_cost_reconciliation(execution), use_container_width=True, hide_index=True)

    with operation_tab:
        dispatch = tables.get("dispatch", pd.DataFrame())
        if dispatch.empty or "day_id" not in dispatch:
            empty_hint("暂无多能调度数据", "重新运行V17模型后查看典型日多能流。")
        else:
            day_ids = dispatch["day_id"].drop_duplicates().tolist()
            day_labels = {}
            for day_id in day_ids:
                day_rows = dispatch[dispatch["day_id"] == day_id]
                day_name = str(day_rows.iloc[0].get("day_name", day_id))
                day_labels[day_id] = f"{day_name}（代表 {float(day_rows.iloc[0].get('day_weight', 1)):.0f} 天）"
            selected_day = st.selectbox(
                "选择典型日",
                options=day_ids,
                format_func=lambda value: day_labels[value],
                key="v17_analysis_day",
            )
            selected_dispatch = dispatch[dispatch["day_id"] == selected_day].sort_values("hour")
            st.plotly_chart(integrated_electric_figure(selected_dispatch), use_container_width=True)
            st.plotly_chart(integrated_heat_figure(selected_dispatch), use_container_width=True)
            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(integrated_cooling_figure(selected_dispatch), use_container_width=True)
            with c2:
                st.plotly_chart(integrated_storage_figure(selected_dispatch), use_container_width=True)
            with st.expander("查看所选典型日调度明细"):
                st.dataframe(
                    localize_v17_table("dispatch", selected_dispatch),
                    use_container_width=True,
                    hide_index=True,
                )

    with economy_tab:
        st.plotly_chart(integrated_cost_figure(tables.get("cost", pd.DataFrame())), use_container_width=True)
        st.dataframe(
            localize_v17_table("cost", tables.get("cost", pd.DataFrame())),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("绿色柱为售电收入抵扣，其余为年度成本；所有金额均按人民币口径展示。")

    with carbon_tab:
        scenario_key = str(execution.summary.get("scenario_key", "S4"))
        scenario = get_integrated_scenario(scenario_key)
        payload = st.session_state.get("integrated_payload")
        if isinstance(payload, dict):
            scenario.update(payload.get("overrides", {}))
        comparison_result = scenario_comparison_result()
        comparison_table = comparison_result.table if comparison_result is not None else None
        carbon_analysis = CarbonAnalysisService().analyze(
            metrics=metrics,
            dispatch=tables.get("dispatch", pd.DataFrame()),
            scenario=scenario,
            scenario_key=scenario_key,
            comparison=comparison_table,
            time_step_hours=float(execution.summary.get("time_step_hours", 1.0) or 1.0),
            baseline_emissions_tco2=execution.summary.get("carbon_baseline_tco2_per_year"),
            target_emissions_tco2=execution.summary.get("carbon_target_tco2_per_year"),
        )

        cards = st.columns(4)
        with cards[0]:
            metric_card(
                "运营期核算排放",
                fmt(carbon_analysis.annual_emissions_tco2),
                "吨/年",
                "orange",
                "C",
            )
        with cards[1]:
            metric_card(
                "电力服务碳强度",
                fmt(carbon_analysis.carbon_intensity_kg_per_mwh),
                "千克/兆瓦时",
                "orange",
                "I",
            )
        with cards[2]:
            metric_card(
                "年度碳排放成本",
                fmt(carbon_analysis.annual_carbon_cost_cny / 10_000.0),
                "万元/年",
                "purple",
                "¥",
            )
        with cards[3]:
            gap = carbon_analysis.target_gap_tco2
            metric_card(
                "减排目标差距",
                fmt(gap) if gap is not None else "待建立基准",
                "吨/年" if gap is not None else "",
                "green" if gap is not None and gap <= 0 else "orange",
                "T",
            )

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(carbon_source_figure(carbon_analysis.source_breakdown), use_container_width=True)
        with c2:
            st.plotly_chart(
                carbon_target_figure(
                    carbon_analysis.baseline_emissions_tco2,
                    carbon_analysis.target_emissions_tco2,
                    carbon_analysis.annual_emissions_tco2,
                ),
                use_container_width=True,
            )

        if carbon_analysis.baseline_emissions_tco2 is None:
            st.info("运行“场景与决策”中的S0基准场景对比后，可显示相对基准减排量、减排率和平均减排成本。")
        else:
            comparison_cards = st.columns(3)
            with comparison_cards[0]:
                metric_card(
                    "相对S0减排量",
                    fmt(carbon_analysis.reduction_vs_baseline_tco2),
                    "吨/年",
                    "green",
                    "R",
                )
            with comparison_cards[1]:
                metric_card(
                    "相对S0减排率",
                    fmt(carbon_analysis.reduction_vs_baseline_percent),
                    "%",
                    "green",
                    "P",
                )
            with comparison_cards[2]:
                metric_card(
                    "平均减排成本",
                    fmt(carbon_analysis.average_abatement_cost_cny_per_tco2),
                    "元/吨",
                    "purple",
                    "A",
                )

        section_label("碳排放核算表")
        st.dataframe(carbon_analysis.accounting, use_container_width=True, hide_index=True)
        source_total = float(carbon_analysis.source_breakdown["年度排放量/吨"].sum())
        reconciliation_error = source_total - carbon_analysis.annual_emissions_tco2
        if abs(reconciliation_error) <= 1e-4:
            st.success("购电、热电联产和燃气锅炉三类排放来源与年度总排放对账通过。")
        else:
            st.warning(f"排放来源与年度总排放存在{reconciliation_error:,.4f}吨差额，需要核查时间权重或排放因子。")

        section_label("核算边界与因子")
        st.dataframe(carbon_analysis.boundary, use_container_width=True, hide_index=True)
        st.dataframe(carbon_analysis.source_breakdown, use_container_width=True, hide_index=True)
        st.caption(
            "当前使用场景参数中的购电和燃气排放因子。正式项目应记录因子发布机构、适用地区、发布年份和版本，"
            "并与企业碳盘查边界保持一致。"
        )

    with reliability_tab:
        checks = integrated_quality_checks(execution)
        attention_count = int(checks["状态"].eq("需关注").sum())
        if attention_count:
            st.warning(f"发现{attention_count}项需要关注的运行或物理一致性指标。")
        else:
            st.success("供能保障、能量平衡和互斥运行检查全部通过。")
        st.dataframe(checks, use_container_width=True, hide_index=True)
        scenario_key = str(execution.summary.get("scenario_key", "S4"))
        audit_scenario = get_integrated_scenario(scenario_key)
        audit_payload = st.session_state.get("integrated_payload")
        if isinstance(audit_payload, dict):
            audit_scenario.update(audit_payload.get("overrides", {}))
        audit = ModelAuditService().analyze(
            metrics=metrics,
            tables=tables,
            scenario=audit_scenario,
        )
        section_label("模型可信度审计")
        if audit.review_count:
            st.warning(f"审计结论：{audit.overall_status}，有{audit.review_count}项必须复核。")
        else:
            st.success(f"审计结论：{audit.overall_status}；{audit.notice_count}项提示已明确披露。")
        st.dataframe(audit.checks, use_container_width=True, hide_index=True)
        st.caption("合理范围只用于发现数量级和口径异常，不构成设备报价、可研估算或政策合规承诺。")
        section_label("求解与约束诊断")
        st.dataframe(
            localize_v17_table("diagnostics", tables.get("diagnostics", pd.DataFrame())),
            use_container_width=True,
            hide_index=True,
        )

    with detail_tab:
        capacity_tab, metrics_tab, dispatch_tab = st.tabs(["容量配置", "全部指标", "完整调度数据"])
        with capacity_tab:
            st.dataframe(
                localize_v17_table("capacity", tables.get("capacity", pd.DataFrame())),
                use_container_width=True,
                hide_index=True,
            )
        with metrics_tab:
            st.dataframe(
                localize_v17_table("metrics", tables.get("metrics", pd.DataFrame())),
                use_container_width=True,
                hide_index=True,
            )
        with dispatch_tab:
            st.dataframe(
                localize_v17_table("dispatch", tables.get("dispatch", pd.DataFrame())),
                use_container_width=True,
                hide_index=True,
            )


def realtime_results_page() -> None:
    if current_model_kind() == ModelKind.INTEGRATED_PLANNING.value:
        page_title("综合能源规划结果", "查看当前V17场景的容量配置和多能协同调度明细。")
        execution = require_integrated_result()
        if execution is None:
            return
        st.download_button(
            "下载本次规划成果包",
            data=execution.artifact_bytes or b"",
            file_name=f"V17综合能源规划_{execution.summary.get('scenario_key', '场景')}.zip",
            mime="application/zip",
            type="primary",
        )
        render_integrated_result_cards(execution)
        tables = execution.tables or {}
        dispatch = tables.get("dispatch", pd.DataFrame())
        if not dispatch.empty and "day_id" in dispatch:
            day_ids = dispatch["day_id"].drop_duplicates().tolist()
            day_labels = {}
            for day_id in day_ids:
                day_rows = dispatch[dispatch["day_id"] == day_id]
                day_name = str(day_rows.iloc[0].get("day_name", day_rows.iloc[0].get("day_type", day_id)))
                day_labels[day_id] = f"{day_name}（权重 {float(day_rows.iloc[0].get('day_weight', 1)):.0f} 天）"
            selected_day = st.selectbox(
                "选择典型日",
                options=day_ids,
                format_func=lambda value: day_labels[value],
            )
            selected_dispatch = dispatch[dispatch["day_id"] == selected_day].sort_values("hour")
            section_label("多能流平衡")
            st.plotly_chart(integrated_electric_figure(selected_dispatch), use_container_width=True)
            st.plotly_chart(integrated_heat_figure(selected_dispatch), use_container_width=True)
            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(integrated_cooling_figure(selected_dispatch), use_container_width=True)
            with c2:
                st.plotly_chart(integrated_storage_figure(selected_dispatch), use_container_width=True)

        section_label("结果明细")
        capacity_tab, dispatch_tab, cost_tab, carbon_tab, diagnostic_tab = st.tabs(
            ["容量", "多能调度", "成本", "碳排", "诊断"]
        )
        with capacity_tab:
            st.dataframe(
                localize_v17_table("capacity", tables.get("capacity", pd.DataFrame())),
                use_container_width=True,
                hide_index=True,
            )
        with dispatch_tab:
            st.dataframe(
                localize_v17_table("dispatch", tables.get("dispatch", pd.DataFrame())),
                use_container_width=True,
                hide_index=True,
            )
        with cost_tab:
            st.dataframe(
                localize_v17_table("cost", tables.get("cost", pd.DataFrame())),
                use_container_width=True,
                hide_index=True,
            )
        with carbon_tab:
            st.dataframe(
                localize_v17_table("carbon", tables.get("carbon", pd.DataFrame())),
                use_container_width=True,
                hide_index=True,
            )
        with diagnostic_tab:
            st.dataframe(
                localize_v17_table("diagnostics", tables.get("diagnostics", pd.DataFrame())),
                use_container_width=True,
                hide_index=True,
            )
        return
    page_title("实时结果图", "所有图表均由当前场景实时计算得到，并随参数变化同步刷新。")
    simulation = require_result()
    if simulation is None:
        return
    zip_buffer = simulation["zip"]
    zip_buffer.seek(0)
    st.download_button(
        "下载本次调度成果包",
        data=zip_buffer.getvalue(),
        file_name="快速电力调度成果.zip",
        mime="application/zip",
        type="primary",
    )
    dispatch = simulation["dispatch"]
    render_result_cards(simulation)

    section_label("电力调度")
    st.plotly_chart(generation_figure(dispatch), use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(storage_figure(dispatch), use_container_width=True)
    with c2:
        st.plotly_chart(balance_figure(dispatch), use_container_width=True)

    section_label("购售电响应")
    st.plotly_chart(price_dispatch_figure(dispatch), use_container_width=True)

    with st.expander("查看本次调度明细"):
        st.dataframe(dispatch, use_container_width=True)
    realtime_indicator_section(simulation)


def realtime_indicator_section(simulation: dict[str, Any]) -> None:
    metrics = metrics_dict(simulation)
    inputs = input_dict()

    section_label("经济、低碳与约束综合指标")
    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.plotly_chart(metrics_bar_figure(metrics), use_container_width=True)
    with c2:
        st.dataframe(simulation["metrics"], use_container_width=True, hide_index=True)

    section_label("约束执行检查")
    rolling_days = float(inputs.get("rolling_days", 1) or 1)
    horizon_ratio = rolling_days * 24 / 8760
    checks = []
    if inputs.get("rps_constraint"):
        checks.append(
            {
                "约束": "绿电占比",
                "目标": f">= {inputs.get('min_res_share', 0):.1f}%",
                "结果": f"{metrics.get('Renewable share [%]', 0):.1f}%",
                "状态": "满足" if metrics.get("Renewable share [%]", 0) + 1e-6 >= float(inputs.get("min_res_share", 0)) else "不满足",
            }
        )
    if inputs.get("co2_constraint"):
        limit = float(inputs.get("max_co2", 0)) * horizon_ratio
        checks.append(
            {
                "约束": "二氧化碳排放",
                "目标": f"不超过 {limit:.1f} 吨",
                "结果": f"{metrics.get('CO2 emissions [tCO2]', 0):.1f} 吨",
                "状态": "满足" if metrics.get("CO2 emissions [tCO2]", 0) <= limit + 1e-6 else "不满足",
            }
        )
    if inputs.get("ceep_constraint"):
        checks.append(
            {
                "约束": "弃电率",
                "目标": f"<= {inputs.get('max_ceep', 0):.1f}%",
                "结果": f"{metrics.get('CEEP share [%]', 0):.1f}%",
                "状态": "满足" if metrics.get("CEEP share [%]", 0) <= float(inputs.get("max_ceep", 0)) + 1e-6 else "不满足",
            }
        )
    if not checks:
        empty_hint("未启用额外约束", "当前场景只执行功率平衡、设备容量、储能荷电状态和购售电容量等基础约束。")
    else:
        st.dataframe(pd.DataFrame(checks), use_container_width=True, hide_index=True)

    section_label("滚动优化状态")
    st.plotly_chart(rolling_figure(simulation["rolling_log"]), use_container_width=True)
    st.dataframe(simulation["rolling_log"], use_container_width=True, hide_index=True)

    section_label("容量规划结果")
    st.dataframe(simulation["investment"], use_container_width=True, hide_index=True)


def scenario_comparison_page(*, embedded: bool = False) -> None:
    if not embedded:
        page_title("S0—S8场景对比", "逐场景调用V17模型，比较成本、碳排、新能源、可靠性与减排成本。")
    else:
        section_label("S0—S8场景对比")
    if current_model_kind() != ModelKind.INTEGRATED_PLANNING.value:
        st.info("请先在侧栏将模型模式切换为“V17综合能源规划”。")
        return
    catalog = list_integrated_scenarios()
    labels = {item["key"]: item["name"] for item in catalog}
    selected_keys = st.multiselect(
        "参与比较的场景",
        options=list(labels),
        default=list(labels),
        format_func=lambda key: labels[key],
    )
    c1, c2 = st.columns(2)
    n_steps_per_hour = c1.selectbox(
        "比较分辨率",
        options=[1, 2, 4],
        format_func=lambda value: {1: "60分钟（推荐演示）", 2: "30分钟", 4: "15分钟"}[value],
    )
    seed = int(c2.number_input("统一随机种子", 0, 1_000_000, 42, 1))
    if n_steps_per_hour > 1:
        st.warning("更高时间分辨率会显著增加S0—S8批量求解时间；演示时建议使用60分钟。")
    if st.button("运行真实场景对比", type="primary", use_container_width=True):
        try:
            with st.spinner(f"正在依次求解{len(selected_keys)}个场景并打包原始结果..."):
                comparison = ScenarioComparisonService().run(
                    selected_keys,
                    n_steps_per_hour=int(n_steps_per_hour),
                    seed=seed,
                )
            st.session_state["scenario_comparison_result"] = comparison
        except ValueError as exc:
            st.error(str(exc))

    comparison = scenario_comparison_result()
    if comparison is None:
        empty_hint("尚未运行场景对比", "点击“运行真实场景对比”后，平台将逐一调用模型，不使用静态演示数据。")
        return
    table = comparison.table
    valid = table[table["是否成功"]] if not table.empty else pd.DataFrame()
    if valid.empty:
        st.error("本次比较没有成功场景，请查看错误信息。")
    else:
        cheapest = valid.loc[valid["社会年度成本/万元"].idxmin()]
        lowest_carbon = valid.loc[valid["年度二氧化碳排放/吨"].idxmin()]
        highest_reduction = valid.loc[valid["相对S0减排率/%"].idxmax()]
        cols = st.columns(4)
        with cols[0]:
            metric_card("已完成场景", str(len(valid)), "个", "blue", "N")
        with cols[1]:
            metric_card("最低成本场景", str(cheapest["场景"]), "", "green", "¥")
        with cols[2]:
            metric_card("最低碳场景", str(lowest_carbon["场景"]), "", "orange", "C")
        with cols[3]:
            metric_card("最大减排场景", str(highest_reduction["场景"]), "", "purple", "R")
        st.plotly_chart(scenario_cost_carbon_figure(table), use_container_width=True)
        st.plotly_chart(abatement_frontier_figure(table), use_container_width=True)

    section_label("场景指标明细")
    st.dataframe(table, use_container_width=True, hide_index=True)
    indistinguishable = (
        table[table["场景差异状态"].eq("新增约束未改变核心结果")]
        if "场景差异状态" in table
        else pd.DataFrame()
    )
    if not indistinguishable.empty:
        groups = indistinguishable["场景"].astype(str).tolist()
        st.warning(
            f"场景{'、'.join(groups)}的核心结果存在重复。平台已标注为“新增约束未改变核心结果”；"
            "演示时应说明约束未起作用，不能把重复结果解释为新增功能带来的额外效益。"
        )
    if "平均减排成本/元每吨" in table and (table["平均减排成本/元每吨"] < 0).any():
        st.info(
            "负的平均减排成本表示：在当前价格、造价和典型日假设下，模型同时得到成本节约和减排；"
            "这是方案筛查结果，不是收益承诺，正式项目需用实测负荷、合同电价和设备报价复算。"
        )
    if comparison.errors:
        st.warning(f"失败场景：{comparison.errors}")
    st.caption(
        f"模型版本 {comparison.metadata['model_version']} · 分辨率 {comparison.metadata['n_steps_per_hour']}点/小时 · "
        f"随机种子 {comparison.metadata['seed']}"
    )
    st.download_button(
        "下载场景对比与全部原始成果包",
        data=comparison.artifact_bytes,
        file_name="S0-S8_scenario_comparison.zip",
        mime="application/zip",
        use_container_width=True,
    )


def green_direct_page(*, embedded: bool = False) -> None:
    if current_model_kind() == ModelKind.INTEGRATED_PLANNING.value:
        if not embedded:
            page_title("绿电直连规划", "读取V17场景内生的园区绿电覆盖、直连筛查和电转其他能源协同结果。")
        else:
            section_label("绿电直连与电转其他能源决策")
        execution = require_integrated_result()
        if execution is None:
            return
        raw_metrics_table = (execution.tables or {}).get("metrics", pd.DataFrame())
        if not raw_metrics_table.empty and "Metric" in raw_metrics_table:
            relevant = raw_metrics_table[
                raw_metrics_table["Metric"].astype(str).str.contains(
                    "renew|green|direct|p2x|hydrogen|electrolyzer|industrial", case=False, regex=True
                )
            ]
            relevant = localize_v17_table("metrics", relevant)
        else:
            relevant = pd.DataFrame()
        render_integrated_result_cards(execution)
        options = GreenDirectService.from_v17_metrics(execution.metrics)
        if not options.empty:
            best = options.loc[options["年度成本/万元"].idxmin()]
            section_label("V17绿电直连方案")
            fig = go.Figure(
                go.Bar(
                    x=options["方案"],
                    y=options["年度成本/万元"],
                    marker_color=["#16a34a", "#2563eb", "#9333ea"],
                    text=options["年度成本/万元"].round(2),
                    textposition="outside",
                )
            )
            fig.update_layout(title="绿电直连年度成本")
            fig.update_yaxes(title="年度成本 / 万元（人民币）")
            st.plotly_chart(plot_layout(fig, height=380), use_container_width=True)
            st.markdown(
                f'<div class="best-strip">模型推荐：<b>{best["方案"]}</b>，年度成本约 '
                f'{float(best["年度成本/万元"]):.2f} 万元（人民币）</div>',
                unsafe_allow_html=True,
            )
        section_label("模型内生筛查指标")
        if relevant.empty:
            empty_hint("当前场景未输出专项指标", "可选择S6、S7或S8并启用绿电直连或电转其他能源参数后重新运行。")
        else:
            st.dataframe(relevant, use_container_width=True, hide_index=True)
        st.info("综合规划模式下，本页直接读取V17优化结果，不使用页面固定数字重新计算方案。")
        return
    if not embedded:
        page_title("绿电直连规划", "根据当前实时调度结果计算绿电缺口，并比较三类补充方式的规划成本。")
    else:
        section_label("绿电补充方案决策")
    simulation = require_result()
    if simulation is None:
        return
    metrics = metrics_dict(simulation)
    inputs = input_dict()
    rolling_days = max(float(inputs.get("rolling_days", 1) or 1), 1.0)
    annual_scale = 365.0 / rolling_days
    annual_demand = float(metrics.get("Total electricity demand [MWh]", 0.0)) * annual_scale
    annual_green = float(metrics.get("Total renewable generation [MWh]", 0.0)) * annual_scale

    c1, c2, c3, c4, c5 = st.columns(5)
    target_share = c1.slider("目标绿电占比 / %", 10.0, 100.0, max(60.0, float(metrics.get("Renewable share [%]", 0.0))), 1.0)
    planning_years = c2.number_input("规划周期 / 年", min_value=1, max_value=50, value=int(inputs.get("service_life", 25) or 25), step=1)
    green_lcoe = c3.number_input("园区内绿电成本 / 元每兆瓦时", min_value=1.0, max_value=1500.0, value=360.0, step=10.0)
    vpp_lcoe = c4.number_input("虚拟电厂绿电成本 / 元每兆瓦时", min_value=1.0, max_value=1500.0, value=430.0, step=10.0)
    base_lcoe = c5.number_input("绿电基地成本 / 元每兆瓦时", min_value=1.0, max_value=1500.0, value=390.0, step=10.0)
    with st.expander("线路损耗与固定工程费"):
        c6, c7, c8 = st.columns(3)
        park_loss = c6.slider("园区内损耗 / %", 0.0, 20.0, 1.5, 0.1)
        vpp_loss = c7.slider("虚拟电厂聚合损耗 / %", 0.0, 20.0, 2.5, 0.1)
        base_loss = c8.slider("绿电基地专线损耗 / %", 0.0, 20.0, 3.5, 0.1)
        c9, c10, c11 = st.columns(3)
        park_fixed = c9.number_input("园区内固定工程费 / 万元", 0.0, 200_000.0, 600.0, 100.0)
        vpp_fixed = c10.number_input("虚拟电厂平台费 / 万元", 0.0, 200_000.0, 900.0, 100.0)
        base_fixed = c11.number_input("绿电基地专线工程费 / 万元", 0.0, 200_000.0, 1800.0, 100.0)

    assessment = GreenDirectService().evaluate(
        GreenDirectRequest(
            annual_demand_mwh=annual_demand,
            annual_green_mwh=annual_green,
            target_share=target_share / 100.0,
            planning_years=int(planning_years),
            park_lcoe_cny_per_mwh=green_lcoe,
            vpp_lcoe_cny_per_mwh=vpp_lcoe,
            base_lcoe_cny_per_mwh=base_lcoe,
            park_loss_rate=park_loss / 100.0,
            vpp_loss_rate=vpp_loss / 100.0,
            base_loss_rate=base_loss / 100.0,
            park_fixed_cost_wan_cny=park_fixed,
            vpp_fixed_cost_wan_cny=vpp_fixed,
            base_fixed_cost_wan_cny=base_fixed,
        )
    )
    costs = dict(zip(assessment.options["方案"], assessment.options["规划期成本/万元"]))

    section_label("当前绿电缺口")
    cols = st.columns(4)
    with cols[0]:
        metric_card("折算年用电量", fmt(annual_demand), "兆瓦时", "blue", "E")
    with cols[1]:
        metric_card("当前年绿电量", fmt(annual_green), "兆瓦时", "green", "R")
    with cols[2]:
        metric_card("目标绿电量", fmt(assessment.annual_target_green_mwh), "兆瓦时", "purple", "T")
    with cols[3]:
        metric_card("需补充绿电", fmt(assessment.annual_green_gap_mwh), "兆瓦时", "orange", "G")

    section_label("方案成本对比")
    st.plotly_chart(green_cost_figure(costs), use_container_width=True)
    st.markdown(
        f'<div class="best-strip">推荐方案：<b>{assessment.recommended_mode}</b>，规划期成本约 '
        f'{assessment.recommended_cost_wan_cny:.1f} 万元</div>',
        unsafe_allow_html=True,
    )
    st.dataframe(assessment.options, use_container_width=True, hide_index=True)


def analysis_page() -> None:
    if current_model_kind() == ModelKind.INTEGRATED_PLANNING.value:
        integrated_analysis_page()
    else:
        realtime_results_page()


def decision_page() -> None:
    if current_model_kind() == ModelKind.INTEGRATED_PLANNING.value:
        page_title("场景与决策", "比较V17规划场景，并查看绿电直连和电转其他能源方案。")
        comparison_tab, green_tab = st.tabs(["场景对比", "绿电直连与电转其他能源"])
        with comparison_tab:
            scenario_comparison_page(embedded=True)
        with green_tab:
            green_direct_page(embedded=True)
    else:
        page_title("绿电决策", "基于当前调度结果测算绿电缺口和补充方案成本。")
        green_direct_page(embedded=True)


def main() -> None:
    init_state()
    page = sidebar()
    if page == "平台概览":
        overview_page()
    elif page == "项目中心":
        project_task_page()
    elif page == "参数配置与运行":
        parameter_run_page()
    elif page == "运行分析":
        analysis_page()
    elif page in {"场景与决策", "绿电决策"}:
        decision_page()


if __name__ == "__main__":
    main()
