from __future__ import annotations

import pytest

from src.model.agri_park_profiles import generate_agri_park_profiles
from src.model.agri_zero_carbon_optimizer import (
    AgriOptimizationRequest,
    AgriZeroCarbonOptimizer,
)


def _winter_week():
    return generate_agri_park_profiles(2025, 60).iloc[: 24 * 7].reset_index(drop=True)


def test_zero_carbon_optimizer_preserves_energy_tasks_and_physical_balance() -> None:
    result = AgriZeroCarbonOptimizer().optimize(
        _winter_week(),
        AgriOptimizationRequest(target_physical_green_share=1.0, planning_interval_hours=1),
    )
    assert result.success, result.status
    assert result.summary["annual_grid_import_mwh"] == pytest.approx(0.0, abs=1e-7)
    assert result.summary["physical_green_match_rate_percent"] == pytest.approx(100.0, abs=1e-7)
    assert result.summary["annual_carbon_emissions_tco2"] == pytest.approx(0.0, abs=1e-7)
    assert result.summary["max_bus_balance_error_mw"] < 1e-8
    assert result.summary["max_daily_production_task_energy_error_mwh"] < 1e-8
    assert result.summary["simultaneous_charge_discharge_hours"] == 0.0
    assert result.summary["simultaneous_grid_import_export_hours"] == 0.0
    assert sum(result.cost_breakdown.values()) == pytest.approx(result.summary["annual_total_cost_cny"])


def test_impossible_zero_carbon_configuration_is_reported_as_infeasible() -> None:
    result = AgriZeroCarbonOptimizer().optimize(
        _winter_week(),
        AgriOptimizationRequest(
            target_physical_green_share=1.0,
            allow_local_pv=False,
            allow_green_direct=False,
            allow_battery=False,
        ),
    )
    assert not result.success
    assert "没有满足目标的可行方案" in result.status


def test_planning_aggregation_preserves_annual_load_energy() -> None:
    profiles = generate_agri_park_profiles(2025, 60)
    aggregated = AgriZeroCarbonOptimizer._aggregate_for_planning(profiles, 3)
    assert len(aggregated) == 2920
    assert float(aggregated["total_meter_load_mw"].sum() * 3.0) == pytest.approx(
        float(profiles["total_meter_load_mw"].sum()),
        rel=1e-10,
    )


def test_invalid_green_target_and_planning_interval_are_rejected() -> None:
    optimizer = AgriZeroCarbonOptimizer()
    with pytest.raises(ValueError, match="物理绿电匹配目标"):
        optimizer.optimize(_winter_week(), AgriOptimizationRequest(target_physical_green_share=1.1))
    with pytest.raises(ValueError, match="容量规划时间间隔"):
        optimizer.optimize(_winter_week(), AgriOptimizationRequest(planning_interval_hours=5))
    with pytest.raises(ValueError, match="超过农业园区规划边界"):
        optimizer.optimize(_winter_week(), AgriOptimizationRequest(fixed_pv_capacity_mw=5.0))


def test_fixed_capacity_dispatch_does_not_silently_expand_assets() -> None:
    request = AgriOptimizationRequest(
        target_physical_green_share=0.0,
        fixed_pv_capacity_mw=1.0,
        fixed_green_direct_capacity_mw=1.0,
        fixed_battery_power_mw=0.5,
        fixed_battery_energy_mwh=1.0,
    )
    result = AgriZeroCarbonOptimizer().optimize(_winter_week(), request)
    assert result.success, result.status
    assert result.capacities["pv_capacity_mw"] == pytest.approx(1.0)
    assert result.capacities["green_direct_capacity_mw"] == pytest.approx(1.0)
    assert result.capacities["battery_power_mw"] == pytest.approx(0.5)
    assert result.capacities["battery_energy_mwh"] == pytest.approx(1.0)
