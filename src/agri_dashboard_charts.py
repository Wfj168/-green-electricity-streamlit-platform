from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


GREEN = "#16a34a"
EMERALD = "#059669"
CYAN = "#06b6d4"
BLUE = "#2563eb"
PURPLE = "#7c3aed"
AMBER = "#f59e0b"
ORANGE = "#f97316"
RED = "#ef4444"
SLATE = "#475569"


def _layout(figure: go.Figure, title: str, height: int = 430) -> go.Figure:
    figure.update_layout(
        title=title,
        template="plotly_white",
        height=height,
        margin={"l": 28, "r": 28, "t": 60, "b": 36},
        font={"family": "Microsoft YaHei, Arial, sans-serif", "size": 13},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
        hovermode="x unified",
    )
    figure.update_xaxes(showgrid=False)
    figure.update_yaxes(gridcolor="rgba(148,163,184,0.22)")
    return figure


def agri_load_calendar_figure(profiles: pd.DataFrame) -> go.Figure:
    data = profiles.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"])
    data["月份"] = data["timestamp"].dt.to_period("M").astype(str)
    monthly = data.groupby("月份", as_index=False).agg(
        灌溉与水泵=("irrigation_load_mw", "sum"),
        粮食烘干与加工=("grain_processing_load_mw", "sum"),
        仓储与冷链=("storage_cold_chain_load_mw", "sum"),
        公共与辅助=("public_auxiliary_load_mw", "sum"),
        月峰值=("total_meter_load_mw", "max"),
    )
    interval = 1.0
    if len(data) > 1:
        interval = float(data["timestamp"].diff().dropna().dt.total_seconds().median()) / 3600.0
    for column in ("灌溉与水泵", "粮食烘干与加工", "仓储与冷链", "公共与辅助"):
        monthly[column] *= interval
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    colors = [BLUE, AMBER, CYAN, SLATE]
    for column, color in zip(("灌溉与水泵", "粮食烘干与加工", "仓储与冷链", "公共与辅助"), colors, strict=True):
        figure.add_trace(
            go.Bar(x=monthly["月份"], y=monthly[column], name=column, marker_color=color),
            secondary_y=False,
        )
    figure.add_trace(
        go.Scatter(
            x=monthly["月份"],
            y=monthly["月峰值"],
            name="月最大负荷",
            mode="lines+markers",
            line={"color": RED, "width": 3},
        ),
        secondary_y=True,
    )
    figure.update_layout(barmode="stack")
    figure.update_yaxes(title_text="月用电量/兆瓦时", secondary_y=False)
    figure.update_yaxes(title_text="最大负荷/兆瓦", secondary_y=True)
    return _layout(figure, "农业生产日历与四类负荷")


def agri_strategy_cost_carbon_figure(comparison: pd.DataFrame) -> go.Figure:
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_trace(
        go.Bar(
            x=comparison["策略"],
            y=comparison["年总成本/万元"],
            name="年总成本",
            marker_color=[SLATE, GREEN, PURPLE],
            text=[f"{value:.1f}" for value in comparison["年总成本/万元"]],
            textposition="outside",
        ),
        secondary_y=False,
    )
    figure.add_trace(
        go.Scatter(
            x=comparison["策略"],
            y=comparison["运营碳排放/吨"],
            name="运营碳排放",
            mode="lines+markers+text",
            text=[f"{value:.0f}" for value in comparison["运营碳排放/吨"]],
            textposition="top center",
            line={"color": ORANGE, "width": 3},
            marker={"size": 10},
        ),
        secondary_y=True,
    )
    figure.update_yaxes(title_text="年总成本/万元", secondary_y=False)
    figure.update_yaxes(title_text="运营碳排放/吨", secondary_y=True)
    return _layout(figure, "三种策略的成本与碳排放权衡")


def agri_energy_flow_sankey_figure(annual_flows: pd.DataFrame) -> go.Figure:
    if annual_flows.empty:
        return go.Figure()
    sources = annual_flows["来源"].astype(str)
    targets = annual_flows["去向"].astype(str)
    labels = list(dict.fromkeys([*sources.tolist(), *targets.tolist()]))
    positions = {label: index for index, label in enumerate(labels)}
    values = pd.to_numeric(annual_flows["电量/兆瓦时"], errors="coerce").fillna(0.0)
    link_colors = [
        "rgba(22,163,74,0.38)" if "光伏" in source or "绿电" in source else "rgba(37,99,235,0.32)"
        for source in sources
    ]
    node_colors = [
        GREEN if "光伏" in label or "绿电" in label else PURPLE if "储能" in label else BLUE if "电网" in label else SLATE
        for label in labels
    ]
    figure = go.Figure(
        go.Sankey(
            arrangement="snap",
            node={
                "label": labels,
                "pad": 18,
                "thickness": 18,
                "color": node_colors,
                "line": {"color": "#e2e8f0", "width": 1},
            },
            link={
                "source": [positions[value] for value in sources],
                "target": [positions[value] for value in targets],
                "value": values,
                "color": link_colors,
            },
            valueformat=",.1f",
            valuesuffix=" 兆瓦时",
        )
    )
    return _layout(figure, "绿电直连方案年度能量流向", 540)


def agri_monthly_balance_figure(dispatch: pd.DataFrame) -> go.Figure:
    data = dispatch.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"])
    data["月份"] = data["timestamp"].dt.to_period("M").astype(str)
    interval = 1.0
    if len(data) > 1:
        interval = float(data["timestamp"].diff().dropna().dt.total_seconds().median()) / 3600.0
    columns = {
        "本地光伏供负荷": "pv_to_load_mw",
        "直连绿电供负荷": "direct_to_load_mw",
        "绿电储能放电": "battery_discharge_total_mw",
        "普通电网购电": "grid_to_load_mw",
    }
    monthly = data.groupby("月份", as_index=False)[[*columns.values(), "optimized_total_load_mw"]].sum()
    for column in [*columns.values(), "optimized_total_load_mw"]:
        monthly[column] *= interval
    figure = go.Figure()
    palette = [GREEN, EMERALD, PURPLE, BLUE]
    for (label, column), color in zip(columns.items(), palette, strict=True):
        figure.add_trace(go.Bar(x=monthly["月份"], y=monthly[column], name=label, marker_color=color))
    figure.add_trace(
        go.Scatter(
            x=monthly["月份"],
            y=monthly["optimized_total_load_mw"],
            name="农业园区用电",
            mode="lines+markers",
            line={"color": "#0f172a", "width": 3},
        )
    )
    figure.update_layout(barmode="stack")
    figure.update_yaxes(title="月电量/兆瓦时")
    return _layout(figure, "零碳协同方案月度供需闭环", 470)


def agri_day_dispatch_figure(dispatch: pd.DataFrame, selected_date: str) -> go.Figure:
    data = dispatch.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"])
    selected = data[data["timestamp"].dt.strftime("%Y-%m-%d").eq(selected_date)].copy()
    selected["时刻"] = selected["timestamp"].dt.strftime("%H:%M")
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    supplies = (
        ("本地光伏直供", "pv_to_load_mw", GREEN),
        ("直连绿电直供", "direct_to_load_mw", EMERALD),
        ("绿电储能放电", "battery_discharge_total_mw", PURPLE),
        ("普通电网购电", "grid_to_load_mw", BLUE),
    )
    for label, column, color in supplies:
        figure.add_trace(
            go.Bar(x=selected["时刻"], y=selected[column], name=label, marker_color=color),
            secondary_y=False,
        )
    figure.add_trace(
        go.Scatter(
            x=selected["时刻"],
            y=selected["optimized_total_load_mw"],
            name="优化后农业负荷",
            mode="lines+markers",
            line={"color": "#0f172a", "width": 3},
        ),
        secondary_y=False,
    )
    curtailment = selected["pv_curtailment_mw"] + selected["direct_curtailment_mw"]
    figure.add_trace(
        go.Scatter(
            x=selected["时刻"],
            y=curtailment,
            name="弃电",
            mode="lines",
            line={"color": RED, "width": 2, "dash": "dot"},
        ),
        secondary_y=True,
    )
    figure.update_layout(barmode="stack")
    figure.update_yaxes(title_text="负荷供能/兆瓦", secondary_y=False)
    figure.update_yaxes(title_text="弃电功率/兆瓦", secondary_y=True)
    return _layout(figure, f"{selected_date}逐时供能、负荷与弃电", 480)


def agri_storage_origin_figure(dispatch: pd.DataFrame, selected_date: str) -> go.Figure:
    data = dispatch.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"])
    selected = data[data["timestamp"].dt.strftime("%Y-%m-%d").eq(selected_date)].copy()
    selected["时刻"] = selected["timestamp"].dt.strftime("%H:%M")
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_trace(
        go.Bar(x=selected["时刻"], y=selected["pv_to_battery_mw"], name="光伏充电", marker_color=GREEN),
        secondary_y=False,
    )
    figure.add_trace(
        go.Bar(
            x=selected["时刻"],
            y=selected["direct_to_battery_mw"],
            name="直连绿电充电",
            marker_color=EMERALD,
        ),
        secondary_y=False,
    )
    figure.add_trace(
        go.Bar(
            x=selected["时刻"],
            y=-selected["battery_discharge_total_mw"],
            name="储能放电",
            marker_color=PURPLE,
        ),
        secondary_y=False,
    )
    figure.add_trace(
        go.Scatter(
            x=selected["时刻"],
            y=selected["battery_soc_pv_mwh"],
            name="光伏来源存量",
            stackgroup="soc",
            line={"color": GREEN},
        ),
        secondary_y=True,
    )
    figure.add_trace(
        go.Scatter(
            x=selected["时刻"],
            y=selected["battery_soc_direct_mwh"],
            name="直连来源存量",
            stackgroup="soc",
            line={"color": EMERALD},
        ),
        secondary_y=True,
    )
    figure.update_layout(barmode="relative")
    figure.update_yaxes(title_text="充放电功率/兆瓦", secondary_y=False)
    figure.update_yaxes(title_text="来源分账存量/兆瓦时", secondary_y=True)
    return _layout(figure, f"{selected_date}储能充放与绿电来源分账", 460)


def agri_zero_carbon_disposition_figure(summary: dict[str, float]) -> go.Figure:
    labels = ["农业负荷消纳", "外送", "弃电", "直连线路损耗"]
    values = [
        summary["annual_physical_green_to_load_mwh"],
        summary["annual_export_mwh"],
        summary["annual_curtailment_mwh"],
        summary["annual_direct_green_line_loss_mwh"],
    ]
    figure = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=[GREEN, BLUE, RED, AMBER],
            text=[f"{value:,.0f}" for value in values],
            textposition="outside",
            hovertemplate="%{x}：%{y:,.1f} 兆瓦时<extra></extra>",
        )
    )
    figure.update_yaxes(title="年电量/兆瓦时")
    return _layout(figure, "零碳方案新增绿电的实际去向", 430)
