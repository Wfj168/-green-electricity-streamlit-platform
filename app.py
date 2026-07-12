from __future__ import annotations

from dataclasses import asdict
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.application import SimulationRequest, SimulationService
from src.api.client import ApiClientError, PlatformApiClient
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


PAGES = [
    "平台概览",
    "项目与任务",
    "参数配置与运行",
    "实时结果图",
    "调度综合指标",
    "绿电直连规划",
    "结果导出",
    "工程架构",
]


def init_state() -> None:
    defaults: dict[str, Any] = {
        "simulation_result": None,
        "simulation_inputs": None,
        "generator_table": default_generator_table(),
        "storage_table": default_storage_table(),
        "fuel_table": default_fuel_table(),
        "capex_table": default_capex_table(),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def result() -> dict[str, Any] | None:
    value = st.session_state.get("simulation_result")
    return value if isinstance(value, dict) and value.get("success") else None


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
        selected = st.radio("功能导航", PAGES, label_visibility="collapsed")
        st.divider()
        if result() is None:
            status_box("当前状态", "尚未完成实时计算，请先配置参数并运行模型。", ok=False)
        else:
            inputs = input_dict()
            status_box(
                "当前状态",
                f"已完成场景：{inputs.get('scenario_name', 'current scenario')}",
                ok=True,
            )
        st.markdown(
            """
            <div class="sidebar-note">
              本平台的图表和指标来自当前参数下的滚动线性优化结果。修改参数后需要重新运行，后续页面会自动读取新的计算结果。
            </div>
            """,
            unsafe_allow_html=True,
        )
    return selected


def overview_page() -> None:
    page_title("园区低碳规划与绿电直连优化平台", "面向园区综合能源系统的参数建模、实时优化、指标分析与绿电直连决策支持。")
    badge("实时计算平台")
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
    if simulation is not None:
        section_label("当前实时结果")
        render_result_cards(simulation)
    else:
        empty_hint("尚未运行模型", "进入“参数配置与运行”页面后，可以使用默认参数或上传时序数据完成第一次计算。")

    section_label("业务流程")
    cols = st.columns(4)
    cards = [
        ("1 参数建模", "配置电源、储能、燃料价格、约束和源荷时序，形成优化问题输入。"),
        ("2 滚动优化", "以48小时窗口滚动求解，每次保存前24小时调度结果，维持储能SOC连续。"),
        ("3 结果分析", "生成电力平衡、储能SOC、购售电行为、成本、碳排和约束执行检查。"),
        ("4 决策输出", "基于计算结果测算绿电直连缺口和规划成本，并导出完整结果包。"),
    ]
    for col, (title, body) in zip(cols, cards):
        with col:
            st.markdown(f'<div class="feature-card"><b>{title}</b><span>{body}</span></div>', unsafe_allow_html=True)

    section_label("核心模型能力")
    pills(["线性规划", "滚动时域调度", "RPS约束", "CO2约束", "CEEP约束", "储能SOC递推", "绿电直连成本测算"])


def project_task_page() -> None:
    page_title("项目与任务", "保存版本化场景、提交后台优化任务，并查看可追溯的历史结果。")
    client = PlatformApiClient()
    if not client.configured:
        st.warning("当前仍在原型直算模式。配置 PLATFORM_API_URL 后即可启用项目、场景和后台任务管理。")
        st.code("PLATFORM_API_URL=http://127.0.0.1:8000", language="text")
        st.info("现有“参数配置与运行”及结果页面不受影响，可继续用于单用户实时演示。")
        return

    try:
        health = client.health()
        status_box(
            "后台服务已连接",
            f"平台版本 {health['version']} · 模型版本 {health['model_version']}",
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
    current_inputs = input_dict()
    if not current_inputs:
        st.info("尚未运行当前会话参数，将使用默认实时场景参数创建后台任务。")
        default_input = build_inputs(
            "Default project scenario", 1_000_000.0, 25, 90.0, 70.0, 500.0,
            True, 35.0, False, 100_000.0, False, 20.0, True, False, 3, "CN",
        )
        current_inputs = asdict(default_input)
    scenario_payload = {
        "inputs": current_inputs,
        "generator_table": st.session_state["generator_table"].to_dict(orient="records"),
        "storage_table": st.session_state["storage_table"].to_dict(orient="records"),
        "fuel_table": st.session_state["fuel_table"].to_dict(orient="records"),
        "capex_table": st.session_state["capex_table"].to_dict(orient="records"),
    }
    with st.form("submit_project_job_form"):
        scenario_name = st.text_input("场景版本名称", value=current_inputs.get("scenario_name", "realtime scenario"))
        submit_job_clicked = st.form_submit_button("保存场景并提交后台计算", type="primary")
    if submit_job_clicked:
        try:
            scenario = client.create_scenario(project_id, scenario_name, scenario_payload)
            job = client.create_job(project_id, scenario["id"])
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


def parameter_run_page() -> None:
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


def green_direct_page() -> None:
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

    c1, c2, c3, c4 = st.columns(4)
    target_share = c1.slider("目标绿电占比 / %", 10.0, 100.0, max(60.0, float(metrics.get("Renewable share [%]", 0.0))), 1.0)
    planning_years = c2.number_input("规划周期 / 年", min_value=1, max_value=50, value=int(inputs.get("service_life", 25) or 25), step=1)
    green_lcoe = c3.number_input("园区内绿电成本 / 元-MWh", min_value=1.0, max_value=1500.0, value=360.0, step=10.0)
    vpp_lcoe = c4.number_input("虚拟电厂绿电成本 / 元-MWh", min_value=1.0, max_value=1500.0, value=430.0, step=10.0)

    c5, c6, c7 = st.columns(3)
    base_lcoe = c5.number_input("绿电基地成本 / 元-MWh", min_value=1.0, max_value=1500.0, value=390.0, step=10.0)
    line_loss = c6.slider("专线损耗率 / %", 0.0, 20.0, 3.5, 0.1)
    fixed_cost = c7.number_input("直连固定工程费 / 万元", min_value=0.0, max_value=200_000.0, value=1500.0, step=100.0)

    target_green = annual_demand * target_share / 100
    green_gap = max(0.0, target_green - annual_green)
    effective_base_energy = green_gap / max(1 - line_loss / 100, 0.01)
    costs = {
        "园区内新增绿电": green_gap * green_lcoe * planning_years / 10_000 + fixed_cost * 0.4,
        "虚拟电厂聚合绿电": green_gap * vpp_lcoe * planning_years / 10_000 + fixed_cost * 0.15,
        "绿电基地直连": effective_base_energy * base_lcoe * planning_years / 10_000 + fixed_cost,
    }
    best_name = min(costs, key=costs.get)

    section_label("当前绿电缺口")
    cols = st.columns(4)
    with cols[0]:
        metric_card("折算年用电量", fmt(annual_demand), "MWh", "blue", "E")
    with cols[1]:
        metric_card("当前年绿电量", fmt(annual_green), "MWh", "green", "R")
    with cols[2]:
        metric_card("目标绿电量", fmt(target_green), "MWh", "purple", "T")
    with cols[3]:
        metric_card("需补充绿电", fmt(green_gap), "MWh", "orange", "G")

    section_label("方案成本对比")
    st.plotly_chart(green_cost_figure(costs), use_container_width=True)
    st.markdown(f'<div class="best-strip">推荐方案：<b>{best_name}</b>，规划期成本约 {costs[best_name]:.1f} 万元</div>', unsafe_allow_html=True)
    st.dataframe(pd.DataFrame({"方案": list(costs.keys()), "规划期成本/万元": list(costs.values())}), use_container_width=True, hide_index=True)


def export_page() -> None:
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
    elif page == "实时结果图":
        realtime_results_page()
    elif page == "调度综合指标":
        indicator_page()
    elif page == "绿电直连规划":
        green_direct_page()
    elif page == "结果导出":
        export_page()
    elif page == "工程架构":
        architecture_page()


if __name__ == "__main__":
    main()
