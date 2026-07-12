from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd
import pytest

from src.storemore_engine import (
    StoreMoreInputs,
    default_capex_table,
    default_fuel_table,
    default_generator_table,
    default_storage_table,
    generate_profiles,
    load_profiles_from_csv,
    run_storemore_simulation,
)


GOLDEN_PATH = Path(__file__).parent / "golden" / "realtime_default.json"


def default_inputs() -> StoreMoreInputs:
    return StoreMoreInputs(
        scenario_name="baseline",
        total_demand=1_000_000.0,
        service_life=25,
        import_price=90.0,
        export_price=70.0,
        import_export_capacity=500.0,
        rps_constraint=True,
        min_res_share=35.0,
        co2_constraint=False,
        max_co2=100_000.0,
        ceep_constraint=False,
        max_ceep=20.0,
        optimize_capacity=True,
        restrict_investments=False,
        rolling_days=3,
        country_code="CN",
    )


@pytest.fixture(scope="module")
def simulation() -> dict[str, object]:
    result = run_storemore_simulation(
        default_inputs(),
        default_generator_table(),
        default_storage_table(),
        default_fuel_table(),
        default_capex_table(),
    )
    assert result["success"] is True, result.get("message")
    return result


def test_generated_profiles_are_deterministic() -> None:
    first = generate_profiles(1_000_000.0, 90.0, 70.0, 72)
    second = generate_profiles(1_000_000.0, 90.0, 70.0, 72)
    pd.testing.assert_frame_equal(first, second)


def test_default_realtime_result_matches_golden_baseline(simulation: dict[str, object]) -> None:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    dispatch = simulation["dispatch"]
    rolling_log = simulation["rolling_log"]
    metrics = simulation["metrics"].set_index("Metric")["Value"].to_dict()

    assert len(dispatch) == golden["dispatch_rows"]
    assert len(rolling_log) == golden["rolling_rows"]
    for name, expected in golden["metrics"].items():
        assert metrics[name] == pytest.approx(expected, rel=1e-6, abs=1e-6), name


def test_power_balance_and_storage_bounds_hold(simulation: dict[str, object]) -> None:
    dispatch = simulation["dispatch"]
    balance = (
        dispatch["Solar"]
        + dispatch["Wind"]
        + dispatch["Gas"]
        + dispatch["Import"]
        + dispatch["Storage discharge"]
        + dispatch["Unmet"]
        - dispatch["Storage charge"]
        - dispatch["Export"]
        - dispatch["Excess"]
        - dispatch["Demand"]
    )
    assert float(np.abs(balance).max()) <= 1e-6
    assert float(dispatch["SOC"].min()) >= -1e-7

    final_soc = dispatch.groupby("Rolling day")["SOC"].last().to_numpy()
    logged_soc = simulation["rolling_log"]["Final SOC after saved horizon [MWh]"].to_numpy()
    np.testing.assert_allclose(final_soc, logged_soc, rtol=0, atol=1e-9)


def test_export_bundle_contains_reproducibility_artifacts(simulation: dict[str, object]) -> None:
    bundle = simulation["zip"]
    bundle.seek(0)
    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
    assert {
        "input_summary.csv",
        "input_profiles_used.csv",
        "dispatch_results.csv",
        "investment_results.csv",
        "key_indicators.csv",
        "rolling_log.csv",
        "capex_inputs.csv",
    }.issubset(names)


def test_uploaded_profile_csv_is_cleaned_and_bounded() -> None:
    raw = pd.DataFrame(
        {
            "period": range(1, 49),
            "demand": [None] + [100.0] * 47,
            "solar_cf": [1.5] * 48,
            "wind_cf": [-0.2] * 48,
            "import_price": [0.0] * 48,
            "export_price": [-1.0] * 48,
        }
    )
    uploaded = BytesIO(raw.to_csv(index=False).encode("utf-8"))
    profiles, message = load_profiles_from_csv(uploaded, "CN", 1_000_000.0, 90.0, 70.0, 48)

    assert "uploaded" in message.lower()
    assert profiles["Demand"].isna().sum() == 0
    assert profiles["Solar CF"].between(0, 1).all()
    assert profiles["Wind CF"].between(0, 1).all()
    assert (profiles["Import price"] >= 1).all()
    assert (profiles["Export price"] >= 0).all()


def test_short_uploaded_profile_is_rejected() -> None:
    raw = pd.DataFrame(
        {
            "demand": [100.0] * 24,
            "solar_cf": [0.5] * 24,
            "wind_cf": [0.5] * 24,
            "import_price": [90.0] * 24,
        }
    )
    uploaded = BytesIO(raw.to_csv(index=False).encode("utf-8"))
    with pytest.raises(ValueError, match="48 rows are required"):
        load_profiles_from_csv(uploaded, "CN", 1_000_000.0, 90.0, 70.0, 48)
