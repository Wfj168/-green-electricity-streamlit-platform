from __future__ import annotations

from dataclasses import asdict, replace
from io import BytesIO
from zipfile import ZipFile

import pytest

from src.application import ModelExecutionRequest, UnifiedModelService, list_model_specs
from src.storemore_engine import (
    default_capex_table,
    default_fuel_table,
    default_generator_table,
    default_storage_table,
)
from src.version import V17_MODEL_VERSION
from tests.test_realtime_regression import default_inputs


def test_model_catalog_exposes_both_supported_models() -> None:
    catalog = {item["kind"]: item for item in list_model_specs()}
    assert set(catalog) == {"realtime_dispatch", "integrated_planning"}
    assert catalog["integrated_planning"]["version"] == V17_MODEL_VERSION


def test_unified_service_runs_realtime_dispatch() -> None:
    payload = {
        "inputs": asdict(replace(default_inputs(), rolling_days=1)),
        "generator_table": default_generator_table().to_dict(orient="records"),
        "storage_table": default_storage_table().to_dict(orient="records"),
        "fuel_table": default_fuel_table().to_dict(orient="records"),
        "capex_table": default_capex_table().to_dict(orient="records"),
    }
    result = UnifiedModelService().run(ModelExecutionRequest("realtime_dispatch", payload))

    assert result.success is True
    assert result.metadata["model_kind"] == "realtime_dispatch"
    assert result.summary["dispatch_rows"] == 24
    assert result.artifact_bytes
    with ZipFile(BytesIO(result.artifact_bytes)) as archive:
        assert "execution.json" in archive.namelist()


@pytest.mark.parametrize("scenario_key", ["S0", "S4", "S7", "S8"])
def test_unified_service_runs_v17_planning_scenarios(scenario_key: str) -> None:
    result = UnifiedModelService().run(
        ModelExecutionRequest(
            "integrated_planning",
            {"scenario_key": scenario_key, "n_steps_per_hour": 1, "seed": 42},
        )
    )

    assert result.success is True, result.message
    assert result.metadata["model_kind"] == "integrated_planning"
    assert result.metadata["model_version"] == V17_MODEL_VERSION
    assert result.summary["scenario_key"] == scenario_key
    assert result.summary["dispatch_rows"] > 0
    assert "Annual CO2 emissions" in result.metrics
    assert result.tables is not None
    assert {"capacity", "dispatch", "cost", "carbon", "metrics", "diagnostics"}.issubset(result.tables)
    assert result.artifact_bytes
    with ZipFile(BytesIO(result.artifact_bytes)) as archive:
        assert {"data/dispatch.csv", "data/metrics.csv", "execution.json", "scenario.json"}.issubset(
            archive.namelist()
        )
