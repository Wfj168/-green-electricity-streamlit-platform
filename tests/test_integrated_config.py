from __future__ import annotations

from dataclasses import replace

from src.application import get_integrated_scenario
from src.core import IntegratedPlanningConfig, scenario_fingerprint


def test_s8_configuration_builds_versioned_traceable_payload() -> None:
    config = IntegratedPlanningConfig.from_scenario("S8", get_integrated_scenario("S8"))
    payload = config.to_payload()

    assert not config.validate()
    assert payload["schema_version"] == "integrated-planning-v1"
    assert payload["model_kind"] == "integrated_planning"
    assert payload["scenario_key"] == "S8"
    assert payload["overrides"]["enable_endogenous_p2x"] is True
    assert len(scenario_fingerprint(payload)) == 64


def test_configuration_validation_reports_dependent_fields() -> None:
    base = IntegratedPlanningConfig.from_scenario("S4", get_integrated_scenario("S4"))
    invalid = replace(
        base,
        enable_battery=True,
        max_battery_energy_capacity=0.0,
        enable_endogenous_p2x=True,
        p2x_min_process_heat_substitution_share=0.0,
        max_electrolyzer_capacity=0.0,
    )

    fields = {issue.field for issue in invalid.validate()}
    assert {"battery", "max_electrolyzer_capacity", "p2x_min_process_heat_substitution_share"}.issubset(fields)


def test_fingerprint_changes_when_a_parameter_changes() -> None:
    base = IntegratedPlanningConfig.from_scenario("S4", get_integrated_scenario("S4"))
    changed = replace(base, max_pv_capacity=base.max_pv_capacity + 1.0)
    assert scenario_fingerprint(base.to_payload()) != scenario_fingerprint(changed.to_payload())
