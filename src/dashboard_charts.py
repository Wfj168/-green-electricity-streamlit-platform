from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


BLUE = "#2563eb"
CYAN = "#06b6d4"
GREEN = "#16a34a"
AMBER = "#f59e0b"
ORANGE = "#f97316"
RED = "#ef4444"
PURPLE = "#8b5cf6"
SLATE = "#64748b"


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series(0.0, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def annualized_dispatch_value(dispatch: pd.DataFrame, column: str) -> float:
    if dispatch.empty or column not in dispatch:
        return 0.0
    weight = _numeric(dispatch, "day_weight")
    if not weight.any():
        weight = pd.Series(1.0, index=dispatch.index)
    step = _numeric(dispatch, "dt")
    if not step.any():
        step = pd.Series(1.0, index=dispatch.index)
    return float((_numeric(dispatch, column) * weight * step).sum())


def energy_flow_sankey_figure(dispatch: pd.DataFrame) -> go.Figure:
    if dispatch.empty:
        return go.Figure()
    nodes = [
        "光伏",
        "风电",
        "电网购电",
        "热电联产发电",
        "电储能放电",
        "园区电力母线",
        "终端用电",
        "热泵",
        "电制冷",
        "电转其他能源",
        "电储能充电",
        "绿电外送",
    ]
    supply = {
        0: annualized_dispatch_value(dispatch, "P_PV"),
        1: annualized_dispatch_value(dispatch, "P_WT"),
        2: annualized_dispatch_value(dispatch, "P_grid_buy"),
        3: annualized_dispatch_value(dispatch, "P_CHP"),
        4: annualized_dispatch_value(dispatch, "P_BAT_dis"),
    }
    demand = {
        6: annualized_dispatch_value(dispatch, "electric_load_adjusted"),
        7: annualized_dispatch_value(dispatch, "P_HP"),
        8: annualized_dispatch_value(dispatch, "P_EC"),
        9: annualized_dispatch_value(dispatch, "P_ELZ"),
        10: annualized_dispatch_value(dispatch, "P_BAT_ch"),
        11: annualized_dispatch_value(dispatch, "P_grid_sell"),
    }
    source: list[int] = []
    target: list[int] = []
    values: list[float] = []
    colors: list[str] = []
    for node, value in supply.items():
        if value > 1e-6:
            source.append(node)
            target.append(5)
            values.append(value)
            colors.append("rgba(37,99,235,0.36)" if node == 2 else "rgba(22,163,74,0.36)")
    for node, value in demand.items():
        if value > 1e-6:
            source.append(5)
            target.append(node)
            values.append(value)
            colors.append("rgba(6,182,212,0.34)" if node != 11 else "rgba(139,92,246,0.34)")
    figure = go.Figure(
        go.Sankey(
            arrangement="snap",
            node={
                "pad": 18,
                "thickness": 18,
                "line": {"color": "#dbeafe", "width": 1},
                "label": nodes,
                "color": [AMBER, GREEN, BLUE, ORANGE, PURPLE, "#0f3b67", "#475569", CYAN, BLUE, GREEN, PURPLE, "#7c3aed"],
            },
            link={"source": source, "target": target, "value": values, "color": colors},
            valueformat=",.0f",
            valuesuffix=" 兆瓦时/年",
        )
    )
    figure.update_layout(title="年度电力流向全景", height=470)
    return figure


def performance_radar_figure(metrics: dict[str, Any]) -> go.Figure:
    categories = ["多能保障", "新能源利用", "本地绿电", "电力自给", "低弃电"]
    values = [
        float(metrics.get("Total multi-energy service rate", 0) or 0),
        float(metrics.get("Renewable utilization rate (including export)", 0) or 0),
        float(metrics.get("Renewable local share of electric-service demand", 0) or 0),
        100.0 - float(metrics.get("Grid import share of electric-service demand", 0) or 0),
        100.0 - float(metrics.get("Renewable curtailment rate", 0) or 0),
    ]
    values = [max(0.0, min(100.0, value)) for value in values]
    figure = go.Figure(
        go.Scatterpolar(
            r=values + values[:1],
            theta=categories + categories[:1],
            fill="toself",
            line={"color": BLUE, "width": 3},
            fillcolor="rgba(37,99,235,0.16)",
            hovertemplate="%{theta}：%{r:.1f}%<extra></extra>",
        )
    )
    figure.update_layout(
        title="系统目标达成画像",
        polar={"radialaxis": {"visible": True, "range": [0, 100], "ticksuffix": "%"}},
        showlegend=False,
        height=390,
    )
    return figure


def capacity_utilization_figure(capacity: pd.DataFrame) -> go.Figure:
    if capacity.empty or "Upper-bound utilization [%]" not in capacity:
        return go.Figure()
    data = capacity.copy()
    data["Upper-bound utilization [%]"] = pd.to_numeric(
        data["Upper-bound utilization [%]"], errors="coerce"
    ).fillna(0.0)
    data["Capacity"] = pd.to_numeric(data["Capacity"], errors="coerce").fillna(0.0)
    data = data[data["Upper bound"].fillna(0).astype(float) > 0].sort_values(
        "Upper-bound utilization [%]"
    )
    technology_labels = {
        "PV": "光伏",
        "WT": "风电",
        "CHP": "热电联产",
        "Heat pump": "热泵",
        "Electric chiller": "电制冷",
        "Gas boiler": "燃气锅炉",
        "Battery energy": "电储能容量",
        "Battery power": "电储能功率",
        "Thermal storage energy": "蓄热容量",
        "Thermal storage power": "蓄热功率",
        "Electrolyzer": "电解槽",
    }
    labels = data["Technology"].map(technology_labels).fillna(data["Technology"])
    utilization = data["Upper-bound utilization [%]"]
    colors = [RED if value >= 95 else AMBER if value >= 75 else BLUE for value in utilization]
    custom = list(zip(data["Capacity"], data["Unit"], data["Upper bound"]))
    figure = go.Figure(
        go.Bar(
            x=utilization,
            y=labels,
            orientation="h",
            marker_color=colors,
            text=[f"{value:.1f}%" for value in utilization],
            textposition="outside",
            customdata=custom,
            hovertemplate="%{y}<br>上限利用率：%{x:.1f}%<br>规划容量：%{customdata[0]:.2f} %{customdata[1]}<br>规划上限：%{customdata[2]:.2f}<extra></extra>",
        )
    )
    figure.update_layout(title="规划边界占用情况", height=430)
    figure.update_xaxes(title="规划上限利用率", range=[0, max(105.0, float(utilization.max()) * 1.12)])
    figure.update_yaxes(title="")
    return figure


def cost_waterfall_figure(localized_cost: pd.DataFrame) -> go.Figure:
    if localized_cost.empty or not {"成本项目", "数值"}.issubset(localized_cost.columns):
        return go.Figure()
    data = localized_cost.copy()
    data["数值"] = pd.to_numeric(data["数值"], errors="coerce").fillna(0.0)
    total_rows = data[data["成本项目"].eq("社会年度总成本")]
    total = float(total_rows.iloc[0]["数值"]) if not total_rows.empty else float(data["数值"].sum())
    aggregate = {"年度可变运行成本", "项目年度总成本", "社会年度总成本", "优化目标年度成本"}
    components = data[~data["成本项目"].isin(aggregate)].copy()
    components.loc[components["成本项目"].eq("上网售电收入"), "数值"] *= -1.0
    components = components[components["数值"].abs() > max(abs(total) * 0.0001, 1e-6)]
    if len(components) > 9:
        top = components.reindex(components["数值"].abs().sort_values(ascending=False).index).head(8)
        remainder = float(components.loc[~components.index.isin(top.index), "数值"].sum())
        components = pd.concat(
            [top, pd.DataFrame([{"成本项目": "其他净成本", "数值": remainder}])],
            ignore_index=True,
        )
    labels = components["成本项目"].astype(str).tolist() + ["社会年度总成本"]
    values = components["数值"].astype(float).tolist() + [total]
    measures = ["relative"] * len(components) + ["total"]
    figure = go.Figure(
        go.Waterfall(
            x=labels,
            y=values,
            measure=measures,
            connector={"line": {"color": "#94a3b8"}},
            increasing={"marker": {"color": BLUE}},
            decreasing={"marker": {"color": GREEN}},
            totals={"marker": {"color": "#0f3b67"}},
            text=[f"{value:,.0f}" for value in values],
            textposition="outside",
        )
    )
    figure.update_layout(title="年度成本形成路径", height=470, showlegend=False)
    figure.update_yaxes(title="万元/年")
    return figure


def dispatch_heatmap_figure(dispatch: pd.DataFrame, column: str = "P_grid_net") -> go.Figure:
    if dispatch.empty or column not in dispatch or "hour" not in dispatch:
        return go.Figure()
    data = dispatch.copy()
    data["典型日"] = data.get("day_name", data.get("day_id", "典型日")).astype(str)
    data["小时"] = pd.to_numeric(data["hour"], errors="coerce").round(2)
    pivot = data.pivot_table(index="典型日", columns="小时", values=column, aggfunc="mean")
    title = "分时电网友好性热力图" if column == "P_grid_net" else "分时碳排放热力图"
    unit = "兆瓦" if column == "P_grid_net" else "吨/小时"
    figure = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=pivot.index,
            colorscale="RdBu_r" if column == "P_grid_net" else "YlOrRd",
            zmid=0 if column == "P_grid_net" else None,
            colorbar={"title": unit},
            hovertemplate="典型日：%{y}<br>时刻：%{x}时<br>数值：%{z:.2f} " + unit + "<extra></extra>",
        )
    )
    figure.update_layout(title=title, height=400)
    figure.update_xaxes(title="时刻/小时")
    figure.update_yaxes(title="")
    return figure


def duration_curve_figure(dispatch: pd.DataFrame) -> go.Figure:
    if dispatch.empty:
        return go.Figure()
    expanded: dict[str, list[float]] = {"园区用电": [], "新能源出力": [], "电网净交换": []}
    columns = {
        "园区用电": "electric_load_adjusted",
        "新能源出力": "renewable_used",
        "电网净交换": "P_grid_net",
    }
    for _, row in dispatch.iterrows():
        repeats = max(1, int(round(float(row.get("day_weight", 1) or 1))))
        for label, column in columns.items():
            expanded[label].extend([float(row.get(column, 0) or 0)] * repeats)
    figure = go.Figure()
    palette = {"园区用电": "#0f172a", "新能源出力": GREEN, "电网净交换": BLUE}
    for label, values in expanded.items():
        if not values:
            continue
        ordered = sorted(values, reverse=True)
        x = [100.0 * index / max(len(ordered) - 1, 1) for index in range(len(ordered))]
        figure.add_trace(
            go.Scatter(x=x, y=ordered, name=label, mode="lines", line={"width": 2.5, "color": palette[label]})
        )
    figure.update_layout(title="全年持续时间曲线", height=400)
    figure.update_xaxes(title="超过该功率的全年时间比例", ticksuffix="%")
    figure.update_yaxes(title="功率/兆瓦")
    return figure


SCENARIO_WEIGHTS = {
    "综合均衡": {"经济性": 0.25, "低碳性": 0.25, "绿电消纳": 0.20, "电网友好": 0.15, "供能保障": 0.15},
    "经济优先": {"经济性": 0.45, "低碳性": 0.15, "绿电消纳": 0.15, "电网友好": 0.15, "供能保障": 0.10},
    "低碳优先": {"经济性": 0.15, "低碳性": 0.45, "绿电消纳": 0.20, "电网友好": 0.10, "供能保障": 0.10},
    "保供优先": {"经济性": 0.15, "低碳性": 0.15, "绿电消纳": 0.10, "电网友好": 0.10, "供能保障": 0.50},
}


def _relative_score(values: pd.Series, *, higher_is_better: bool) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    minimum = numeric.min()
    maximum = numeric.max()
    if pd.isna(minimum) or pd.isna(maximum):
        return pd.Series(0.0, index=values.index)
    if abs(float(maximum) - float(minimum)) <= 1e-9:
        return pd.Series(100.0, index=values.index)
    score = (numeric - minimum) / (maximum - minimum) * 100.0
    return score if higher_is_better else 100.0 - score


def scenario_score_table(table: pd.DataFrame, preference: str = "综合均衡") -> pd.DataFrame:
    valid = table[table["是否成功"]].copy()
    if valid.empty:
        return valid
    valid["经济性"] = _relative_score(valid["社会年度成本/万元"], higher_is_better=False)
    valid["低碳性"] = _relative_score(valid["年度二氧化碳排放/吨"], higher_is_better=False)
    valid["绿电消纳"] = _relative_score(valid["新能源综合利用率/%"], higher_is_better=True)
    valid["电网友好"] = _relative_score(valid["年度电网购电量/兆瓦时"], higher_is_better=False)
    valid["供能保障"] = _relative_score(valid["多能综合服务保障率/%"], higher_is_better=True)
    weights = SCENARIO_WEIGHTS.get(preference, SCENARIO_WEIGHTS["综合均衡"])
    valid["相对综合得分"] = sum(valid[name] * weight for name, weight in weights.items())
    valid["相对排名"] = valid["相对综合得分"].rank(method="min", ascending=False).astype(int)
    valid["决策偏好"] = preference
    return valid.sort_values(["相对排名", "社会年度成本/万元"]).reset_index(drop=True)


def scenario_score_heatmap_figure(score_table: pd.DataFrame) -> go.Figure:
    dimensions = ["经济性", "低碳性", "绿电消纳", "电网友好", "供能保障"]
    if score_table.empty or not set(dimensions).issubset(score_table.columns):
        return go.Figure()
    data = score_table.sort_values("相对排名")
    z = data[dimensions].to_numpy(dtype=float)
    figure = go.Figure(
        go.Heatmap(
            z=z,
            x=dimensions,
            y=data["场景"],
            colorscale=[[0, "#fee2e2"], [0.5, "#fef3c7"], [1, "#dcfce7"]],
            zmin=0,
            zmax=100,
            text=[[f"{value:.0f}" for value in row] for row in z],
            texttemplate="%{text}",
            colorbar={"title": "相对表现"},
            hovertemplate="场景：%{y}<br>维度：%{x}<br>相对表现：%{z:.1f}<extra></extra>",
        )
    )
    figure.update_layout(title="场景多维决策矩阵", height=410)
    return figure


def scenario_parallel_coordinates_figure(score_table: pd.DataFrame) -> go.Figure:
    if score_table.empty:
        return go.Figure()
    data = score_table.sort_values("场景").reset_index(drop=True)
    dimensions = [
        {"label": "场景", "values": data.index, "tickvals": data.index, "ticktext": data["场景"]},
        {"label": "成本/万元", "values": data["社会年度成本/万元"]},
        {"label": "排放/吨", "values": data["年度二氧化碳排放/吨"]},
        {"label": "购电/兆瓦时", "values": data["年度电网购电量/兆瓦时"]},
        {"label": "新能源利用/%", "values": data["新能源综合利用率/%"]},
        {"label": "储能循环/次", "values": data["电池等效循环次数/次每年"]},
        {"label": "相对得分", "values": data["相对综合得分"]},
    ]
    figure = go.Figure(
        go.Parcoords(
            line={
                "color": data["相对综合得分"],
                "colorscale": "Viridis",
                "showscale": True,
                "colorbar": {"title": "相对得分"},
            },
            dimensions=dimensions,
        )
    )
    figure.update_layout(title="场景多指标平行坐标", height=460)
    return figure


def scenario_incremental_figure(table: pd.DataFrame) -> go.Figure:
    valid = table[table["是否成功"]].copy()
    if valid.empty:
        return go.Figure()
    valid["场景序号"] = pd.to_numeric(valid["场景"].astype(str).str.extract(r"(\d+)")[0], errors="coerce")
    valid = valid.sort_values("场景序号")
    cost_delta = pd.to_numeric(valid["社会年度成本/万元"], errors="coerce").diff().fillna(0.0)
    emission_reduction = -pd.to_numeric(valid["年度二氧化碳排放/吨"], errors="coerce").diff().fillna(0.0)
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_trace(
        go.Bar(
            x=valid["场景"],
            y=cost_delta,
            name="相邻场景成本变化",
            marker_color=[GREEN if value < 0 else BLUE for value in cost_delta],
        ),
        secondary_y=False,
    )
    figure.add_trace(
        go.Scatter(
            x=valid["场景"],
            y=emission_reduction,
            name="相邻场景减排变化",
            mode="lines+markers",
            line={"color": RED, "width": 3},
        ),
        secondary_y=True,
    )
    figure.update_layout(title="相邻场景的边际变化", height=410)
    figure.update_yaxes(title_text="成本变化/万元", secondary_y=False)
    figure.update_yaxes(title_text="新增减排量/吨", secondary_y=True)
    return figure
