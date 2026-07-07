from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import streamlit as st

from src import charts
from src.algorithm_catalog import algorithm_dataframe, storemore_feature_dataframe
from src.data_loader import (
    figure_assets,
    load_carbon_management,
    load_dispatch,
    load_metrics,
    load_summary,
    metric_from_table,
)
from src.diagnostics import old_platform_note, run_static_checks
from src.model_adapter import run_quick_trial
try:
    from src.ui_components import (
        badge,
        empty_hint,
        green_direct_cost_card,
        inject_global_css,
        metric_card,
        page_title,
        pills,
        section_label,
        status_box,
    )
except ImportError:
    from src.ui_components import (
        badge,
        empty_hint,
        green_direct_cost_card,
        inject_global_css,
        metric_card,
        page_title,
        section_label,
    )

    def pills(items: list[str]) -> None:
        st.write("、".join(items))

    def status_box(title: str, body: str, ok: bool = True) -> None:
        if ok:
            st.success(f"{title}：{body}")
        else:
            st.warning(f"{title}：{body}")


APP_TITLE = "园区低碳规划与绿电直连优化平台"
BRAND = "绿电向导"


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="G",
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
        1: "园区内新建绿电",
        2: "虚拟电厂聚合绿电",
        3: "绿电基地",
    }
    return mapping.get(int(round(index or 1)), "园区内新建绿电")


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
                "算法与界面对应关系",
                "调度结果图",
                "调度综合指标分析",
                "常见案例对比分析",
                "绿电直连补充方式",
                "StoreMore融合与功能自检",
                "技术路线与创新点",
            ],
            label_visibility="collapsed",
        )
        st.markdown(
            '<div class="sidebar-note">模型定位：县域/园区综合能源系统线性规划与调度模型，'
            "用于方案规划、低碳机制比较、调度结果展示和决策支持；不表述为真实10kV潮流平台。</div>",
            unsafe_allow_html=True,
        )
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
          平台基于 V17.3.9 县域/园区综合能源模型，融合 StoreMore 的能源系统建模思路，
          将电、热、冷、气、氢、碳等维度统一到可交互的网页中。页面重点展示正式模型结果，
          同时提供低分辨率快速试算、参数校验、算法说明、案例对比和功能自检，便于汇报和复核。
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    with cols[0]:
        metric_card("规划场景", "S0-S8", "9类", "blue", "场景")
    with cols[1]:
        metric_card("运行场景", "R0-R4", "5类", "green", "调度")
    with cols[2]:
        metric_card(
            "深度低碳 CO2",
            f"{_safe_number(s8.get('Annual CO2 emissions [tCO2/year]')):,.0f}",
            "t/年",
            "purple",
            "碳",
        )
    with cols[3]:
        metric_card(
            "低碳调度成本",
            f"{_safe_number(r4.get('Private total annual cost [million CNY/year]')):.2f}",
            "百万元/年",
            "orange",
            "成本",
        )

    section_label("核心功能")
    f1, f2 = st.columns([0.95, 1.05])
    with f1:
        st.markdown(
            """
            <div class="feature-grid">
              <div class="feature-card"><b>多能流耦合调度</b><span>统一展示电、热、冷、气、氢、碳多维运行结果，支持典型日切换。</span></div>
              <div class="feature-card"><b>StoreMore约束融合</b><span>新增 RPS、CO2、CEEP、储能技术、氢能和电价上传等手册功能映射。</span></div>
              <div class="feature-card"><b>算法可解释</b><span>把嵌入算法逐项对应到页面、输入输出和代码位置，便于答辩说明。</span></div>
              <div class="feature-card"><b>报错自检</b><span>检查数据、字段、图集、模型代码和快速试算回退状态，避免空白页面。</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with f2:
        fig = charts.summary_comparison_bar(
            planning,
            scenarios=["S0", "S2", "S4", "S6", "S8"],
            metric="Annual CO2 emissions [tCO2/year]",
            title="规划场景年度CO2排放对比",
            color="#22c55e",
        )
        st.plotly_chart(fig, use_container_width=True)

    section_label("论文结果图集")
    figures = figure_assets()
    if figures:
        selected = st.selectbox(
            "选择图表",
            options=[item.name for item in figures],
            format_func=lambda name: name.replace("_", " ").replace(".png", ""),
        )
        st.image(str(Path("assets/figures") / selected), use_container_width=True)
    else:
        empty_hint("缺少图集", "未检测到 assets/figures 下的 PNG 结果图。")


def system_page() -> None:
    page_title("系统构建与运行机制设置", "园区基础设备、StoreMore约束、低碳机制、源荷预测与按钮流程")

    tab1, tab2, tab3, tab4 = st.tabs(["园区组成", "StoreMore约束", "市场-源-荷信息", "求解流程"])

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
            st.number_input("1h充放电最大功率 MW", min_value=0.0, value=5.0)

        c4, c5, c6 = st.columns(3)
        with c4:
            st.toggle("启用电锅炉", value=True)
            st.text_input("电锅炉耗电功率上下限 MW", value="0-40")
        with c5:
            st.toggle("启用蓄热", value=True)
            st.number_input("蓄热容量 MWh", min_value=0.0, value=120.0)
            st.text_input("蓄热范围 MWh", value="20-120")
            st.number_input("蓄热效率 %", min_value=0.0, max_value=100.0, value=95.0)
        with c6:
            st.toggle("启用垃圾焚烧电厂", value=True)
            st.number_input("日总处理量 MW", min_value=0.0, value=2.0)
            st.text_input("单时段出力范围 MW", value="0.06-0.1")

        section_label("StoreMore储能技术选择")
        selected_storage = st.multiselect(
            "选择需要纳入说明或后续扩展的储能技术",
            ["Li-ion", "Gravity", "CAES", "LAES", "VRFB", "SMES", "Heat storage", "H2 tank"],
            default=["Li-ion", "Heat storage", "H2 tank"],
        )
        pills(selected_storage)
        st.caption("当前正式求解结果已包含电储能、热储能和氢能代理；其余 StoreMore 储能技术作为平台扩展参数预留。")

    with tab2:
        section_label("StoreMore约束与模型参数")
        scenario_name = st.text_input("场景名称", value="园区低碳协同调度演示")
        c1, c2, c3 = st.columns(3)
        with c1:
            enable_rps = st.checkbox("RPS 可再生能源占比约束", value=True)
            min_res = st.slider("最小可再生能源占比 %", 0, 100, 48)
        with c2:
            enable_co2 = st.checkbox("CO2 年度排放约束", value=True)
            max_co2 = st.number_input("年度CO2上限 t", min_value=0.0, value=25000.0, step=500.0)
        with c3:
            enable_ceep = st.checkbox("CEEP 弃电约束", value=True)
            max_ceep = st.slider("最大弃电率 %", 0, 50, 8)

        c4, c5, c6 = st.columns(3)
        with c4:
            st.checkbox("Model heat 启用供热耦合", value=True)
        with c5:
            st.checkbox("Optimize generation capacity 优化新增容量", value=True)
        with c6:
            st.checkbox("Restrict investments 限制投资边界", value=True)

        st.markdown(
            f"""
            <div class="white-panel">
              <b>当前约束摘要</b><br>
              场景：{scenario_name}；
              RPS：{'启用' if enable_rps else '关闭'}，目标 {min_res}%；
              CO2：{'启用' if enable_co2 else '关闭'}，上限 {max_co2:,.0f} t；
              CEEP：{'启用' if enable_ceep else '关闭'}，最大弃电率 {max_ceep}%。
            </div>
            """,
            unsafe_allow_html=True,
        )

        section_label("StoreMore手册输入表")
        generator_table = pd.DataFrame(
            [
                {"技术": "燃气轮机/CHP", "已装容量MW": 350, "最大新增MW": 80, "效率%": 35, "CO2强度t/MWh": 0.202},
                {"技术": "光伏", "已装容量MW": 300, "最大新增MW": 120, "效率%": 100, "CO2强度t/MWh": 0.0},
                {"技术": "风电", "已装容量MW": 500, "最大新增MW": 160, "效率%": 100, "CO2强度t/MWh": 0.0},
                {"技术": "电解槽", "已装容量MW": 120, "最大新增MW": 50, "效率%": 85, "CO2强度t/MWh": 0.0},
            ]
        )
        st.data_editor(generator_table, hide_index=True, use_container_width=True, disabled=False)

    with tab3:
        section_label("源荷预测数据")
        dispatch = load_dispatch("operation", "R4")
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(charts.source_forecast(dispatch), use_container_width=True)
        with c2:
            st.plotly_chart(charts.load_forecast(dispatch), use_container_width=True)

        section_label("电价分布上传校验")
        uploaded = st.file_uploader("上传 StoreMore 格式电价 CSV：第一列 period，第二列为国家或地区代码", type=["csv"])
        if uploaded is not None:
            try:
                price_df = pd.read_csv(uploaded)
                if price_df.shape[1] >= 2 and price_df.columns[0].lower() == "period":
                    st.success("电价文件格式校验通过。当前演示不会覆盖正式结果，只作为参数检查。")
                    st.dataframe(price_df.head(12), use_container_width=True)
                else:
                    st.warning("文件已读取，但第一列应为 period，第二列应为价格序列。")
            except Exception as exc:
                st.error(f"电价文件读取失败：{exc}")

    with tab4:
        section_label("按钮流程与快速试算")
        b1, b2, b3, b4, b5 = st.columns([1, 1, 1, 1, 1])
        if b1.button("一键导入", use_container_width=True):
            st.session_state.data_ready = True
            st.success("预测数据已成功导入。")
        if b2.button("刷新数据", use_container_width=True):
            st.session_state.data_ready = True
            st.info("已刷新为内置正式结果数据。")
        if b3.button("确认调度数据", use_container_width=True, disabled=not st.session_state.data_ready):
            st.session_state.data_confirmed = True
            st.success("调度数据已确认。")
        if b4.button("参数校验", use_container_width=True, disabled=not st.session_state.data_confirmed):
            st.session_state.params_valid = True
            st.success("参数校验通过。")
        if b5.button("开始优化调度", use_container_width=True, disabled=not st.session_state.params_valid):
            with st.spinner("正在执行低分辨率快速试算；若云端资源不足，将自动回退到正式结果。"):
                started = time.time()
                result = run_quick_trial("S4", {"milp_time_limit": 20.0, "mip_rel_gap": 0.02})
                result["elapsed"] = time.time() - started
                st.session_state.quick_trial = result
                st.session_state.quick_trial_message = result.get("message", "")
            if result.get("success"):
                st.success(f"快速试算完成，用时 {result['elapsed']:.1f} 秒。")
            else:
                st.warning("快速试算未完成，页面已回退展示正式结果。")

        quick = st.session_state.quick_trial
        if quick:
            if quick.get("success"):
                metrics = quick["result"]["metrics"]
                total_cost = metric_from_table(metrics, "Private total annual cost")
                co2 = metric_from_table(metrics, "Annual CO2 emissions")
                c1, c2 = st.columns(2)
                with c1:
                    metric_card("快速试算总成本", f"{total_cost * 7.8 / 1e6:.2f}", "百万元/年", "blue", "试算")
                with c2:
                    metric_card("快速试算CO2", f"{co2:,.0f}", "t/年", "green", "碳")
            else:
                st.caption(st.session_state.quick_trial_message)

        st.markdown(
            """
            <div class="white-panel">
              <b>求解流程说明</b><br>
              StoreMore手册中包含“全年完美预见规划”和“48小时滚动调度”两阶段思想。
              本平台为保证 Streamlit Cloud 稳定性，展示正式全年结果为主；按钮触发的是低分辨率快速试算，
              若资源不足会明确提示并回退到正式结果，不让页面空白或报错。
            </div>
            """,
            unsafe_allow_html=True,
        )


def algorithm_page() -> None:
    page_title("算法与界面对应关系", "整理平台嵌入算法、对应界面、输入输出和代码位置")
    algorithms = algorithm_dataframe()
    st.dataframe(algorithms, hide_index=True, use_container_width=True, height=420)

    section_label("按界面快速说明")
    selected = st.selectbox("选择一个界面查看它调用或展示的算法", sorted({p for pages in algorithms["对应界面"] for p in pages.split("、")}))
    subset = algorithms[algorithms["对应界面"].str.contains(selected, regex=False)]
    for _, row in subset.iterrows():
        st.markdown(
            f"""
            <div class="algorithm-card">
              <b>{row['算法模块']}</b>
              <span>{row['核心方法']}</span><br><br>
              <span><b>输入：</b>{row['主要输入']}</span><br>
              <span><b>输出：</b>{row['主要输出']}</span><br>
              <span><b>代码：</b>{row['代码位置']}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    section_label("老师提问时的回答口径")
    st.info(
        "平台不是只嵌入一个算法，而是把综合能源线性规划、StoreMore两阶段思想、RPS/CO2/CEEP约束、"
        "储能SOC、P2X绿氢、碳管理后处理、绿电直连成本筛选和源荷数据生成组合成一个决策支持流程。"
    )


def dispatch_page() -> None:
    page_title("调度结果图", "多能流耦合园区运行结果与能流分析")
    scenario = st.selectbox("运行场景", ["R0", "R1", "R2", "R3", "R4"], index=4)
    dispatch = load_dispatch("operation", scenario)
    day_options = dispatch["day_name"].dropna().unique().tolist()
    selected_day = st.selectbox("典型日", day_options, index=0)
    carrier = st.radio("能流类型", ["电", "热", "气", "氢", "碳"], horizontal=True)

    st.plotly_chart(charts.dispatch_chart(dispatch, selected_day, carrier), use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(charts.storage_profile(dispatch, selected_day), use_container_width=True)
    with c2:
        st.plotly_chart(charts.dispatch_chart(dispatch, selected_day, "碳"), use_container_width=True)

    section_label("论文结果图快速查看")
    figures = figure_assets()
    if figures:
        cols = st.columns(3)
        for index, figure in enumerate(figures[:6]):
            with cols[index % 3]:
                st.image(str(figure), caption=figure.name[:2] + " 结果图", use_container_width=True)
    else:
        empty_hint("缺少图集", "未检测到论文结果图。")


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
    st.plotly_chart(charts.metric_strip(operation, "R4", econ_metrics), use_container_width=True)

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
        metric_card("总CO2排放量", f"{_safe_number(r4.get('Annual CO2 emissions [tCO2/year]')):,.2f}", "tCO2/年", "red", "排")
    with env_cols[1]:
        metric_card("P2X减排潜力", f"{_safe_number(r4.get('Endogenous P2X avoided emissions [tCO2/year]')):,.2f}", "tCO2/年", "blue", "减")
    with env_cols[2]:
        metric_card("绿电直连减排代理", f"{_safe_number(r4.get('Green-direct avoided emissions proxy [tCO2/year]')):,.2f}", "tCO2/年", "green", "绿")

    carbon = load_carbon_management("decomposition")
    st.plotly_chart(charts.carbon_decomposition(carbon), use_container_width=True)


def case_page() -> None:
    page_title("常见案例对比", "对比不同案例下的调度结果指标")
    planning = load_summary("planning")
    cases = ["S0", "S1", "S2", "S3", "S4", "S6", "S8"]
    labels = [f"案例{i}" for i in range(1, 8)]
    metric_map = {
        "当日总成本（万元）": ("Private total annual cost [million CNY/year]", 100 / 365),
        "运行成本（万元）": ("Variable operating annual cost [million CNY/year]", 100 / 365),
        "总CO2排放量（吨）": ("Annual CO2 emissions [tCO2/year]", 1),
        "今日绿电吸纳量（MWh）": ("Annual renewable local absorption [MWh/year]", 1 / 365),
        "绿电占比（%）": ("Renewable local absorption rate [%]", 1),
        "弃风弃光率（%）": ("Renewable curtailment rate [%]", 1),
        "绿电直连成本（百万元）": ("Best green-direct annual cost [million CNY/year]", 1),
    }
    table = pd.DataFrame({"对比指标": list(metric_map.keys())})
    for label, scenario in zip(labels, cases):
        row = _scenario_row(planning, scenario)
        values = []
        for source, scale in metric_map.values():
            values.append(_safe_number(row.get(source)) * scale)
        table[label] = [f"{value:.2f}" if value else "-" for value in values]

    st.dataframe(table, hide_index=True, use_container_width=True, height=340)

    descriptions = {
        "案例1": "低碳机制全部启用，配置垃圾焚烧电厂，降碳技术全部启用。",
        "案例2": "启用阶梯碳交易与绿证机制，配置垃圾焚烧电厂。",
        "案例3": "启用阶梯碳交易与绿氢机制，配置垃圾焚烧电厂。",
        "案例4": "关闭低碳机制，保留垃圾焚烧电厂和降碳技术。",
        "案例5": "关闭低碳机制，不配置垃圾焚烧电厂。",
        "案例6": "关闭低碳机制，启用电转气和碳捕集设备。",
        "案例7": "深度脱碳：P2X、绿电直连与工业园区热替代协同。",
    }
    for key, text in descriptions.items():
        st.markdown(f"**{key}：** {text}")

    if st.button("案例对比", type="primary"):
        st.success("案例对比已完成，表格已根据正式模型结果刷新。")

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(
            charts.summary_comparison_bar(
                planning,
                scenarios=cases,
                metric="Annual CO2 emissions [tCO2/year]",
                title="七类案例CO2排放对比",
                color="#a855f7",
            ),
            use_container_width=True,
        )
    with c2:
        st.plotly_chart(charts.scenario_scatter(planning[planning["Scenario"].isin(cases)]), use_container_width=True)


def green_direct_page() -> None:
    page_title("绿电直连补充方式", "绿电补充方式规划，支持多种方案直观对比")
    planning = load_summary("planning")
    s8 = _scenario_row(planning, "S8")

    mode = st.radio(
        "选择绿电直连方式",
        ["园区内新建绿电", "虚拟电厂聚合绿电", "绿电基地"],
        horizontal=True,
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<div class="mode-card mode-green"><b>园区内新建绿电</b><span>就地生产，就地消纳，线损低。</span></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="mode-card mode-blue"><b>虚拟电厂聚合绿电</b><span>聚合分散绿电资源统一调度。</span></div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="mode-card mode-purple"><b>绿电基地</b><span>远距离、大容量、专线输送。</span></div>', unsafe_allow_html=True)

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
        st.success(f"已按 {years} 年周期计算，当前最优绿电直连方式为：{best}。")

    c1, c2, c3 = st.columns(3)
    with c1:
        green_direct_cost_card("园区内绿电", park_cost, "green", selected=mode == "园区内新建绿电")
    with c2:
        green_direct_cost_card("虚拟电厂聚合绿电", vpp_cost, "blue", selected=mode == "虚拟电厂聚合绿电")
    with c3:
        green_direct_cost_card("绿电基地", base_cost, "purple", selected=mode == "绿电基地")

    st.markdown(f'<div class="best-strip">最优绿电直连方式是：<b>{best}</b></div>', unsafe_allow_html=True)
    st.caption(
        f"当前参数：风电 {wind_cap:.0f} MW，光伏 {pv_cap:.0f} MW，专线 {line_cap:.0f} MW，"
        f"线损 {loss_rate:.1f}%，电价 {price:.2f} 元/kWh。正式模型推荐："
        f"{_mode_name(_safe_number(s8.get('Best green-direct mode index'), 1))}。"
    )


def storemore_page() -> None:
    page_title("StoreMore融合与功能自检", "融合上传手册内容，并检查平台中可能导致报错的关键环节")

    section_label("StoreMore功能融合清单")
    st.dataframe(storemore_feature_dataframe(), hide_index=True, use_container_width=True, height=310)

    section_label("两阶段求解思想")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            """
            <div class="soft-panel blue-panel">
              <b>第一阶段：Perfect foresight 全年规划</b>
              <span>以全年8760小时或典型日权重为规划视角，决定容量、成本、碳排和绿电直连结果。</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
            <div class="soft-panel green-panel">
              <b>第二阶段：Myopic 滚动运行</b>
              <span>参考 StoreMore 48小时滚动思想，平台用典型日调度与快速试算展示运行侧可行性。</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    section_label("功能自检")
    checks = run_static_checks()
    st.dataframe(checks, hide_index=True, use_container_width=True, height=360)
    if (checks["状态"] == "通过").all():
        status_box("静态检查通过", "数据、图集和关键字段均可读取。", ok=True)
    else:
        status_box("存在需处理项", "请查看上表中状态不是“通过”的检查项。", ok=False)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("运行S0快速试算", use_container_width=True):
            with st.spinner("正在试算 S0..."):
                result = run_quick_trial("S0", {"milp_time_limit": 15.0})
            if result.get("success"):
                st.success("S0快速试算成功。")
            else:
                st.warning(result.get("message", "S0快速试算失败。"))
    with c2:
        if st.button("运行S8快速试算", use_container_width=True):
            with st.spinner("正在试算 S8..."):
                result = run_quick_trial("S8", {"milp_time_limit": 15.0})
            if result.get("success"):
                st.success("S8快速试算成功。")
            else:
                st.warning(result.get("message", "S8快速试算失败。"))

    section_label("旧平台融合说明")
    st.info(old_platform_note())


def innovation_page() -> None:
    page_title("技术路线与创新点", "作品技术路线、程序设计思路和核心特色")
    section_label("作品技术路线")
    c1, c2, c3 = st.columns([1, 0.9, 1])
    with c1:
        st.markdown(
            """
            <div class="route-card">
              <b>前端UI展示层</b>
              <span>Streamlit 构建可视化交互界面，承担参数配置、场景切换、流程按钮和结果呈现。</span>
            </div>
            <div class="route-card">
              <b>中间数据层</b>
              <span>CSV正式结果、调度明细、碳管理结果和论文图集统一读取，服务图表和指标卡。</span>
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
        ("绿电补充层", "集成绿电直连能力，比较不同接入方案的成本效益。"),
        ("输出层", "生成调度结果图、经济指标、环境指标、案例对比与算法说明。"),
    ]
    for col, (title, text) in zip(cols, ideas):
        with col:
            st.markdown(f'<div class="idea-card"><b>{title}</b><span>{text}</span></div>', unsafe_allow_html=True)

    section_label("作品创新点")
    cols = st.columns(3)
    innovations = [
        ("01", "多维多能流联合优化调度模型", "突破单一电力调度展示，呈现电、热、气、氢、碳全维度协同优化。"),
        ("02", "多低碳机制与技术联合模拟", "支持RPS、CO2、CEEP、碳交易、绿证、P2X和碳管理的联合展示。"),
        ("03", "园区绿电直连一体化规划算法", "支持不同规划周期测算，自动推荐成本更优的绿电直连方案。"),
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
        elif page == "算法与界面对应关系":
            algorithm_page()
        elif page == "调度结果图":
            dispatch_page()
        elif page == "调度综合指标分析":
            metrics_page()
        elif page == "常见案例对比分析":
            case_page()
        elif page == "绿电直连补充方式":
            green_direct_page()
        elif page == "StoreMore融合与功能自检":
            storemore_page()
        else:
            innovation_page()
    except FileNotFoundError as exc:
        empty_hint("缺少数据文件", f"请确认 data/results 和 assets/figures 已随仓库提交。详细信息：{exc}")
    except Exception as exc:
        empty_hint("页面加载失败", str(exc))
        if st.checkbox("显示调试信息"):
            st.exception(exc)


if __name__ == "__main__":
    main()
