from __future__ import annotations

from dataclasses import replace

import pytest

from src.application.agri_energy_flow_service import (
    AgriEnergyFlowRequest,
    AgriEnergyFlowService,
)
from src.model.agri_park_profiles import generate_agri_park_profiles


def test_energy_flow_is_physically_balanced_and_source_traceable() -> None:
    result = AgriEnergyFlowService().simulate(generate_agri_park_profiles(2025, 60))
    dispatch = result.dispatch
    assert result.summary["max_bus_balance_error_mw"] < 1e-9
    assert result.summary["max_system_balance_error_mw"] < 1e-9
    assert result.summary["max_load_allocation_error_mw"] < 1e-9
    assert (
        dispatch["battery_soc_pv_mwh"]
        + dispatch["battery_soc_direct_mwh"]
        + dispatch["battery_soc_grid_mwh"]
        - dispatch["battery_soc_total_mwh"]
    ).abs().max() < 1e-9
    assert not (
        dispatch["battery_charge_total_mw"].gt(1e-9)
        & dispatch["battery_discharge_total_mw"].gt(1e-9)
    ).any()


def test_default_energy_flow_has_nonidealized_golden_results() -> None:
    summary = AgriEnergyFlowService().simulate(generate_agri_park_profiles(2025, 60)).summary
    assert summary["annual_demand_mwh"] == pytest.approx(8902.355703, abs=1e-5)
    assert summary["annual_pv_generation_mwh"] == pytest.approx(2814.957496, abs=1e-5)
    assert summary["annual_direct_green_injected_mwh"] == pytest.approx(4444.548826, abs=1e-5)
    assert summary["annual_direct_green_line_loss_mwh"] == pytest.approx(155.559209, abs=1e-5)
    assert summary["annual_grid_import_mwh"] == pytest.approx(2256.274874, abs=1e-5)
    assert summary["physical_green_match_rate_percent"] == pytest.approx(74.653171, abs=1e-5)
    assert summary["annual_carbon_emissions_tco2"] == pytest.approx(1241.055681, abs=1e-5)
    assert 0.0 < summary["physical_green_match_rate_percent"] < 100.0
    assert summary["annual_curtailment_mwh"] > 0.0


def test_annual_load_allocations_sum_to_annual_demand() -> None:
    result = AgriEnergyFlowService().simulate(generate_agri_park_profiles(2025, 60))
    load_flows = result.annual_flows[result.annual_flows["类型"].eq("负荷供能")]
    assert float(load_flows["电量/兆瓦时"].sum()) == pytest.approx(
        result.summary["annual_demand_mwh"], abs=1e-6
    )
    assert set(load_flows["去向"]) == {"灌溉与水泵", "粮食烘干与加工", "仓储与冷链", "公共与辅助"}


def test_direct_green_injection_equals_delivery_plus_line_loss() -> None:
    result = AgriEnergyFlowService().simulate(generate_agri_park_profiles(2025, 60))
    dispatch = result.dispatch
    residual = (
        dispatch["direct_green_injected_mw"]
        - dispatch["direct_green_delivered_mw"]
        - dispatch["direct_green_line_loss_mw"]
    )
    assert float(residual.abs().max()) < 1e-12


def test_zero_battery_case_remains_balanced() -> None:
    request = replace(AgriEnergyFlowRequest(), battery_power_mw=0.0, battery_energy_mwh=0.0)
    result = AgriEnergyFlowService().simulate(generate_agri_park_profiles(2025, 60), request)
    assert result.summary["annual_battery_charge_mwh"] == 0.0
    assert result.summary["annual_battery_discharge_mwh"] == 0.0
    assert result.summary["max_system_balance_error_mw"] < 1e-9


def test_energy_flow_rejects_invalid_efficiency() -> None:
    request = replace(AgriEnergyFlowRequest(), battery_charge_efficiency=0.0)
    with pytest.raises(ValueError, match="储能效率"):
        AgriEnergyFlowService().simulate(generate_agri_park_profiles(2025, 60), request)
