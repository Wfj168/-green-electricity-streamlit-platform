from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

import pytest

from src.application import (
    GreenDirectRequest,
    GreenDirectService,
    ScenarioComparisonService,
)


def test_green_direct_service_uses_losses_and_fixed_costs() -> None:
    request = GreenDirectRequest(
        annual_demand_mwh=100_000.0,
        annual_green_mwh=50_000.0,
        target_share=0.8,
        planning_years=20,
        park_lcoe_cny_per_mwh=320.0,
        vpp_lcoe_cny_per_mwh=395.0,
        base_lcoe_cny_per_mwh=355.0,
    )
    result = GreenDirectService().evaluate(request)

    assert result.annual_target_green_mwh == pytest.approx(80_000.0)
    assert result.annual_green_gap_mwh == pytest.approx(30_000.0)
    assert len(result.options) == 3
    assert result.recommended_mode in set(result.options["方案"])
    assert result.recommended_cost_wan_cny == pytest.approx(result.options["规划期成本/万元"].min())


def test_green_direct_service_extracts_true_v17_metrics() -> None:
    table = GreenDirectService.from_v17_metrics(
        {
            "Park-internal green-direct cost": 48.0,
            "VPP aggregated green-direct cost": 60.0,
            "Remote green-base direct cost": 55.0,
        }
    )
    assert table.set_index("方案").loc["园区内新增绿电", "年度成本/万元"] == 4800.0


def test_s0_to_s8_comparison_is_computed_and_traceable() -> None:
    keys = [f"S{index}" for index in range(9)]
    result = ScenarioComparisonService().run(keys, n_steps_per_hour=1, seed=42)

    assert result.success is True, result.errors
    assert result.table["场景"].tolist() == keys
    assert result.table["是否成功"].all()
    assert result.table["参数指纹"].nunique() == 9
    assert result.table.loc[result.table["场景"] == "S0", "相对S0减排量/吨"].iloc[0] == 0
    assert result.table.loc[result.table["场景"] == "S8", "相对S0减排量/吨"].iloc[0] > 0
    assert "碳约束状态" in result.table
    assert "场景差异状态" in result.table
    repeated = result.table[result.table["场景"].isin(["S4", "S5", "S6", "S7"])]
    assert repeated["场景差异状态"].eq("新增约束未改变核心结果").all()
    with ZipFile(BytesIO(result.artifact_bytes)) as archive:
        assert "scenario_comparison.csv" in archive.namelist()
        assert "comparison_manifest.json" in archive.namelist()
        for key in keys:
            assert f"scenarios/{key}_result.zip" in archive.namelist()
