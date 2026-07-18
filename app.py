from __future__ import annotations

from dataclasses import asdict
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.application import (
    GreenDirectRequest,
    GreenDirectService,
    ModelExecutionRequest,
    ModelExecutionResult,
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
from src.core import IntegratedPlanningConfig, scenario_fingerprint
from src.core.schemas import StoreMoreInputs
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
    "项目与任务",
    "参数配置与运行",
    "实时结果图",
    "调度综合指标",
    "绿电直连规划",
    "结果导出",
    "工程架构",
]

INTEGRATED_PAGES = [
    "平台概览",
    "项目与任务",
    "参数配置与运行",
    "多能流结果",
    "综合规划指标",
    "场景对比",
    "绿电直连规划",
    "结果导出",
    "工程架构",
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
        scenario_name="Default realtime scenario",
        total_demand=1_000_000.0,
        service_life=25,
        import_price=90.0,
        export_price=70.0,
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
    colors = {
        "Solar": "#f59e0b",
        "Wind": "#22c55e",
        "Gas": "#f97316",
        "Import": "#2563eb",
        "Storage discharge": "#8b5cf6",
    }
    fig = go.Figure()
    for column in ["Solar", "Wind", "Gas", "Import", "Storage discharge"]:
        fig.add_trace(
            go.Scatter(
                x=dispatch["Period"],
                y=dispatch[column],
                mode="lines",
                stackgroup="supply",
                name=column,
                line=dict(width=1.5, color=colors[column]),
            )
        )
    fig.add_trace(
        go.Scatter(
            x=dispatch["Period"],
            y=dispatch["Demand"],
            mode="lines",
            name="Demand",
            line=dict(width=3, color="#111827"),
        )
    )
    fig.update_xaxes(title="滚动小时")
    fig.update_yaxes(title="功率 / MW")
    fig.update_layout(title="电力平衡实时计算结果")
    return plot_layout(fig)


def storage_figure(dispatch: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=dispatch["Period"],
            y=-dispatch["Storage charge"],
            name="Storage charge",
            marker_color="#38bdf8",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(
            x=dispatch["Period"],
            y=dispatch["Storage discharge"],
            name="Storage discharge",
            marker_color="#a855f7",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=dispatch["Period"],
            y=dispatch["SOC"],
            name="SOC",
            line=dict(color="#16a34a", width=3),
        ),
        secondary_y=True,
    )
    fig.update_layout(title="储能充放电与 SOC")
    fig.update_xaxes(title="滚动小时")
    fig.update_yaxes(title_text="充放电功率 / MW", secondary_y=False)
    fig.update_yaxes(title_text="SOC / MWh", secondary_y=True)
    return plot_layout(fig)


def balance_figure(dispatch: pd.DataFrame) -> go.Figure:
    total_supply = dispatch[["Solar", "Wind", "Gas", "Import", "Storage discharge"]].sum(axis=1)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dispatch["Period"], y=dispatch["Demand"], mode="lines", name="Demand", line=dict(color="#111827", width=3)))
    fig.add_trace(go.Scatter(x=dispatch["Period"], y=total_supply, mode="lines", name="Total supply", line=dict(color="#0ea5e9", width=3)))
    fig.add_trace(go.Bar(x=dispatch["Period"], y=dispatch["Excess"], name="Excess", marker_color="#f59e0b"))
    fig.add_trace(go.Bar(x=dispatch["Period"], y=dispatch["Unmet"], name="Unmet", marker_color="#ef4444"))
    fig.update_layout(title="供需校核、弃电与缺电", barmode="group")
    fig.update_xaxes(title="滚动小时")
    fig.update_yaxes(title="MWh / h")
    return plot_layout(fig)


def price_dispatch_figure(dispatch: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=dispatch["Period"], y=dispatch["Import price"], name="Import price", line=dict(color="#2563eb", width=2)), secondary_y=True)
    fig.add_trace(go.Scatter(x=dispatch["Period"], y=dispatch["Export price"], name="Export price", line=dict(color="#64748b", width=2, dash="dot")), secondary_y=True)
    fig.add_trace(go.Bar(x=dispatch["Period"], y=dispatch["Import"], name="Import power", marker_color="#93c5fd"), secondary_y=False)
    fig.add_trace(go.Bar(x=dispatch["Period"], y=-dispatch["Export"], name="Export power", marker_color="#fbbf24"), secondary_y=False)
    fig.update_layout(title="电价驱动的购售电行为")
    fig.update_xaxes(title="滚动小时")
    fig.update_yaxes(title_text="购售电功率 / MW", secondary_y=False)
    fig.update_yaxes(title_text="价格 / EUR-MWh", secondary_y=True)
    return plot_layout(fig)


def metrics_bar_figure(metrics: dict[str, float]) -> go.Figure:
    selected = {
        "Renewable share [%]": "绿电占比",
        "CEEP share [%]": "弃电率",
        "CO2 emissions [tCO2]": "碳排放",
        "Total cost proxy [EUR]": "综合成本",
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
            name="48h window objective",
            marker_color="#0ea5e9",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=rolling_log["Rolling day"],
            y=rolling_log["Final SOC after saved horizon [MWh]"],
            name="Final SOC",
            yaxis="y2",
            line=dict(color="#22c55e", width=3),
        )
    )
    fig.update_layout(
        title="滚动优化窗口状态",
        yaxis=dict(title="目标函数值"),
        yaxis2=dict(title="末端 SOC / MWh", overlaying="y", side="right"),
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
    fig.update_xaxes(title="典型日时刻 / h")
    fig.update_yaxes(title="功率 / MW")
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
    fig.update_xaxes(title="典型日时刻 / h")
    fig.update_yaxes(title="热功率 / MWth")
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
    fig.update_xaxes(title="典型日时刻 / h")
    fig.update_yaxes(title="冷功率 / MWc")
    return plot_layout(fig, height=380)


def integrated_storage_figure(dispatch: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if "SOC_BAT" in dispatch:
        fig.add_trace(
            go.Scatter(x=dispatch["hour"], y=dispatch["SOC_BAT"], name="电储能SOC", line=dict(width=3))
        )
    if "SOC_TS" in dispatch:
        fig.add_trace(
            go.Scatter(x=dispatch["hour"], y=dispatch["SOC_TS"], name="蓄热SOC", line=dict(width=3))
        )
    fig.update_layout(title="电/热储能状态")
    fig.update_xaxes(title="典型日时刻 / h")
    fig.update_yaxes(title="储能量 / MWh")
    return plot_layout(fig, height=380)


def scenario_cost_carbon_figure(table: pd.DataFrame) -> go.Figure:
    valid = table[table["Success"]].copy()
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=valid["Scenario"],
            y=valid["Social annual cost [EUR/year]"] / 1_000_000.0,
            name="社会年成本",
            marker_color="#2563eb",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=valid["Scenario"],
            y=valid["Annual CO2 [tCO2/year]"],
            name="年度碳排放",
            mode="lines+markers",
            line=dict(width=3, color="#ef4444"),
        ),
        secondary_y=True,
    )
    fig.update_layout(title="S0—S8成本与碳排放")
    fig.update_yaxes(title_text="社会年成本 / 百万EUR", secondary_y=False)
    fig.update_yaxes(title_text="年度碳排放 / tCO2", secondary_y=True)
    return plot_layout(fig)


def abatement_frontier_figure(table: pd.DataFrame) -> go.Figure:
    valid = table[table["Success"]].copy()
    fig = go.Figure(
        go.Scatter(
            x=valid["Annual CO2 [tCO2/year]"],
            y=valid["Social annual cost [EUR/year]"] / 1_000_000.0,
            text=valid["Scenario"],
            mode="markers+text",
            textposition="top center",
            marker=dict(
                size=14,
                color=valid["CO2 reduction vs S0 [%]"],
                colorscale="Viridis",
                showscale=True,
                colorbar=dict(title="减排/%"),
            ),
        )
    )
    fig.update_layout(title="成本—碳排权衡前沿")
    fig.update_xaxes(title="年度碳排放 / tCO2")
    fig.update_yaxes(title="社会年成本 / 百万EUR")
    return plot_layout(fig, height=420)


def render_result_cards(simulation: dict[str, Any]) -> None:
    metrics = metrics_dict(simulation)
    cols = st.columns(4)
    with cols[0]:
        metric_card("模拟期用电量", fmt(metrics.get("Total electricity demand [MWh]", 0)), "MWh", "blue", "E")
    with cols[1]:
        metric_card("绿电占比", fmt(metrics.get("Renewable share [%]", 0)), "%", "green", "R")
    with cols[2]:
        metric_card("CO2排放量", fmt(metrics.get("CO2 emissions [tCO2]", 0)), "tCO2", "orange", "C")
    with cols[3]:
        metric_card("综合成本", fmt(metrics.get("Total cost proxy [EUR]", 0)), "EUR", "purple", "¥")


def render_integrated_result_cards(execution: ModelExecutionResult) -> None:
    metrics = execution.metrics
    cols = st.columns(4)
    with cols[0]:
        metric_card("年度碳排放", fmt(metrics.get("Annual CO2 emissions", 0)), "tCO2", "orange", "C")
    with cols[1]:
        metric_card("年度电网购电", fmt(metrics.get("Annual grid import", 0)), "MWh", "blue", "G")
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
            help="快速调度用于小时级电力运行；V17用于电、热、冷、气、储能、柔性负荷、碳与P2X协同规划。",
        )
        st.session_state["model_kind"] = next(
            key for key, label in MODEL_LABELS.items() if label == selected_model_label
        )
        pages = (
            INTEGRATED_PAGES
            if current_model_kind() == ModelKind.INTEGRATED_PLANNING.value
            else REALTIME_PAGES
        )
        selected = st.radio("功能导航", pages, label_visibility="collapsed")
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
                f"已完成场景：{inputs.get('scenario_name', 'current scenario')}",
                ok=True,
            )
        mode_note = (
            "综合规划结果来自当前S0—S8场景和参数覆盖项。修改设备、储能、柔性负荷、碳或P2X参数后需要重新运行。"
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
        ("2 系统配置", "配置设备、储能、柔性负荷、碳、绿电直连和P2X参数。"),
        ("3 优化求解", "通过统一模型服务执行线性规划、滚动优化或综合规划。"),
        ("4 决策交付", "保存场景版本、比较指标并导出可追溯成果包。"),
    ]
    for col, (title, body) in zip(cols, cards):
        with col:
            st.markdown(f'<div class="feature-card"><b>{title}</b><span>{body}</span></div>', unsafe_allow_html=True)

    section_label("核心模型能力")
    pills(["双模型目录", "滚动时域调度", "电热冷气协同", "储能与柔性负荷", "碳约束", "绿电直连", "P2X/绿氢"])


def project_task_page() -> None:
    page_title("项目与任务", "保存版本化场景、提交后台优化任务，并查看可追溯的历史结果。")
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
            f"平台版本 {health.get('version', '未知')} · 模型版本 {health.get('model_version', '未知')}",
            ok=True,
        )
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
                "Default project scenario", 1_000_000.0, 25, 90.0, 70.0, 500.0,
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
        default_scenario_name = str(current_inputs.get("scenario_name", "realtime scenario"))
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
    st.dataframe(job_table[[column for column in visible_columns if column in job_table]], hide_index=True)
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
            st.json(persisted_result)
        except ApiClientError as exc:
            st.error(str(exc))


def integrated_parameter_run_page() -> None:
    page_title(
        "综合能源系统配置与运行",
        "选择S0—S8场景，配置电、热、冷、储能、柔性负荷、碳、绿电直连和P2X参数。",
    )
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
            ["设备", "储能", "柔性负荷", "碳约束", "绿电直连", "P2X/绿氢"]
        )
        with equipment_tab:
            st.caption("容量均为规划上限；0表示不允许新增该技术。")
            c1, c2, c3 = st.columns(3)
            max_pv = c1.number_input("光伏上限 / MW", 0.0, 2000.0, base.max_pv_capacity, 10.0)
            max_wt = c2.number_input("风电上限 / MW", 0.0, 2000.0, base.max_wt_capacity, 10.0)
            max_chp = c3.number_input("热电联产上限 / MW", 0.0, 1000.0, base.max_chp_capacity, 5.0)
            c4, c5, c6 = st.columns(3)
            max_hp = c4.number_input("热泵上限 / MWth", 0.0, 1000.0, base.max_hp_capacity, 5.0)
            max_ec = c5.number_input("电制冷上限 / MWc", 0.0, 1000.0, base.max_ec_capacity, 5.0)
            max_gb = c6.number_input("燃气锅炉上限 / MWth", 0.0, 1000.0, base.max_gb_capacity, 5.0)

        with storage_tab:
            c1, c2 = st.columns(2)
            enable_battery = c1.checkbox("启用电化学储能", value=base.enable_battery)
            enable_thermal_storage = c2.checkbox("启用蓄热储能", value=base.enable_thermal_storage)
            c3, c4, c5, c6 = st.columns(4)
            battery_energy = c3.number_input(
                "电储能能量上限 / MWh", 0.0, 3000.0, base.max_battery_energy_capacity, 10.0,
                disabled=not enable_battery,
            )
            battery_power = c4.number_input(
                "电储能功率上限 / MW", 0.0, 1000.0, base.max_battery_power_capacity, 5.0,
                disabled=not enable_battery,
            )
            thermal_energy = c5.number_input(
                "蓄热能量上限 / MWhth", 0.0, 3000.0, base.max_thermal_storage_energy_capacity, 10.0,
                disabled=not enable_thermal_storage,
            )
            thermal_power = c6.number_input(
                "蓄热功率上限 / MWth", 0.0, 1000.0, base.max_thermal_storage_power_capacity, 5.0,
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
                "相对S0碳排上限 / %", 1.0, 100.0, 100.0 * base.co2_cap_ratio_to_s0, 1.0,
                disabled=not enable_carbon,
            )
            carbon_price = c4.number_input(
                "碳市场价格 / CNY-tCO2", 0.0, 2000.0, base.carbon_market_price_cny_per_tco2, 10.0,
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
            enable_p2x = st.checkbox("启用内生P2X/绿氢优化", value=base.enable_endogenous_p2x)
            c1, c2, c3 = st.columns(3)
            p2x_heat_share = c1.slider(
                "最低工艺热替代 / %", 0.0, 100.0,
                100.0 * base.p2x_min_process_heat_substitution_share, 1.0,
                disabled=not enable_p2x,
            )
            electrolyzer_capacity = c2.number_input(
                "电解槽容量上限 / MW", 0.0, 1000.0, base.max_electrolyzer_capacity, 5.0,
                disabled=not enable_p2x,
            )
            p2x_power_share = c3.slider(
                "P2X最多使用新能源电量 / %", 0.0, 100.0,
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
    st.caption(f"参数结构：integrated-planning-v1 · 参数指纹：{scenario_fingerprint(payload)[:12]}")
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
    if current_model_kind() == ModelKind.INTEGRATED_PLANNING.value:
        integrated_parameter_run_page()
    else:
        realtime_parameter_run_page()


def realtime_parameter_run_page() -> None:
    page_title("参数配置与运行", "先建立园区系统边界，再运行实时优化，后续页面全部读取本次计算结果。")

    with st.container():
        section_label("基础场景")
        c1, c2, c3, c4 = st.columns(4)
        scenario_name = c1.text_input("场景名称", value="Park realtime case")
        total_demand = c2.number_input("年用电需求 / MWh", min_value=10_000.0, max_value=10_000_000.0, value=1_000_000.0, step=50_000.0)
        service_life = c3.number_input("规划周期 / 年", min_value=1, max_value=50, value=25, step=1)
        rolling_days = c4.slider("滚动优化天数", min_value=1, max_value=14, value=3)

        c5, c6, c7, c8 = st.columns(4)
        import_price = c5.number_input("购电均价 / EUR-MWh", min_value=1.0, max_value=500.0, value=90.0, step=5.0)
        export_price = c6.number_input("售电均价 / EUR-MWh", min_value=0.0, max_value=500.0, value=70.0, step=5.0)
        import_export_capacity = c7.number_input("购售电容量上限 / MW", min_value=1.0, max_value=5000.0, value=500.0, step=20.0)
        country_code = c8.text_input("电价分布国家代码", value="CN")

    section_label("约束与运行策略")
    c1, c2, c3 = st.columns(3)
    with c1:
        rps_constraint = st.checkbox("启用绿电占比约束", value=True)
        min_res_share = st.slider("最低绿电占比 / %", 0.0, 95.0, 35.0, 1.0)
    with c2:
        co2_constraint = st.checkbox("启用CO2排放约束", value=False)
        max_co2 = st.number_input("年度CO2排放上限 / tCO2", min_value=1000.0, max_value=5_000_000.0, value=100_000.0, step=10_000.0)
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
    st.caption("可上传完整时序CSV，也可以不上传，由平台根据总需求、典型日内曲线和随机扰动生成计算用数据。")
    template = csv_template(total_demand=total_demand, import_price=import_price, export_price=export_price)
    st.download_button(
        "下载8760小时CSV模板",
        data=template.to_csv(index=False).encode("utf-8-sig"),
        file_name="profile_template.csv",
        mime="text/csv",
    )
    uploaded_csv = st.file_uploader("上传源荷或电价CSV", type=["csv"])

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
            st.info("可以适当放宽绿电占比、CO2上限或弃电率约束，也可以提高购售电容量上限后重新运行。")


def realtime_results_page() -> None:
    if current_model_kind() == ModelKind.INTEGRATED_PLANNING.value:
        page_title("综合能源规划结果", "查看当前V17场景的容量配置和多能协同调度明细。")
        execution = require_integrated_result()
        if execution is None:
            return
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
            st.dataframe(tables.get("capacity", pd.DataFrame()), use_container_width=True, hide_index=True)
        with dispatch_tab:
            st.dataframe(tables.get("dispatch", pd.DataFrame()), use_container_width=True, hide_index=True)
        with cost_tab:
            st.dataframe(tables.get("cost", pd.DataFrame()), use_container_width=True, hide_index=True)
        with carbon_tab:
            st.dataframe(tables.get("carbon", pd.DataFrame()), use_container_width=True, hide_index=True)
        with diagnostic_tab:
            st.dataframe(tables.get("diagnostics", pd.DataFrame()), use_container_width=True, hide_index=True)
        return
    page_title("实时结果图", "所有图表均由当前场景实时计算得到，并随参数变化同步刷新。")
    simulation = require_result()
    if simulation is None:
        return
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


def indicator_page() -> None:
    if current_model_kind() == ModelKind.INTEGRATED_PLANNING.value:
        page_title("综合规划指标", "查看当前V17场景的能源、经济、环境、可靠性和求解指标。")
        execution = require_integrated_result()
        if execution is None:
            return
        render_integrated_result_cards(execution)
        metrics_table = (execution.tables or {}).get("metrics", pd.DataFrame())
        section_label("分组指标")
        groups = {
            "能源": "renewable|grid import|grid export|storage|flexible|hydrogen|electrolyzer",
            "经济": "cost|charge|revenue",
            "环境": "co2|carbon|curtailment",
            "可靠性": "service rate|unmet|unserved|shortage|autonomy",
            "园区与P2X": "industrial|green-direct|p2x|low-altitude",
        }
        tabs = st.tabs(list(groups) + ["全部"])
        for tab, (name, pattern) in zip(tabs[:-1], groups.items()):
            with tab:
                if metrics_table.empty:
                    st.dataframe(metrics_table)
                else:
                    selected = metrics_table[
                        metrics_table["Metric"].astype(str).str.contains(pattern, case=False, regex=True)
                    ]
                    st.dataframe(selected, use_container_width=True, hide_index=True)
        with tabs[-1]:
            st.dataframe(metrics_table, use_container_width=True, hide_index=True)
        section_label("执行追溯")
        st.json({"summary": execution.summary, "metadata": execution.metadata})
        return
    page_title("调度综合指标", "基于实时调度结果计算经济、低碳、可靠性与约束执行情况。")
    simulation = require_result()
    if simulation is None:
        return
    metrics = metrics_dict(simulation)
    inputs = input_dict()
    render_result_cards(simulation)

    section_label("关键指标图")
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
                "约束": "CO2排放",
                "目标": f"<= {limit:.1f} tCO2",
                "结果": f"{metrics.get('CO2 emissions [tCO2]', 0):.1f} tCO2",
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
        empty_hint("未启用额外约束", "当前场景只执行功率平衡、设备容量、储能SOC和购售电容量等基础约束。")
    else:
        st.dataframe(pd.DataFrame(checks), use_container_width=True, hide_index=True)

    section_label("滚动优化状态")
    st.plotly_chart(rolling_figure(simulation["rolling_log"]), use_container_width=True)
    st.dataframe(simulation["rolling_log"], use_container_width=True, hide_index=True)

    section_label("容量规划结果")
    st.dataframe(simulation["investment"], use_container_width=True, hide_index=True)


def scenario_comparison_page() -> None:
    page_title("S0—S8场景对比", "逐场景调用V17模型，比较成本、碳排、新能源、可靠性与减排成本。")
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
    valid = table[table["Success"]] if not table.empty else pd.DataFrame()
    if valid.empty:
        st.error("本次比较没有成功场景，请查看错误信息。")
    else:
        cheapest = valid.loc[valid["Social annual cost [EUR/year]"].idxmin()]
        lowest_carbon = valid.loc[valid["Annual CO2 [tCO2/year]"].idxmin()]
        highest_reduction = valid.loc[valid["CO2 reduction vs S0 [%]"].idxmax()]
        cols = st.columns(4)
        with cols[0]:
            metric_card("已完成场景", str(len(valid)), "个", "blue", "N")
        with cols[1]:
            metric_card("最低成本场景", str(cheapest["Scenario"]), "", "green", "¥")
        with cols[2]:
            metric_card("最低碳场景", str(lowest_carbon["Scenario"]), "", "orange", "C")
        with cols[3]:
            metric_card("最大减排场景", str(highest_reduction["Scenario"]), "", "purple", "R")
        st.plotly_chart(scenario_cost_carbon_figure(table), use_container_width=True)
        st.plotly_chart(abatement_frontier_figure(table), use_container_width=True)

    section_label("场景指标明细")
    st.dataframe(table, use_container_width=True, hide_index=True)
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


def green_direct_page() -> None:
    if current_model_kind() == ModelKind.INTEGRATED_PLANNING.value:
        page_title("绿电直连规划", "读取V17场景内生的园区绿电覆盖、直连筛查和P2X协同结果。")
        execution = require_integrated_result()
        if execution is None:
            return
        metrics_table = (execution.tables or {}).get("metrics", pd.DataFrame())
        if not metrics_table.empty and "Metric" in metrics_table:
            relevant = metrics_table[
                metrics_table["Metric"].astype(str).str.contains(
                    "renew|green|direct|p2x|hydrogen|electrolyzer|industrial", case=False, regex=True
                )
            ]
        else:
            relevant = pd.DataFrame()
        render_integrated_result_cards(execution)
        options = GreenDirectService.from_v17_metrics(execution.metrics)
        if not options.empty:
            best = options.loc[options["年度成本/百万元"].idxmin()]
            section_label("V17绿电直连方案")
            fig = go.Figure(
                go.Bar(
                    x=options["方案"],
                    y=options["年度成本/百万元"],
                    marker_color=["#16a34a", "#2563eb", "#9333ea"],
                    text=options["年度成本/百万元"].round(2),
                    textposition="outside",
                )
            )
            fig.update_layout(title="绿电直连年度成本")
            fig.update_yaxes(title="年度成本 / 百万元")
            st.plotly_chart(plot_layout(fig, height=380), use_container_width=True)
            st.markdown(
                f'<div class="best-strip">模型推荐：<b>{best["方案"]}</b>，年度成本约 '
                f'{float(best["年度成本/百万元"]):.2f} 百万元</div>',
                unsafe_allow_html=True,
            )
        section_label("模型内生筛查指标")
        if relevant.empty:
            empty_hint("当前场景未输出专项指标", "可选择S6、S7或S8并启用绿电直连/P2X参数后重新运行。")
        else:
            st.dataframe(relevant, use_container_width=True, hide_index=True)
        st.info("综合规划模式下，本页直接读取V17优化结果，不使用页面固定数字重新计算方案。")
        return
    page_title("绿电直连规划", "根据当前实时调度结果计算绿电缺口，并比较三类补充方式的规划成本。")
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
    green_lcoe = c3.number_input("园区内绿电成本 / 元-MWh", min_value=1.0, max_value=1500.0, value=360.0, step=10.0)
    vpp_lcoe = c4.number_input("虚拟电厂绿电成本 / 元-MWh", min_value=1.0, max_value=1500.0, value=430.0, step=10.0)
    base_lcoe = c5.number_input("绿电基地成本 / 元-MWh", min_value=1.0, max_value=1500.0, value=390.0, step=10.0)
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
        metric_card("折算年用电量", fmt(annual_demand), "MWh", "blue", "E")
    with cols[1]:
        metric_card("当前年绿电量", fmt(annual_green), "MWh", "green", "R")
    with cols[2]:
        metric_card("目标绿电量", fmt(assessment.annual_target_green_mwh), "MWh", "purple", "T")
    with cols[3]:
        metric_card("需补充绿电", fmt(assessment.annual_green_gap_mwh), "MWh", "orange", "G")

    section_label("方案成本对比")
    st.plotly_chart(green_cost_figure(costs), use_container_width=True)
    st.markdown(
        f'<div class="best-strip">推荐方案：<b>{assessment.recommended_mode}</b>，规划期成本约 '
        f'{assessment.recommended_cost_wan_cny:.1f} 万元</div>',
        unsafe_allow_html=True,
    )
    st.dataframe(assessment.options, use_container_width=True, hide_index=True)


def export_page() -> None:
    if current_model_kind() == ModelKind.INTEGRATED_PLANNING.value:
        page_title("结果导出", "导出当前V17场景的容量、调度、成本、碳排、指标、诊断和执行清单。")
        execution = require_integrated_result()
        if execution is None:
            return
        section_label("可导出内容")
        pills(["capacity.csv", "dispatch.csv", "cost.csv", "carbon.csv", "metrics.csv", "diagnostics.csv", "execution.json"])
        st.download_button(
            "下载当前综合规划完整结果包",
            data=execution.artifact_bytes or b"",
            file_name=f"integrated_planning_{execution.summary.get('scenario_key', 'scenario')}.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )
        st.json({"summary": execution.summary, "metadata": execution.metadata})
        return
    page_title("结果导出", "导出当前场景的输入、调度、投资、指标、滚动日志和计算图。")
    simulation = require_result()
    if simulation is None:
        return
    section_label("可导出内容")
    pills(["input_summary.csv", "input_profiles_used.csv", "dispatch_results.csv", "investment_results.csv", "key_indicators.csv", "rolling_log.csv", "实时计算图"])
    zip_buffer = simulation["zip"]
    zip_buffer.seek(0)
    st.download_button(
        "下载当前场景完整结果包",
        data=zip_buffer.getvalue(),
        file_name="green_electricity_realtime_results.zip",
        mime="application/zip",
        type="primary",
        use_container_width=True,
    )
    st.dataframe(simulation["summary"], use_container_width=True, hide_index=True)


def architecture_page() -> None:
    page_title("工程架构", "说明平台如何把输入、模型、结果和决策模块组织成可复现工程。")
    section_label("模块划分")
    architecture = pd.DataFrame(
        [
            ["参数配置", "接收设备容量、成本、燃料价格、约束和CSV时序数据", "StoreMoreInputs + DataFrame"],
            ["源荷生成", "无CSV时自动生成负荷、风光出力系数和购售电价曲线", "profiles"],
            ["容量规划", "按需求和投资上限给出光伏、风电、储能新增容量", "investment_results"],
            ["滚动优化", "48小时窗口求解线性规划，每日保存前24小时，SOC跨窗口传递", "dispatch_results"],
            ["指标后处理", "计算绿电占比、弃电、缺电、碳排、运行成本、投资成本", "key_indicators"],
            ["绿电直连", "由当前调度结果折算年绿电缺口并比较三类补充方案", "cost comparison"],
        ],
        columns=["模块", "功能", "数据输出"],
    )
    st.dataframe(architecture, use_container_width=True, hide_index=True)

    section_label("嵌入算法")
    algorithms = pd.DataFrame(
        [
            ["线性规划调度", "最小化燃料、购电、储能、弃电和缺电惩罚成本", "参数配置与运行、实时结果图"],
            ["滚动时域优化", "用48小时预测窗口滚动求解，保留前24小时真实调度结果", "参数配置与运行、调度综合指标"],
            ["储能SOC递推", "充放电效率、小时损耗和末端SOC跨窗口传递", "实时结果图"],
            ["RPS约束", "约束可再生能源发电占比不低于目标值", "参数配置与运行、调度综合指标"],
            ["CO2约束", "用气电碳排因子约束模拟期折算排放", "参数配置与运行、调度综合指标"],
            ["CEEP约束", "限制弃电电量占负荷比例", "参数配置与运行、调度综合指标"],
            ["绿电直连成本筛选", "按实时绿电缺口、规划年限、损耗和电价计算三类方案成本", "绿电直连规划"],
        ],
        columns=["算法", "作用", "对应页面"],
    )
    st.dataframe(algorithms, use_container_width=True, hide_index=True)

    section_label("严谨性边界")
    st.info(
        "当前版本定位为园区综合能源系统线性规划与调度决策平台。它不声称替代真实潮流计算、继电保护校核或电网接入审查；"
        "若用于工程落地，应继续接入配电网潮流、安全约束、电价合同和设备实测数据。"
    )


def main() -> None:
    init_state()
    page = sidebar()
    if page == "平台概览":
        overview_page()
    elif page == "项目与任务":
        project_task_page()
    elif page == "参数配置与运行":
        parameter_run_page()
    elif page in {"实时结果图", "多能流结果"}:
        realtime_results_page()
    elif page in {"调度综合指标", "综合规划指标"}:
        indicator_page()
    elif page == "场景对比":
        scenario_comparison_page()
    elif page == "绿电直连规划":
        green_direct_page()
    elif page == "结果导出":
        export_page()
    elif page == "工程架构":
        architecture_page()


if __name__ == "__main__":
    main()
