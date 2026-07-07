from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


COLORWAY = ["#0ea5e9", "#22c55e", "#f59e0b", "#a855f7", "#06b6d4", "#ef4444"]


def _base_layout(fig: go.Figure, title: str | None = None, height: int = 420) -> go.Figure:
    fig.update_layout(
        title=title,
        template="plotly_white",
        colorway=COLORWAY,
        margin=dict(l=20, r=20, t=48 if title else 24, b=20),
        height=height,
        font=dict(family="Arial, Microsoft YaHei, sans-serif", size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(148, 163, 184, 0.22)")
    return fig


def _day_hourly(dispatch: pd.DataFrame, day_name: str | None = None) -> pd.DataFrame:
    data = dispatch.copy()
    if day_name and "day_name" in data.columns:
        data = data[data["day_name"].eq(day_name)]
    data["hour_int"] = data["hour"].round().astype(int).clip(0, 23)
    numeric = data.select_dtypes("number").columns.tolist()
    return data.groupby("hour_int", as_index=False)[numeric].mean()


def source_forecast(dispatch: pd.DataFrame) -> go.Figure:
    data = _day_hourly(dispatch)
    fig = go.Figure()
    if "P_WT" in data:
        fig.add_trace(go.Scatter(x=data["hour_int"], y=data["P_WT"], mode="lines", name="风机预测"))
    if "P_PV" in data:
        fig.add_trace(go.Scatter(x=data["hour_int"], y=data["P_PV"], mode="lines", name="光伏预测"))
    fig.update_layout(yaxis_title="功率 / MW", xaxis_title="时间 / h")
    return _base_layout(fig, "新能源出力预测")


def load_forecast(dispatch: pd.DataFrame) -> go.Figure:
    data = _day_hourly(dispatch)
    fig = go.Figure()
    if "electric_load" in data:
        fig.add_trace(go.Scatter(x=data["hour_int"], y=data["electric_load"], mode="lines", name="电负荷"))
    if "heat_load" in data:
        fig.add_trace(go.Scatter(x=data["hour_int"], y=data["heat_load"], mode="lines", name="热负荷"))
    if "cooling_load" in data:
        fig.add_trace(go.Scatter(x=data["hour_int"], y=data["cooling_load"], mode="lines", name="冷负荷"))
    fig.update_layout(yaxis_title="功率 / MW", xaxis_title="时间 / h")
    return _base_layout(fig, "负荷预测")


def dispatch_chart(dispatch: pd.DataFrame, day_name: str, carrier: str) -> go.Figure:
    data = _day_hourly(dispatch, day_name)
    groups = {
        "电": [
            ("燃气轮机", "P_CHP"),
            ("主网购电", "P_grid_buy"),
            ("风机", "P_WT"),
            ("光伏", "P_PV"),
            ("电池放电", "P_BAT_dis"),
            ("电负荷", "electric_load"),
        ],
        "热": [
            ("燃气轮机", "H_CHP"),
            ("热泵", "H_HP"),
            ("燃气锅炉", "H_GB"),
            ("蓄热释放", "H_TS_dis"),
            ("热负荷", "heat_load"),
        ],
        "气": [
            ("主网购气", "G_CHP"),
            ("燃气轮机耗气", "G_CHP"),
            ("燃气锅炉耗气", "G_GB"),
        ],
        "氢": [
            ("电制氢", "P_ELZ"),
            ("氢气释能", "H_H2"),
        ],
        "碳": [
            ("实际碳排放", "co2_emission"),
            ("碳封存代理", "P_ELZ"),
            ("碳捕集代理", "H_H2"),
        ],
    }
    fig = go.Figure()
    for label, column in groups.get(carrier, []):
        if column in data:
            fig.add_trace(go.Bar(x=data["hour_int"], y=data[column], name=label))
    fig.update_layout(
        barmode="group",
        yaxis_title="功率 / MW" if carrier != "碳" else "碳排 / t",
        xaxis_title="时间 / h",
    )
    return _base_layout(fig, f"{carrier}侧调度结果")


def summary_comparison_bar(
    summary: pd.DataFrame,
    scenarios: list[str],
    metric: str,
    title: str,
    color: str,
) -> go.Figure:
    data = summary[summary["Scenario"].isin(scenarios)].copy()
    data["Scenario"] = pd.Categorical(data["Scenario"], categories=scenarios, ordered=True)
    data = data.sort_values("Scenario")
    fig = px.bar(
        data,
        x="Scenario",
        y=metric,
        color_discrete_sequence=[color],
        hover_data=["Name"] if "Name" in data.columns else None,
    )
    fig.update_layout(yaxis_title=metric, xaxis_title="场景")
    return _base_layout(fig, title)


def metric_strip(summary: pd.DataFrame, scenario: str, metrics: list[str]) -> go.Figure:
    row = summary[summary["Scenario"].eq(scenario)]
    values = []
    if not row.empty:
        source = row.iloc[0]
        for metric in metrics:
            try:
                values.append(float(source.get(metric, 0.0)))
            except (TypeError, ValueError):
                values.append(0.0)
    data = pd.DataFrame(
        {
            "指标": [item.replace(" [million CNY/year]", "") for item in metrics],
            "值": values,
        }
    )
    fig = px.bar(data, x="指标", y="值", color="指标", color_discrete_sequence=COLORWAY)
    fig.update_layout(showlegend=False, yaxis_title="百万元/年", xaxis_title="")
    return _base_layout(fig, f"{scenario} 经济指标")


def carbon_decomposition(carbon: pd.DataFrame) -> go.Figure:
    data = carbon.copy()
    data = data[data["Scenario"].isin(["S0", "S2", "S4", "S6", "S8"])]
    columns = [
        "Grid import emissions [tCO2/year]",
        "CHP gas emissions [tCO2/year]",
        "Gas boiler emissions [tCO2/year]",
        "Green-direct avoided emissions proxy [tCO2/year]",
        "Endogenous P2X avoided emissions [tCO2/year]",
    ]
    labels = {
        "Grid import emissions [tCO2/year]": "主网购电碳排",
        "CHP gas emissions [tCO2/year]": "CHP燃气碳排",
        "Gas boiler emissions [tCO2/year]": "燃气锅炉碳排",
        "Green-direct avoided emissions proxy [tCO2/year]": "绿电直连减排",
        "Endogenous P2X avoided emissions [tCO2/year]": "P2X减排",
    }
    melted = data.melt(
        id_vars=["Scenario"],
        value_vars=[c for c in columns if c in data],
        var_name="类型",
        value_name="tCO2",
    )
    melted["类型"] = melted["类型"].map(labels).fillna(melted["类型"])
    fig = px.bar(melted, x="Scenario", y="tCO2", color="类型", barmode="group", color_discrete_sequence=COLORWAY)
    fig.update_layout(yaxis_title="tCO2/年", xaxis_title="场景")
    return _base_layout(fig, "碳排放来源与减排贡献")


def scenario_scatter(summary: pd.DataFrame) -> go.Figure:
    required = [
        "Private total annual cost [million CNY/year]",
        "Annual CO2 emissions [tCO2/year]",
        "Renewable local absorption rate [%]",
        "Scenario",
    ]
    data = summary[[c for c in required if c in summary.columns]].copy()
    fig = px.scatter(
        data,
        x="Private total annual cost [million CNY/year]",
        y="Annual CO2 emissions [tCO2/year]",
        size="Renewable local absorption rate [%]" if "Renewable local absorption rate [%]" in data else None,
        color="Scenario",
        hover_name="Scenario",
        color_discrete_sequence=COLORWAY,
    )
    fig.update_layout(
        xaxis_title="私有总成本 / 百万元·年",
        yaxis_title="年度CO2排放 / t",
    )
    return _base_layout(fig, "成本-碳排-绿电吸纳综合对比")


def storage_profile(dispatch: pd.DataFrame, day_name: str) -> go.Figure:
    data = _day_hourly(dispatch, day_name)
    fig = go.Figure()
    for label, column in [
        ("电池充电", "P_BAT_ch"),
        ("电池放电", "P_BAT_dis"),
        ("电池SOC", "SOC_BAT"),
        ("蓄热充热", "H_TS_ch"),
        ("蓄热放热", "H_TS_dis"),
        ("蓄热SOC", "SOC_TS"),
    ]:
        if column in data:
            fig.add_trace(go.Scatter(x=data["hour_int"], y=data[column], mode="lines+markers", name=label))
    fig.update_layout(yaxis_title="功率或SOC", xaxis_title="时间 / h")
    return _base_layout(fig, "储能充放与状态轨迹")
