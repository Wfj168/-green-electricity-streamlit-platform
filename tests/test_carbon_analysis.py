from __future__ import annotations

import pandas as pd
import pytest

from src.application import CarbonAnalysisService, ModelExecutionRequest, UnifiedModelService
from src.model_adapter import build_scenario


def test_v17_carbon_sources_reconcile_and_avoidance_is_not_double_counted() -> None:
    execution = UnifiedModelService().run(
        ModelExecutionRequest(
            "integrated_planning",
            {"scenario_key": "S4", "n_steps_per_hour": 1, "seed": 42},
        )
    )
    assert execution.success is True, execution.message
    assert execution.tables is not None

    comparison = pd.DataFrame(
        {
            "场景": ["S0", "S4"],
            "是否成功": [True, True],
            "年度二氧化碳排放/吨": [20_000.0, execution.metrics["Annual CO2 emissions"]],
            "平均减排成本/元每吨": [None, 320.0],
        }
    )
    analysis = CarbonAnalysisService().analyze(
        metrics=execution.metrics,
        dispatch=execution.tables["dispatch"],
        scenario=build_scenario("S4"),
        scenario_key="S4",
        comparison=comparison,
        time_step_hours=float(execution.summary["time_step_hours"]),
        baseline_emissions_tco2=execution.summary["carbon_baseline_tco2_per_year"],
        target_emissions_tco2=execution.summary["carbon_target_tco2_per_year"],
    )

    assert analysis.source_breakdown["年度排放量/吨"].sum() == pytest.approx(
        analysis.annual_emissions_tco2, abs=1e-6
    )
    final_accounted = analysis.accounting.set_index("核算项目").loc["最终入账排放", "年度数量/吨"]
    assert final_accounted == pytest.approx(analysis.annual_emissions_tco2)
    assert analysis.target_emissions_tco2 == pytest.approx(
        execution.summary["carbon_target_tco2_per_year"]
    )
    assert analysis.average_abatement_cost_cny_per_tco2 == pytest.approx(320.0)
    assert "全生命周期" in set(analysis.boundary["边界项目"])
