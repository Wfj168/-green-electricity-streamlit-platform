from __future__ import annotations

from src.application.agri_stress_test_service import (
    AgriReferenceCapacities,
    AgriStressTestService,
)
from src.model.agri_park_profiles import generate_agri_park_profiles


def test_stress_test_keeps_assets_fixed_and_reports_all_six_pressures() -> None:
    profiles = generate_agri_park_profiles(2025, 60).iloc[: 24 * 31].reset_index(drop=True)
    capacities = AgriReferenceCapacities(4.0, 2.60, 1.90, 7.60)
    result = AgriStressTestService().evaluate(profiles, capacities, planning_interval_hours=6)
    assert result.table["压力编号"].tolist() == [
        "BASE",
        "STRESS-PV",
        "STRESS-IRR",
        "STRESS-PROC",
        "STRESS-DIRECT",
        "STRESS-PRICE",
        "STRESS-GRID",
    ]
    for scenario in result.scenario_results.values():
        if scenario.success:
            assert scenario.capacities["pv_capacity_mw"] == capacities.pv_capacity_mw
            assert scenario.capacities["green_direct_capacity_mw"] == capacities.green_direct_capacity_mw
            assert scenario.capacities["battery_power_mw"] == capacities.battery_power_mw
            assert scenario.capacities["battery_energy_mwh"] == capacities.battery_energy_mwh
    base = result.table.set_index("压力编号").loc["BASE"]
    price = result.table.set_index("压力编号").loc["STRESS-PRICE"]
    assert price["年总成本/万元"] > base["年总成本/万元"]


def test_direct_restriction_reduces_green_supply_without_changing_load_definition() -> None:
    service = AgriStressTestService()
    profiles = generate_agri_park_profiles(2025, 60).iloc[:48].reset_index(drop=True)
    restricted = service._direct_restriction(profiles)
    assert restricted["total_meter_load_mw"].equals(profiles["total_meter_load_mw"])
    assert (restricted["direct_green_available_mw"] == profiles["direct_green_available_mw"] * 0.60).all()
