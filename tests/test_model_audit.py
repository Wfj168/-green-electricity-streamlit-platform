from __future__ import annotations

import pytest

from src.application import (
    ModelAuditService,
    ModelExecutionRequest,
    UnifiedModelService,
)
from src.model_adapter import build_scenario


@pytest.fixture(scope="module")
def s4_execution():
    execution = UnifiedModelService().run(
        ModelExecutionRequest(
            "integrated_planning",
            {"scenario_key": "S4", "n_steps_per_hour": 1, "seed": 42},
        )
    )
    assert execution.success is True, execution.message
    assert execution.tables is not None
    return execution


def test_v17_carbon_target_and_market_price_reach_the_solver(s4_execution) -> None:
    target = float(s4_execution.summary["carbon_target_tco2_per_year"])
    emissions = float(s4_execution.metrics["Annual CO2 emissions"])
    carbon_cost = float(s4_execution.metrics["Carbon external cost"])

    assert emissions <= target + 1e-6
    assert carbon_cost / emissions == pytest.approx(215.0, rel=1e-8)


def test_v17_default_result_passes_hard_audit_and_percentages_are_bounded(s4_execution) -> None:
    audit = ModelAuditService().analyze(
        metrics=s4_execution.metrics,
        tables=s4_execution.tables,
        scenario=build_scenario("S4"),
    )

    assert audit.review_count == 0, audit.checks.to_dict("records")
    assert audit.notice_count >= 1
    assert audit.overall_status == "通过（含提示）"
    assert s4_execution.metrics["Industrial-park local renewable coverage"] <= 100.0
