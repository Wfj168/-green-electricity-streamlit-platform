from __future__ import annotations

import pytest

from src.application.green_direct_benefit_service import GreenDirectBenefitService
from src.model.agri_park_profiles import generate_agri_park_profiles


@pytest.fixture(scope="module")
def benefits():
    profiles = generate_agri_park_profiles(2025, 60)
    return GreenDirectBenefitService().evaluate(profiles)


def test_green_direct_benefits_compare_five_model_derived_schemes(benefits) -> None:
    schemes = benefits.schemes

    assert schemes["方案编号"].tolist() == ["G0", "G1", "G2", "G3", "G4"]
    assert (schemes["年总成本/元"] > 0).all()
    assert (schemes["最大母线平衡误差/兆瓦"].abs() <= 1e-7).all()
    assert schemes.loc[schemes["方案编号"] == "G0", "物理绿电匹配率/%"].iloc[0] == pytest.approx(0.0)


def test_green_direct_benefits_do_not_hide_unfavourable_results(benefits) -> None:
    schemes = benefits.schemes
    savings = schemes.set_index("方案编号")["相对基准年节省/元"]

    assert savings["G0"] == pytest.approx(0.0)
    assert all(isinstance(value, str) and value for value in schemes["结论"])
    assert "不展示P10、P50、P90" in benefits.methodology["uncertainty"]


def test_green_direct_attribution_reconciles_to_final_savings(benefits) -> None:
    schemes = benefits.schemes.set_index("方案编号")
    attributed = benefits.attribution["增量年成本节省/元"].sum()
    expected = schemes.loc["G0", "年总成本/元"] - schemes.loc["G4", "年总成本/元"]

    assert attributed == pytest.approx(expected, abs=1e-5)
    assert benefits.attribution["贡献环节"].tolist() == [
        "本地光伏",
        "绿电直连",
        "储能",
        "农业柔性与联合优化",
    ]


def test_contract_and_reliability_terms_are_explicit(benefits) -> None:
    assert benefits.contract_terms["transmissionFeeCnyPerMwh"] >= 0
    assert benefits.contract_terms["deviationPenaltyCnyPerMwh"] >= 0
    assert benefits.contract_terms["availabilityTarget"] <= 1
    assert (benefits.schemes["停电窗口缺供/兆瓦时"] >= 0).all()
    assert (benefits.schemes["停电损失避免/元"] >= -1e-8).all()
