from __future__ import annotations

from pathlib import Path
import re


SCHEMA_PATH = Path(__file__).parents[1] / "deploy" / "postgres" / "init" / "001_v2_schema.sql"


def _schema() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def test_v2_schema_contains_all_business_domains() -> None:
    sql = _schema()
    required_tables = {
        "organizations",
        "parks",
        "park_zones",
        "accounts",
        "roles",
        "assets",
        "measurement_points",
        "measurements",
        "agricultural_tasks",
        "green_power_contracts",
        "parameter_sets",
        "parameter_values",
        "model_registry",
        "scenarios_v2",
        "optimization_runs_v2",
        "run_metrics",
        "energy_flow_intervals",
        "dispatch_intervals",
        "forecast_series",
        "storage_source_ledger",
        "carbon_ledger",
        "green_power_ledger",
        "alerts",
        "report_exports",
        "audit_events",
    }
    created_tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS\s+([a-z0-9_]+)", sql))
    assert required_tables <= created_tables


def test_v2_schema_enforces_rmb_and_parameter_evidence() -> None:
    sql = _schema()
    assert "CHECK (currency = 'CNY')" in sql
    assert "source_evidence_id UUID REFERENCES source_evidence(id)" in sql
    assert "source_grade TEXT NOT NULL CHECK (source_grade IN ('A', 'B', 'C', 'D', 'E'))" in sql


def test_v2_schema_separates_direct_injection_delivery_and_losses() -> None:
    sql = _schema()
    for column in (
        "direct_injected_kwh",
        "direct_delivered_kwh",
        "line_loss_kwh",
        "storage_loss_kwh",
        "balance_error_kwh",
    ):
        assert column in sql


def test_v2_schema_tracks_storage_energy_source() -> None:
    sql = _schema()
    for column in (
        "pv_soc_kwh",
        "direct_soc_kwh",
        "grid_soc_kwh",
        "unverifiable_soc_kwh",
        "discharge_pv_kwh",
        "discharge_direct_kwh",
        "discharge_grid_kwh",
    ):
        assert column in sql


def test_v2_measurements_have_time_series_indexes() -> None:
    sql = _schema()
    assert "idx_measurements_park_time" in sql
    assert "USING BRIN (measured_at)" in sql
