from __future__ import annotations

import pandas as pd

from src.agri_dashboard_charts import (
    agri_day_dispatch_figure,
    agri_energy_flow_sankey_figure,
    agri_load_calendar_figure,
    agri_monthly_balance_figure,
    agri_storage_origin_figure,
    agri_stress_test_figure,
    agri_strategy_cost_carbon_figure,
    agri_zero_carbon_disposition_figure,
)
from src.model.agri_park_profiles import generate_agri_park_profiles
from src.model.agri_zero_carbon_optimizer import AgriOptimizationRequest, AgriZeroCarbonOptimizer


def _optimized_week() -> pd.DataFrame:
    profiles = generate_agri_park_profiles(2025, 60).iloc[: 24 * 7].reset_index(drop=True)
    result = AgriZeroCarbonOptimizer().optimize(
        profiles,
        AgriOptimizationRequest(target_physical_green_share=1.0),
    )
    assert result.success
    return result.dispatch


def test_agriculture_load_and_strategy_figures_are_multidimensional() -> None:
    profiles = generate_agri_park_profiles(2025, 60)
    comparison = pd.read_csv("data/demo/phase1_strategy_comparison.csv", encoding="utf-8-sig")
    assert len(agri_load_calendar_figure(profiles).data) == 5
    assert len(agri_strategy_cost_carbon_figure(comparison).data) == 2


def test_agriculture_dispatch_figures_explain_supply_storage_and_losses() -> None:
    dispatch = _optimized_week()
    date = "2025-01-03"
    assert len(agri_monthly_balance_figure(dispatch).data) == 5
    assert len(agri_day_dispatch_figure(dispatch, date).data) == 6
    assert len(agri_storage_origin_figure(dispatch, date).data) == 5


def test_agriculture_sankey_and_disposition_keep_absolute_energy_values() -> None:
    annual_flows = pd.DataFrame(
        {
            "来源": ["园区本地光伏", "公共电网当期购电"],
            "去向": ["灌溉与水泵", "粮食烘干与加工"],
            "电量/兆瓦时": [100.0, 50.0],
            "类型": ["负荷供能", "负荷供能"],
        }
    )
    summary = {
        "annual_physical_green_to_load_mwh": 100.0,
        "annual_export_mwh": 20.0,
        "annual_curtailment_mwh": 10.0,
        "annual_direct_green_line_loss_mwh": 5.0,
    }
    assert len(agri_energy_flow_sankey_figure(annual_flows).data) == 1
    assert sum(agri_energy_flow_sankey_figure(annual_flows).data[0].link.value) == 150.0
    assert len(agri_zero_carbon_disposition_figure(summary).data) == 1


def test_stress_figure_displays_energy_shortfall_and_cost_change() -> None:
    stress = pd.read_csv("data/demo/phase1_stress_test_results.csv", encoding="utf-8-sig")
    figure = agri_stress_test_figure(stress)
    assert len(figure.data) == 2
    assert max(figure.data[0].y) > 0.0
