from __future__ import annotations

import pytest

from src.model.agri_park_profiles import (
    PROFILE_SOURCE,
    generate_agri_park_profiles,
    summarize_agri_park_profiles,
    validate_agri_park_profiles,
)


def test_hourly_agri_park_profile_is_continuous_balanced_and_park_scaled() -> None:
    profiles = generate_agri_park_profiles(2025, 60)
    assert len(profiles) == 8760
    assert not validate_agri_park_profiles(profiles)
    assert profiles["total_meter_load_mw"].max() < 3.0
    assert set(profiles["source_reference"]) == {PROFILE_SOURCE}
    assert set(profiles["data_quality_flag"]) == {"合成"}
    assert "residential_load" not in profiles
    assert "low_altitude_electric_load" not in profiles


def test_agri_park_profile_has_explicit_golden_annual_loads() -> None:
    summary = summarize_agri_park_profiles(generate_agri_park_profiles(2025, 60)).set_index("负荷类别")
    assert summary.loc["灌溉与水泵", "年用电量/兆瓦时"] == pytest.approx(521.928997, abs=1e-5)
    assert summary.loc["粮食烘干与加工", "年用电量/兆瓦时"] == pytest.approx(3825.83, abs=1e-5)
    assert summary.loc["仓储与冷链", "年用电量/兆瓦时"] == pytest.approx(3287.876707, abs=1e-5)
    assert summary.loc["公共与辅助", "年用电量/兆瓦时"] == pytest.approx(1266.72, abs=1e-5)
    assert summary.loc["园区合计", "年用电量/兆瓦时"] == pytest.approx(8902.355703, abs=1e-5)


def test_15_minute_and_hourly_profiles_have_consistent_annual_energy() -> None:
    hourly = summarize_agri_park_profiles(generate_agri_park_profiles(2025, 60)).set_index("负荷类别")
    quarter = summarize_agri_park_profiles(generate_agri_park_profiles(2025, 15)).set_index("负荷类别")
    relative_gap = (
        hourly["年用电量/兆瓦时"] - quarter["年用电量/兆瓦时"]
    ).abs() / quarter["年用电量/兆瓦时"]
    assert float(relative_gap.max()) < 0.0001


def test_agricultural_calendar_drives_irrigation_and_processing() -> None:
    profiles = generate_agri_park_profiles(2025, 60).set_index("timestamp")
    assert profiles.loc["2025-05-10", "irrigation_load_mw"].max() > 1.0
    assert profiles.loc["2025-07-10", "irrigation_load_mw"].max() == 0.0
    assert profiles.loc["2025-10-10", "grain_processing_load_mw"].max() == 2.0
    assert profiles.loc["2025-07-10", "grain_processing_load_mw"].max() == 0.55


def test_profile_rejects_unsupported_resolution() -> None:
    with pytest.raises(ValueError, match="时间分辨率"):
        generate_agri_park_profiles(2025, 10)
