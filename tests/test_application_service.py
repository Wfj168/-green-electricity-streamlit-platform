from __future__ import annotations

from dataclasses import replace

import pytest

from src.application import SimulationRequest, SimulationService
from src.storemore_engine import (
    default_capex_table,
    default_fuel_table,
    default_generator_table,
    default_storage_table,
    simple_capacity_planning,
)
from src.version import PLATFORM_VERSION
from tests.test_realtime_regression import default_inputs


def request_with_defaults(**input_overrides) -> SimulationRequest:
    inputs = replace(default_inputs(), rolling_days=1, **input_overrides)
    return SimulationRequest(
        inputs=inputs,
        generator_table=default_generator_table(),
        storage_table=default_storage_table(),
        fuel_table=default_fuel_table(),
        capex_table=default_capex_table(),
    )


def test_service_returns_structured_input_error() -> None:
    response = SimulationService().run(request_with_defaults(total_demand=0.0, country_code=""))

    assert response["success"] is False
    assert response["error"]["code"] == "INPUT_VALIDATION_ERROR"
    fields = {issue["field"] for issue in response["error"]["issues"]}
    assert {"total_demand", "country_code"}.issubset(fields)


def test_service_rejects_invalid_storage_efficiency() -> None:
    request = request_with_defaults()
    storage = request.storage_table.copy()
    storage.loc[storage["Unit Name"] == "Liion storage", "Efficiency [-]"] = 1.2
    response = SimulationService().run(
        SimulationRequest(
            inputs=request.inputs,
            generator_table=request.generator_table,
            storage_table=storage,
            fuel_table=request.fuel_table,
            capex_table=request.capex_table,
        )
    )

    assert response["success"] is False
    assert response["error"]["code"] == "INPUT_VALIDATION_ERROR"
    assert any("Efficiency" in issue["field"] for issue in response["error"]["issues"])


def test_service_success_includes_model_traceability_metadata() -> None:
    response = SimulationService().run(request_with_defaults())

    assert response["success"] is True
    assert response["metadata"]["platform_version"] == PLATFORM_VERSION
    assert response["metadata"]["model_version"] == "storemore-lp-1.0"


def test_investment_restriction_switch_changes_capacity_limits() -> None:
    generators = default_generator_table()
    storage = default_storage_table()
    generators.loc[generators["Unit Name"] == "solar", "Max Investment [MW]"] = 5.0
    generators.loc[generators["Unit Name"] == "wind", "Max Investment [MW]"] = 7.0
    storage.loc[storage["Unit Name"] == "Liion storage", "Max Investment [MWh]"] = 9.0

    restricted = simple_capacity_planning(generators, storage, 1_000_000.0, True, True)
    unrestricted = simple_capacity_planning(generators, storage, 1_000_000.0, True, False)

    assert restricted == pytest.approx((5.0, 7.0, 9.0))
    assert unrestricted[0] > restricted[0]
    assert unrestricted[1] > restricted[1]
    assert unrestricted[2] > restricted[2]
