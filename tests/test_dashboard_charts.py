from __future__ import annotations

import pandas as pd

from src.dashboard_charts import (
    annualized_dispatch_value,
    capacity_utilization_figure,
    dispatch_heatmap_figure,
    duration_curve_figure,
    energy_flow_sankey_figure,
    performance_radar_figure,
    scenario_incremental_figure,
    scenario_parallel_coordinates_figure,
    scenario_score_heatmap_figure,
    scenario_score_table,
)


def sample_dispatch() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "day_id": [1, 1, 2, 2],
            "day_name": ["春季", "春季", "夏季", "夏季"],
            "day_weight": [180, 180, 185, 185],
            "dt": [1.0, 1.0, 1.0, 1.0],
            "hour": [0.0, 1.0, 0.0, 1.0],
            "P_PV": [0.0, 5.0, 0.0, 8.0],
            "P_WT": [3.0, 4.0, 2.0, 3.0],
            "P_grid_buy": [5.0, 0.0, 6.0, 0.0],
            "P_CHP": [1.0, 1.0, 1.0, 1.0],
            "P_BAT_dis": [0.0, 1.0, 0.0, 1.0],
            "electric_load_adjusted": [8.0, 8.0, 9.0, 9.0],
            "P_HP": [1.0, 1.0, 1.0, 1.0],
            "P_EC": [0.0, 1.0, 0.0, 2.0],
            "P_ELZ": [0.0, 0.0, 0.0, 0.0],
            "P_BAT_ch": [0.0, 0.0, 0.0, 0.0],
            "P_grid_sell": [0.0, 1.0, 0.0, 1.0],
            "P_grid_net": [5.0, -1.0, 6.0, -1.0],
            "renewable_used": [3.0, 9.0, 2.0, 11.0],
            "co2_emission_rate": [2.0, 0.2, 2.4, 0.1],
        }
    )


def test_dashboard_dispatch_figures_use_weighted_model_results() -> None:
    dispatch = sample_dispatch()
    assert annualized_dispatch_value(dispatch, "P_grid_buy") == 2010.0
    assert len(energy_flow_sankey_figure(dispatch).data) == 1
    assert len(dispatch_heatmap_figure(dispatch).data) == 1
    assert len(duration_curve_figure(dispatch).data) == 3


def test_capacity_and_performance_figures_have_decision_dimensions() -> None:
    capacity = pd.DataFrame(
        {
            "Technology": ["PV", "WT"],
            "Capacity": [40.0, 60.0],
            "Unit": ["MW", "MW"],
            "Upper bound": [100.0, 100.0],
            "Upper-bound utilization [%]": [40.0, 60.0],
        }
    )
    metrics = {
        "Total multi-energy service rate": 99.9,
        "Renewable utilization rate (including export)": 92.0,
        "Renewable local share of electric-service demand": 80.0,
        "Grid import share of electric-service demand": 20.0,
        "Renewable curtailment rate": 8.0,
    }
    assert len(capacity_utilization_figure(capacity).data) == 1
    assert len(performance_radar_figure(metrics).data[0].r) == 6


def test_scenario_visuals_and_preference_ranking_are_traceable() -> None:
    table = pd.DataFrame(
        {
            "场景": ["S0", "S4", "S8"],
            "场景名称": ["基准", "低碳", "深度脱碳"],
            "是否成功": [True, True, True],
            "社会年度成本/万元": [100.0, 105.0, 110.0],
            "年度二氧化碳排放/吨": [1000.0, 600.0, 400.0],
            "年度电网购电量/兆瓦时": [1000.0, 700.0, 500.0],
            "新能源综合利用率/%": [80.0, 90.0, 95.0],
            "多能综合服务保障率/%": [99.0, 100.0, 100.0],
            "电池等效循环次数/次每年": [0.0, 200.0, 220.0],
            "相对S0减排率/%": [0.0, 40.0, 60.0],
        }
    )
    scored = scenario_score_table(table, "低碳优先")
    assert scored.iloc[0]["场景"] == "S8"
    assert scored["相对排名"].tolist() == [1, 2, 3]
    assert len(scenario_score_heatmap_figure(scored).data) == 1
    assert len(scenario_parallel_coordinates_figure(scored).data) == 1
    assert len(scenario_incremental_figure(table).data) == 2
