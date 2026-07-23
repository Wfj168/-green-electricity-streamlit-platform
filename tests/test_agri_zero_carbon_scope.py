from __future__ import annotations

from src.core import PHASE1_SCOPE, ZeroCarbonStatus, assess_zero_carbon_status


def test_phase1_scope_freezes_four_agricultural_load_categories() -> None:
    categories = {category.code for category in PHASE1_SCOPE.load_categories}
    assert categories == {
        "irrigation_pumping",
        "grain_processing",
        "storage_cold_chain",
        "public_auxiliary",
    }


def test_phase1_scope_separates_strategies_from_stress_tests() -> None:
    assert PHASE1_SCOPE.comparison_strategies == (
        "现状基准方案",
        "绿电直连方案",
        "零碳源网荷储协同方案",
    )
    assert not set(PHASE1_SCOPE.comparison_strategies).intersection(PHASE1_SCOPE.stress_tests)


def test_zero_carbon_claim_requires_traceable_balanced_zero_residual_result() -> None:
    achieved = assess_zero_carbon_status(
        0.0,
        energy_balance_valid=True,
        parameter_provenance_complete=True,
    )
    assert achieved.status is ZeroCarbonStatus.ACHIEVED

    incomplete = assess_zero_carbon_status(
        0.0,
        energy_balance_valid=True,
        parameter_provenance_complete=False,
    )
    assert incomplete.status is ZeroCarbonStatus.NOT_VERIFIABLE

    residual = assess_zero_carbon_status(
        1.0,
        energy_balance_valid=True,
        parameter_provenance_complete=True,
    )
    assert residual.status is ZeroCarbonStatus.NOT_ACHIEVED


def test_phase1_does_not_allow_offsets_to_create_zero_carbon_claim() -> None:
    result = assess_zero_carbon_status(
        0.0,
        energy_balance_valid=True,
        parameter_provenance_complete=True,
        unverified_offset_tco2=1.0,
    )
    assert result.status is ZeroCarbonStatus.NOT_VERIFIABLE
