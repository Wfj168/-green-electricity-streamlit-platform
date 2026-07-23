from __future__ import annotations

import csv
from pathlib import Path

from src.core import (
    ASSET_COLUMNS,
    PHASE1_PARAMETER_REGISTRY,
    PRODUCTION_TASK_COLUMNS,
    SOURCE_LEDGER_COLUMNS,
    TIMESERIES_COLUMNS,
    ParameterSourceGrade,
    formal_readiness_gaps,
    phase1_parameter_value,
    validate_phase1_parameter_registry,
    validate_template_headers,
)


ROOT = Path(__file__).resolve().parents[1]


def _headers(path: str) -> list[str]:
    with (ROOT / path).open("r", encoding="utf-8-sig", newline="") as stream:
        return next(csv.reader(stream))


def test_phase1_parameter_registry_is_unique_ranged_and_traceable() -> None:
    assert len(PHASE1_PARAMETER_REGISTRY) >= 55
    assert not validate_phase1_parameter_registry()
    assert all(parameter.source_reference for parameter in PHASE1_PARAMETER_REGISTRY)
    assert all(parameter.setting_method for parameter in PHASE1_PARAMETER_REGISTRY)


def test_green_direct_defaults_have_one_registry_source() -> None:
    assert phase1_parameter_value("green_direct.park_lcoe_cny_per_mwh") == 320.0
    assert phase1_parameter_value("green_direct.vpp_lcoe_cny_per_mwh") == 395.0
    assert phase1_parameter_value("green_direct.base_lcoe_cny_per_mwh") == 355.0


def test_formal_readiness_exposes_demo_and_missing_project_values() -> None:
    gaps = formal_readiness_gaps()
    assert "load.irrigation.annual_energy_mwh" in gaps
    assert "grid.transformer_capacity_mva" in gaps
    assert "pv.capex_cny_per_mw" in gaps
    assert all(
        parameter.source_grade is not ParameterSourceGrade.E or parameter.code in gaps
        for parameter in PHASE1_PARAMETER_REGISTRY
    )


def test_empty_csv_templates_match_machine_readable_contracts() -> None:
    pairs = (
        ("data/templates/phase1_agri_park_timeseries_template.csv", TIMESERIES_COLUMNS),
        ("data/templates/phase1_agri_park_assets_template.csv", ASSET_COLUMNS),
        ("data/templates/phase1_agri_park_tasks_template.csv", PRODUCTION_TASK_COLUMNS),
        ("data/templates/phase1_source_ledger_template.csv", SOURCE_LEDGER_COLUMNS),
    )
    for path, columns in pairs:
        assert not validate_template_headers(_headers(path), columns)
