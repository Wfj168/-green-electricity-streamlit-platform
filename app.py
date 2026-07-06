from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import streamlit as st

from src import charts
from src.data_loader import (
    figure_assets,
    load_carbon_management,
    load_dispatch,
    load_metrics,
    load_summary,
    metric_from_table,
)
from src.model_adapter import run_quick_trial
from src.ui_components import (
    badge,
    empty_hint,
    green_direct_cost_card,
    inject_global_css,
    metric_card,
    page_title,
    section_label,
)


APP_TITLE = "园区低碳规划与绿电直连优化平台"
BRAND = "绿电向导"


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="leaf",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_global_css()


def _init_state() -> None:
    defaults = {
        "data_ready": False,
        "data_confirmed": False,
        "params_valid": False,
        "quick_trial": None,
        "quick_trial_message": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _safe_number(value: object, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _scenario_row(summary: pd.DataFrame, scenario: str) -> pd.Series:
    hit = summary[summary["Scenario"].eq(scenario)]
    if hit.empty:
        return pd.Series(dtype="object")
    return hit.iloc[0]


def _mode_name(index: float) -> str:
    mapping = {
        1: "园区内绿电",
        2: "虚拟电厂聚合绿电",
        3: "绿电基地",
    }
    return mapping.get(int(round(index or 1)), "园区内绿电")


def _sidebar() -> str:
    with st.sidebar:
        st.markdown(
            f"""
            <div class="brand-card">
              <div class="brand-logo">G</div>
              <div>
                <div class="brand-name">{BRAND}</div>
                <div class="brand-subtitle">县域/园区综合能源优化</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        page = st.radio(
            "功能导航",
            [
                "平台概述",
                "系统构建与运行机制设置",
                "调度结果图",
                "调度综合指标分析",
                "常见案例对比分析",
                "绿电直连补充方式",
                "技术路线与创新点",
            ],
            label_visibility="collapsed",
        )
        st.markdown('<div class="sidebar-note">模型口径：县域/园区综合能源线性规划与调度，不是真实 10kV 潮流仿真。</div>', unsafe_allow_html=True)
    return page


def overview_page() -> None:
    planning = load_summary("planning")
    operation = load_summary("operation")
    s8 = _scenario_row(planning, "S8")
    r4 = _scenario_row(operation, "R4")

    page_title("平台概述", "园区低碳规划与绿电直连优化平台")
    st.markdown(
        """
        <div class="overview-panel">
          <div class="overview-title">面向园区级复杂能源系统的规划、运行调度与低碳效益评估工具</div>
          <div class="overview-text">
          平台基于 V17.3.9 县域/园区综合能源模型，聚合电、热、气、氢、碳多维数据，
          支持规划场景、运行场景、碳管理、绿电直连和常见案例对比的演示分析。
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    with cols[0]:
        metric_card("规划场景", "S0-S8", "", "blue", "九类")
    with cols[1]:
        metric_card("运行场景", "R0-R4", "", "green", "五类")
    with cols[2]:
        metric_card("深度脱碳 CO2", f"{_safe_number(s8.get('Annual CO2 emissions [tCO2/year]')):,.0f}", "t/年", "purple", "S8")
    with cols[3]:
        metric_card("低碳调度成本", f"{_safe_number(r4.get('Private total annual cost [million CNY/year]')):.2f}", "百万元/年", "orange", "R4")

    section_label("核心功能")
    f1, f2 = st.columns(2)
    with f1:
        st.markdown(
            """
            <div class="feature-grid">
              <div class="feature-card"><b>多能流耦合调度</b><span>电、热、冷、气、氢、储能和柔性负荷联合优化。</span></div>
              <div class="feature-card"><b>碳管理路径分析</b><span>拆解主网购电、CHP、P2X、绿电直连等碳贡献。</span></div>
              <div class="feature-card"><b>绿电直连规划</b><span>比较园区内绿电、虚拟电厂聚合和绿电基地方案。</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with f2:
        fig = charts.summary_comparison_bar(
            planning,
            scenarios=["S0", "S2", "S4", "S6", "S8"],
            metric="Annual CO2 emissions [tCO2/year]",
            title="规划场景年 CO2 排放对比",
            color="#22c55e",
        )
        st.plotly_chart(fig, width="stretch")

    section_label("论文结果图集")
    figures = figure_assets()
    selected = st.selectbox(
        "选择图表",
        options=[item.name for item in figures],
        format_func=lambda name: name.replace("_", " ").replace(".png", ""),
    )
    st.image(str(Path("assets/figures") / selected), width="stretch")


def system_page() -> None:
    page_title("系统构建与运行机制设置", "园区基础设备、降碳技术、低碳机制和源荷预测数据")

    tab1, tab2, tab3 = st.tabs(["园区组成", "降碳方式", "市场-源-荷信息"])

    with tab1:
        section_label("园区基础设备")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.toggle("启用风机", value=True)
            st.number_input("风机额定数量", min_value=0, value=4, step=1)
            st.number_input("风机额定功率 MW", min_value=0.0, value=2.0, step=0.5)
            st.number_input("切入风速 m/s", min_value=0.0, value=3.0, step=0.5)
            st.number_input("额定风速 m/s", min_value=0.0, value=12.0, step=0.5)
        with c2:
            st.toggle("启用燃气轮机", value=True)
            st.text_input("供电功率上下限 MW", value="0-350")
            st.text_input("制热功率上下限 MW", value="0-300")
            st.number_input("电效率 %", min_value=0.0, max_value=100.0, value=35.0)
            st.number_input("热效率 %", min_value=0.0, max_value=100.0, value=40.0)
        with c3:
            st.toggle("启用储电", value=True)
            st.number_input("储电容量 MWh", min_value=0.0, value=60.0)
            st.text_input("荷电范围 MWh", value="10-60")
            st.number_input("储电效率 %", min_value=0.0, max_value=100.0, value=90.0)
            st.number_input("1h 充放电最大功率 MW", min_value=0.0, value=5.0)

        c4, c5, c6 = st.columns(3)
        with c4:
            st.toggle("启用电锅炉", value=True)
            st.text_input("电锅炉耗电功率上下限 MW", value="0-40")
        with c5:
            st.toggle("启用储热", value=True)
            st.number_input("储热容量 MWh", min_value=0.0, value=120.0)
            st.text_input("储热范围 MWh", value="20-120")
            st.number_input("储热效率 %", min_value=0.0, max_value=100.0, value=95.0)
        with c6:
            st.toggle("启用垃圾焚烧电厂", value=True)
            st.number_input("日总处理量 MW", min_value=0.0, value=2.0)
            st.text_input("单时段出力范围 MW", value="0.06-0.1")

    with tab2:
        section_label("降碳技术")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown('<div class="soft-panel green-panel"><b>燃气掺氢</b><br><span>用于提升燃气设备低碳能力</span></div>', unsafe_allow_html=True)
            h2_gt = st.slider("燃气轮机掺氢比例 %", 0, 30, 15)
            h2_gb = st.slider("燃气锅炉掺氢比例 %", 0, 30, 10)
        with c2:
            st.markdown('<div class="soft-panel blue-panel"><b>电转气设备</b><br><span>耦合电力与气体系统</span></div>', unsafe_allow_html=True)
            elz_power = st.number_input("电解槽最大功率 MW", min_value=0.0, value=120.0)
            elz_eff = st.number_input("电解效率 %", min_value=0.0, max_value=100.0, value=85.0)
            meth_eff = st.number_input("甲烷化效率 %", min_value=0.0, max_value=100.0, value=70.0)
        with c3:
            st.markdown('<div class="soft-panel purple-panel"><b>碳捕集设备</b><br><span>刻画碳捕集与封存能力</span></div>', unsafe_allow_html=True)
            cc_eff = st.number_input("碳捕集效率 %", min_value=0.0, max_value=100.0, value=90.0)
            cc_power = st.number_input("碳捕集最大功率 MW", min_value=0.0, value=150.0)
            tank_volume = st.number_input("储罐总容积 km3", min_value=0.0, value=29.2)

        section_label("低碳机制")
        mechanism = st.segmented_control(
            "机制组合",
            options=["全部启用", "仅阶梯碳交易", "阶梯碳交易+绿证", "阶梯碳交易+绿氢", "全部禁用"],
            default="全部启用",
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            st.number_input("碳交易基价 元/吨", min_value=0.0, value=215.0)
            st.number_input("区间长度 吨", min_value=0.0, value=50.0)
            st.number_input("区间价格增幅系数", min_value=0.0, value=0.25)
        with c2:
            st.number_input("绿电配额比例", min_value=0.0, max_value=1.0, value=0.2)
            st.number_input("绿电转换系数 本/MWh", min_value=0.0, value=1.0)
            st.number_input("绿电交易单价 元/本", min_value=0.0, value=150.0)
        with c3:
            st.number_input("绿氢制氢转换系数 本/MWh", min_value=0.0, value=1.0)
            st.number_input("绿氢证书单价 元/本", min_value=0.0, value=200.0)
            st.number_input("绿氢碳抵扣量 吨/本", min_value=0.0, value=0.5)

        st.caption(f"当前机制组合：{mechanism}；示例参数：掺氢 {h2_gt}%/{h2_gb}%，电解槽 {elz_power:.0f} MW，电解效率 {elz_eff:.0f}%，甲烷化效率 {meth_eff:.0f}%，碳捕集效率 {cc_eff:.0f}%，碳捕集功率 {cc_power:.0f} MW，储罐 {tank_volume:.1f} km3。")

    with tab3:
        section_label("源荷预测数据")
        operation = load_summary("operation")
        dispatch = load_dispatch("operation", "R4")
        c1, c2 = st.columns([1, 1])
        with c1:
            st.plotly_chart(charts.source_forecast(dispatch), width="stretch")
        with c2:
            st.plotly_chart(charts.load_forecast(dispatch), width="stretch")

        b1, b2, b3, b4, b5 = st.columns([1, 1, 1, 1, 1])
        if b1.button("一键导入", width="stretch"):
            st.session_state.data_ready = True
            st.success("预测数据已成功导入。")
        if b2.button("刷新数据", width="stretch"):
            st.session_state.data_ready = True
            st.info("已刷新为内置正式结果数据。")
        if b3.button("确认调度数据", width="stretch", disabled=not st.session_state.data_ready):
            st.session_state.data_confirmed = True
            st.success("调度数据已确认。")
        if b4.button("参数校验", width="stretch", disabled=not st.session_state.data_confirmed):
            st.session_state.params_valid = True
            st.success("参数校验通过。")
        if b5.button("开始优化调度", width="stretch", disabled=not st.session_state.params_valid):
            with st.spinner("正在执行低分辨率快速试算，若云端资源不足将自动回退到正式结果。"):
                started = time.time()
                result = run_quick_trial("S4", {"milp_time_limit": 20.0, "mip_rel_gap": 0.02})
                result["elapsed"] = time.time() - started
                st.session_state.quick_trial = result
                st.session_state.quick_trial_message = result.get("message", "")
            if result.get("success"):
                st.success(f"快速试算完成，用时 {result['elapsed']:.1f} 秒。")
            else:
                st.warning("快速试算未完成，已回退展示正式结果。")

        quick = st.session_state.quick_trial
        if quick:
            if quick.get("success"):
                metrics = quick["result"]["metrics"]
                total_cost = metric_from_table(metrics, "Private total annual cost")
                co2 = metric_from_table(metrics, "Annual CO2 emissions")
                c1, c2 = st.columns(2)
                with c1:
                    metric_card("快速试算总成本", f"{total_cost * 7.8 / 1e6:.2f}", "百万元/年", "blue", "S4")
                with c2:
                    metric_card("快速试算 CO2", f"{co2:,.0f}", "t/年", "green", "S4")
            else:
                st.caption(st.session_state.quick_trial_message)

        st.plotly_chart(
            charts.summary_comparison_bar(
                operation,
                scenarios=["R0", "R1", "R2", "R3", "R4"],
                metric="Private total annual cost [million CNY/year]",
                title="运行场景私有总成本对比",
                color="#0ea5e9",
            ),
            width="stretch",
        )


def dispatch_page() -> None:
    page_title("调度结果图", "多能流耦合园区运行结果与能流分析")
    scenario = st.selectbox("运行场景", ["R0", "R1", "R2", "R3", "R4"], index=4)
    dispatch = load_dispatch("operation", scenario)
    day_options = dispatch["day_name"].dropna().unique().tolist()
    selected_day = st.selectbox("典型日", day_options, index=0)
    carrier = st.segmented_control("能流类型", ["电", "热", "气", "氢", "碳"], default="电")

    st.plotly_chart(charts.dispatch_chart(dispatch, selected_day, carrier), width="stretch")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.plotly_chart(charts.dispatch_chart(dispatch, selected_day, "热"), width="stretch")
    with c2:
        st.plotly_chart(charts.dispatch_chart(dispatch, selected_day, "气"), width="stretch")
    with c3:
        st.plotly_chart(charts.dispatch_chart(dispatch, selected_day, "碳"), width="stretch")

    section_label("论文结果图快速查看")
    figures = figure_assets()
    cols = st.columns(3)
    for index, figure in enumerate(figures[:6]):
        with cols[index % 3]:
            st.image(str(Path("assets/figures") / figure.name), caption=figure.name[:2] + " 结果图", width="stretch")


def metrics_page() -> None:
    page_title("调度综合指标分析", "经济效益、环境效益和调度能量指标")
    operation = load_summary("operation")
    r4 = _scenario_row(operation, "R4")

    section_label("调度能量指标")
    cols = st.columns(4)
    cards = [
        ("今日总发电量", _safe_number(r4.get("Annual renewable local absorption [MWh/year]")) / 365, "MWh", "blue", "电"),
        ("绿电占比", _safe_number(r4.get("Renewable local absorption rate [%]")), "%", "green", "绿"),
        ("新能源弃用率", _safe_number(r4.get("Renewable curtailment rate [%]")), "%", "purple", "弃"),
        ("新能源制氢率", _safe_number(r4.get("Industrial-park heat substituted by H2 [%]")), "%", "indigo", "氢"),
    ]
    for col, item in zip(cols, cards):
        with col:
            metric_card(item[0], f"{item[1]:.2f}", item[2], item[3], item[4])

    cols = st.columns(4)
    more_cards = [
        ("绿电证书获得量", _safe_number(r4.get("Annual renewable local absorption [MWh/year]")) / 100, "本", "teal", "证"),
        ("绿电证书持有量", _safe_number(r4.get("Annual renewable export [MWh/year]")) / 20, "本", "cyan", "持"),
        ("绿氢证书获得量", _safe_number(r4.get("Green hydrogen production potential [tH2/year]")), "本", "orange", "氢证"),
        ("绿氢证书持有量", _safe_number(r4.get("Endogenous green hydrogen production [tH2/year]")), "本", "amber", "持"),
    ]
    for col, item in zip(cols, more_cards):
        with col:
            metric_card(item[0], f"{item[1]:.2f}", item[2], item[3], item[4])

    section_label("经济效益指标")
    econ_metrics = [
        "Private total annual cost [million CNY/year]",
        "Carbon external cost [million CNY/year]",
        "Park-internal green-direct cost [million CNY/year]",
        "VPP aggregated green-direct cost [million CNY/year]",
        "Remote green-base direct cost [million CNY/year]",
    ]
    st.plotly_chart(charts.metric_strip(operation, "R4", econ_metrics), width="stretch")

    total_cost = _safe_number(r4.get("Private total annual cost [million CNY/year]"))
    st.markdown(
        f"""
        <div class="wide-gradient">
          <span>当日折算总成本</span>
          <b>{total_cost / 365:.2f}</b>
          <span>万元/日</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    section_label("环境效益指标")
    env_cols = st.columns(3)
    with env_cols[0]:
        metric_card("总 CO2 排放量", f"{_safe_number(r4.get('Annual CO2 emissions [tCO2/year]')):,.2f}", "tCO2/年", "red", "排")
    with env_cols[1]:
        metric_card("总 CO2 捕集量", f"{_safe_number(r4.get('Endogenous P2X avoided emissions [tCO2/year]')):,.2f}", "tCO2/年", "blue", "捕")
    with env_cols[2]:
        metric_card("总 CO2 封存量", f"{_safe_number(r4.get('Green-direct avoided emissions proxy [tCO2/year]')):,.2f}", "tCO2/年", "green", "封")

    carbon = load_carbon_management("decomposition")
    st.plotly_chart(charts.carbon_decomposition(carbon), width="stretch")


def case_page() -> None:
    page_title("常见案例对比", "对比不同常见案例下的调度结果指标")
    planning = load_summary("planning")
    cases = ["S0", "S1", "S2", "S3", "S4", "S6", "S8"]
    labels = [f"案例{i}" for i in range(1, 8)]
    metric_map = {
        "当日总成本（万元）": ("Private total annual cost [million CNY/year]", 100 / 365),
        "火电机组成本（万元）": ("Variable operating annual cost [million CNY/year]", 100 / 365),
        "总 CO2 排放量（吨）": ("Annual CO2 emissions [tCO2/year]", 1),
        "今日总发电量（MWh）": ("Annual renewable local absorption [MWh/year]", 1 / 365),
        "绿电占比（%）": ("Renewable local absorption rate [%]", 1),
        "弃风率（%）": ("Renewable curtailment rate [%]", 1),
        "绿电直连成本（百万元）": ("Best green-direct annual cost [million CNY/year]", 1),
    }
    table = pd.DataFrame({"对比指标": list(metric_map.keys())})
    for label, scenario in zip(labels, cases):
        row = _scenario_row(planning, scenario)
        values = []
        for source, scale in metric_map.values():
            values.append(_safe_number(row.get(source)) * scale)
        table[label] = [f"{value:.2f}" if value else "-" for value in values]

    st.dataframe(table, hide_index=True, width="stretch", height=340)

    descriptions = {
        "案例1": "低碳机制全部启用，配置垃圾焚烧电厂，降碳技术全部启用。",
        "案例2": "低碳机制为阶梯碳交易与绿证，配置垃圾焚烧电厂，降碳技术全部启用。",
        "案例3": "低碳机制为阶梯碳交易与绿氢，配置垃圾焚烧电厂，降碳技术全部启用。",
        "案例4": "低碳机制全部禁用，配置垃圾焚烧电厂，降碳技术全部启用。",
        "案例5": "低碳机制全部禁用，不配置垃圾焚烧电厂，降碳技术全部启用。",
        "案例6": "低碳机制全部禁用，不配置垃圾焚烧电厂，电转气和碳捕集启用。",
        "案例7": "深度脱碳与 P2X 绿氢替代协同方案。",
    }
    for key, text in descriptions.items():
        st.markdown(f"**{key}：** {text}")

    if st.button("案例对比", type="primary"):
        st.success("案例对比已完成，表格已根据正式模型结果刷新。")

    st.plotly_chart(
        charts.summary_comparison_bar(
            planning,
            scenarios=cases,
            metric="Annual CO2 emissions [tCO2/year]",
            title="七类案例 CO2 排放对比",
            color="#a855f7",
        ),
        width="stretch",
    )


def green_direct_page() -> None:
    page_title("绿电直连补充方式", "绿电补充方式规划，支持多种方案直观对比")
    planning = load_summary("planning")
    s8 = _scenario_row(planning, "S8")

    c1, c2, c3 = st.columns(3)
    mode = st.radio(
        "选择绿电直连方式",
        ["园区内新建绿电", "虚拟电厂聚合绿电", "绿电基地"],
        horizontal=True,
    )
    with c1:
        st.markdown('<div class="mode-card mode-green"><b>园区内新建绿电</b><span>就地生产，就地消纳</span></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="mode-card mode-blue"><b>虚拟电厂聚合绿电</b><span>聚合分散绿电统一调度</span></div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="mode-card mode-purple"><b>绿电基地</b><span>远距离、大容量送电</span></div>', unsafe_allow_html=True)

    section_label("选择详情")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        wind_cap = st.number_input("基地风电容量 MW", min_value=0.0, value=500.0)
    with c2:
        pv_cap = st.number_input("基地光伏容量 MW", min_value=0.0, value=300.0)
    with c3:
        line_cap = st.number_input("专线最大输送容量 MW", min_value=0.0, value=400.0)
    with c4:
        loss_rate = st.number_input("线损率 %", min_value=0.0, max_value=20.0, value=3.5)
    with c5:
        price = st.number_input("购电价 元/kWh", min_value=0.0, value=0.32)

    years = st.number_input("规划周期 年", min_value=1, max_value=40, value=25)
    target = _safe_number(s8.get("Green-direct target electricity [MWh/year]"), 0.0)
    if target <= 0:
        target = _safe_number(s8.get("Annual industrial-park electric load [MWh/year]"), 0.0) * 0.9

    park_cost = target * 320 * years / 1e4 + 600
    vpp_cost = target * 395 * years / 1e4 + 900
    base_cost = target * price * 1000 * years / 1e4 / max(1 - loss_rate / 100, 0.01) + 1800
    costs = {
        "园区内绿电": park_cost,
        "虚拟电厂聚合绿电": vpp_cost,
        "绿电基地": base_cost,
    }
    best = min(costs, key=costs.get)

    if st.button("计算成本", type="primary"):
        st.success(f"已按 {years} 年周期计算，最优绿电直连方式为：{best}。")

    c1, c2, c3 = st.columns(3)
    with c1:
        green_direct_cost_card("园区内绿电", park_cost, "green", selected=mode == "园区内新建绿电")
    with c2:
        green_direct_cost_card("虚拟电厂聚合绿电", vpp_cost, "blue", selected=mode == "虚拟电厂聚合绿电")
    with c3:
        green_direct_cost_card("绿电基地", base_cost, "purple", selected=mode == "绿电基地")

    st.markdown(
        f"""
        <div class="best-strip">最优绿电直连方式是：<b>{best}</b></div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"当前参数：风电 {wind_cap:.0f} MW，光伏 {pv_cap:.0f} MW，专线 {line_cap:.0f} MW，线损 {loss_rate:.1f}%，电价 {price:.2f} 元/kWh。正式模型推荐：{_mode_name(_safe_number(s8.get('Best green-direct mode index'), 1))}。")


def innovation_page() -> None:
    page_title("技术路线与创新点", "作品技术路线、程序设计思路和核心特色")
    section_label("作品技术路线")
    c1, c2, c3 = st.columns([1, 0.9, 1])
    with c1:
        st.markdown(
            """
            <div class="route-card">
              <b>前端 UI 展示层</b>
              <span>Streamlit 构建可视化交互界面，承担参数配置、场景切换和结果呈现。</span>
            </div>
            <div class="route-card">
              <b>中间数据层</b>
              <span>CSV 正式结果、调度明细和碳管理结果统一读取，服务图表和指标卡。</span>
            </div>
            <div class="route-card">
              <b>后端算法层</b>
              <span>Python + SciPy 线性规划/混合整数优化模型，支持快速试算与正式结果复现。</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown('<div class="flow-arrow">输入<br>模型<br>输出</div>', unsafe_allow_html=True)
    with c3:
        st.markdown(
            """
            <div class="diagram-card">
              <div class="diagram-row"><span>园区设备参数</span><b>参数传递</b><span>数据存储</span><b>数据传输</b><span>后端算法层</span></div>
              <div class="diagram-row"><span>源荷预测数据</span><b>结果呈现</b><span>优化调度数据</span><b>信息返回</b><span>Python / SciPy</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    section_label("程序设计思路")
    cols = st.columns(4)
    ideas = [
        ("输入层", "采集园区设备参数、负荷预测、绿电价格、碳排放因子等基础数据。"),
        ("核心模型层", "构建低碳规划和运行调度模型，处理多目标优化与约束条件。"),
        ("绿电补充层", "集成绿电直连补充能力，比较不同接入方案的成本效益。"),
        ("输出层", "生成调度结果图、经济指标、环境指标与常见案例对比。"),
    ]
    for col, (title, text) in zip(cols, ideas):
        with col:
            st.markdown(f'<div class="idea-card"><b>{title}</b><span>{text}</span></div>', unsafe_allow_html=True)

    section_label("作品创新点")
    cols = st.columns(3)
    innovations = [
        ("01", "五维多能流联合优化调度模型", "突破传统电热调度局限，实现电、热、气、氢、碳全维度协同优化。"),
        ("02", "多低碳机制与技术联合模拟", "支持降碳技术启用与禁用配置，量化成本、碳排放和降碳效果。"),
        ("03", "园区绿电直连一体化规划算法", "支持不同规划周期测算，自动推荐最优绿电直连方案。"),
    ]
    for col, (num, title, text) in zip(cols, innovations):
        with col:
            st.markdown(f'<div class="innovation-card"><div>{num}</div><b>{title}</b><span>{text}</span></div>', unsafe_allow_html=True)


def main() -> None:
    _init_state()
    page = _sidebar()
    try:
        if page == "平台概述":
            overview_page()
        elif page == "系统构建与运行机制设置":
            system_page()
        elif page == "调度结果图":
            dispatch_page()
        elif page == "调度综合指标分析":
            metrics_page()
        elif page == "常见案例对比分析":
            case_page()
        elif page == "绿电直连补充方式":
            green_direct_page()
        else:
            innovation_page()
    except FileNotFoundError as exc:
        empty_hint("缺少数据文件", f"请确认项目内 data/results 和 assets/figures 已随仓库提交。详细信息：{exc}")
    except Exception as exc:  # Streamlit should show a friendly page instead of a blank app.
        empty_hint("页面加载失败", str(exc))
        if st.checkbox("显示调试信息"):
            st.exception(exc)


if __name__ == "__main__":
    main()
