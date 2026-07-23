from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.core.agri_parameter_registry import phase1_parameter_value


PROFILE_VERSION = "agri-park-demo-2025-v1"
PROFILE_SOURCE = "第一阶段农业园区可追溯演示基准；非同江实际园区实测数据"


@dataclass(frozen=True, slots=True)
class AgriParkProfileAssumptions:
    irrigation_morning_power_mw: float = phase1_parameter_value("load.irrigation.peak_mw")
    irrigation_afternoon_power_mw: float = 0.90
    processing_peak_power_mw: float = phase1_parameter_value("load.processing.peak_mw")
    storage_power_limit_mw: float = 0.65
    auxiliary_power_limit_mw: float = phase1_parameter_value("load.auxiliary.peak_mw")
    direct_green_capacity_mw: float = phase1_parameter_value("green_direct.max_capacity_mw")
    irrigation_start_month_day: tuple[int, int] = (4, 20)
    irrigation_end_month_day: tuple[int, int] = (6, 10)
    harvest_start_month_day: tuple[int, int] = (9, 15)
    harvest_end_month_day: tuple[int, int] = (11, 30)


def _date_mask(
    timestamps: pd.DatetimeIndex,
    start_month_day: tuple[int, int],
    end_month_day: tuple[int, int],
) -> np.ndarray:
    month_day = timestamps.month * 100 + timestamps.day
    start = start_month_day[0] * 100 + start_month_day[1]
    end = end_month_day[0] * 100 + end_month_day[1]
    return np.asarray((month_day >= start) & (month_day <= end), dtype=bool)


def _tou_buy_price(hour: np.ndarray) -> np.ndarray:
    return np.select(
        [
            (hour >= 0.0) & (hour < 7.0),
            (hour >= 7.0) & (hour < 11.0),
            (hour >= 11.0) & (hour < 16.0),
            (hour >= 16.0) & (hour < 22.0),
        ],
        [300.0, 520.0, 430.0, 850.0],
        default=350.0,
    )


def generate_agri_park_profiles(
    year: int = 2025,
    resolution_minutes: int = 60,
    assumptions: AgriParkProfileAssumptions | None = None,
) -> pd.DataFrame:
    if resolution_minutes not in {15, 30, 60}:
        raise ValueError("时间分辨率只支持15、30或60分钟")
    assumptions = assumptions or AgriParkProfileAssumptions()
    timestamps = pd.date_range(
        start=f"{year}-01-01 00:00:00",
        end=f"{year + 1}-01-01 00:00:00",
        freq=f"{resolution_minutes}min",
        inclusive="left",
    )
    hour = timestamps.hour.to_numpy(dtype=float) + timestamps.minute.to_numpy(dtype=float) / 60.0
    day_of_year = timestamps.dayofyear.to_numpy(dtype=float)
    weekday = timestamps.dayofweek.to_numpy()

    irrigation_season = _date_mask(
        timestamps,
        assumptions.irrigation_start_month_day,
        assumptions.irrigation_end_month_day,
    )
    irrigation_day_factor = 0.92 + 0.08 * np.sin(2.0 * np.pi * (day_of_year - 1.0) / 7.0)
    irrigation = np.zeros(len(timestamps), dtype=float)
    morning = irrigation_season & (hour >= 7.0) & (hour < 12.0)
    afternoon = irrigation_season & (hour >= 13.5) & (hour < 19.0)
    irrigation[morning] = assumptions.irrigation_morning_power_mw * irrigation_day_factor[morning]
    irrigation[afternoon] = assumptions.irrigation_afternoon_power_mw * irrigation_day_factor[afternoon]
    if resolution_minutes == 60:
        half_hour_start = irrigation_season & (hour >= 13.0) & (hour < 14.0)
        irrigation[half_hour_start] = (
            0.5 * assumptions.irrigation_afternoon_power_mw * irrigation_day_factor[half_hour_start]
        )

    harvest_season = _date_mask(
        timestamps,
        assumptions.harvest_start_month_day,
        assumptions.harvest_end_month_day,
    )
    processing = np.full(len(timestamps), 0.12, dtype=float)
    regular_work = (~harvest_season) & (weekday < 6) & (hour >= 8.0) & (hour < 17.0)
    processing[regular_work] = 0.55
    harvest_schedule = np.select(
        [
            (hour >= 6.0) & (hour < 8.0),
            (hour >= 8.0) & (hour < 12.0),
            (hour >= 12.0) & (hour < 13.0),
            (hour >= 13.0) & (hour < 18.0),
            (hour >= 18.0) & (hour < 22.0),
        ],
        [0.80, 1.70, 0.90, assumptions.processing_peak_power_mw, 1.30],
        default=0.25,
    )
    processing[harvest_season] = harvest_schedule[harvest_season]

    temperature = (
        4.5
        + 20.0 * np.cos(2.0 * np.pi * (day_of_year - 200.0) / 365.0)
        + 3.0 * np.sin(2.0 * np.pi * (hour - 14.0) / 24.0)
    )
    storage = (
        0.28
        + 0.008 * np.maximum(temperature - 5.0, 0.0)
        + 0.05 * ((hour >= 8.0) & (hour < 20.0))
        + 0.10 * harvest_season
    )
    storage = np.clip(storage, 0.20, assumptions.storage_power_limit_mw)

    auxiliary = (
        0.07
        + 0.12 * ((hour >= 7.0) & (hour < 19.0))
        + 0.04 * harvest_season
        + 0.02 * ((timestamps.month <= 2) | (timestamps.month >= 11))
    )
    auxiliary = np.clip(auxiliary, 0.0, assumptions.auxiliary_power_limit_mw)

    total_load = irrigation + processing + storage + auxiliary

    daylight_hours = 12.0 + 4.0 * np.sin(2.0 * np.pi * (day_of_year - 80.0) / 365.0)
    sunrise = 12.0 - daylight_hours / 2.0
    sunset = 12.0 + daylight_hours / 2.0
    daylight = (hour >= sunrise) & (hour <= sunset)
    solar_angle = np.zeros(len(timestamps), dtype=float)
    solar_angle[daylight] = np.pi * (hour[daylight] - sunrise[daylight]) / daylight_hours[daylight]
    deterministic_cloud = np.clip(
        0.82
        + 0.08 * np.sin(2.0 * np.pi * day_of_year / 9.0)
        + 0.05 * np.cos(2.0 * np.pi * day_of_year / 17.0),
        0.65,
        0.95,
    )
    pv_availability = np.zeros(len(timestamps), dtype=float)
    pv_availability[daylight] = (
        0.95 * np.sin(solar_angle[daylight]) ** 1.55 * deterministic_cloud[daylight]
    )
    pv_availability = np.clip(pv_availability, 0.0, 0.95)

    direct_green_capacity_factor = np.clip(
        0.46
        + 0.22 * pv_availability
        + 0.08 * np.sin(2.0 * np.pi * (hour + 2.0) / 24.0)
        + 0.06 * np.sin(2.0 * np.pi * day_of_year / 11.0),
        0.20,
        0.85,
    )
    direct_green_available = assumptions.direct_green_capacity_mw * direct_green_capacity_factor

    buy_price = _tou_buy_price(hour)
    sell_price = 0.35 * buy_price
    grid_emission_factor = phase1_parameter_value("grid.emission_factor_tco2_per_mwh")

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "irrigation_load_mw": irrigation,
            "grain_processing_load_mw": processing,
            "storage_cold_chain_load_mw": storage,
            "public_auxiliary_load_mw": auxiliary,
            "total_meter_load_mw": total_load,
            "pv_availability_pu": pv_availability,
            "direct_green_available_mw": direct_green_available,
            "grid_buy_price_cny_per_mwh": buy_price,
            "grid_sell_price_cny_per_mwh": sell_price,
            "grid_emission_factor_tco2_per_mwh": np.full(len(timestamps), grid_emission_factor),
            "ambient_temperature_c": temperature,
            "solar_irradiance_w_per_m2": 1000.0 * pv_availability / 0.95,
            "data_quality_flag": "合成",
            "source_reference": PROFILE_SOURCE,
            "profile_version": PROFILE_VERSION,
            "resolution_minutes": resolution_minutes,
        }
    )


def validate_agri_park_profiles(profiles: pd.DataFrame) -> list[str]:
    issues: list[str] = []
    load_columns = [
        "irrigation_load_mw",
        "grain_processing_load_mw",
        "storage_cold_chain_load_mw",
        "public_auxiliary_load_mw",
    ]
    required = [
        "timestamp",
        *load_columns,
        "total_meter_load_mw",
        "pv_availability_pu",
        "direct_green_available_mw",
        "grid_buy_price_cny_per_mwh",
        "grid_sell_price_cny_per_mwh",
        "grid_emission_factor_tco2_per_mwh",
        "data_quality_flag",
        "source_reference",
    ]
    missing = [column for column in required if column not in profiles]
    if missing:
        return [f"缺少字段：{','.join(missing)}"]
    if profiles.empty:
        return ["时序数据为空"]
    timestamps = pd.to_datetime(profiles["timestamp"], errors="coerce")
    if timestamps.isna().any() or timestamps.duplicated().any() or not timestamps.is_monotonic_increasing:
        issues.append("时间戳无效、重复或未按升序排列")
    if len(timestamps) > 1:
        intervals = timestamps.diff().dropna().dt.total_seconds().div(60.0)
        if intervals.nunique() != 1 or float(intervals.iloc[0]) not in {15.0, 30.0, 60.0}:
            issues.append("时间间隔不连续或不受支持")
    if (profiles[load_columns + ["total_meter_load_mw", "direct_green_available_mw"]].lt(0.0)).any().any():
        issues.append("负荷或绿电可用功率出现负值")
    expected_total = profiles[load_columns].sum(axis=1)
    if float((expected_total - profiles["total_meter_load_mw"]).abs().max()) > 1e-9:
        issues.append("四类分项负荷与园区总表不闭合")
    if not profiles["pv_availability_pu"].between(0.0, 1.0).all():
        issues.append("光伏可用出力超出0至1范围")
    if not profiles["grid_emission_factor_tco2_per_mwh"].ge(0.0).all():
        issues.append("电网排放因子出现负值")
    if profiles["source_reference"].astype(str).str.strip().eq("").any():
        issues.append("时序数据缺少来源标记")
    return issues


def summarize_agri_park_profiles(profiles: pd.DataFrame) -> pd.DataFrame:
    if profiles.empty:
        return pd.DataFrame(columns=["负荷类别", "年用电量/兆瓦时", "峰值/兆瓦", "负荷率/%"])
    if len(profiles) > 1:
        dt_hours = (
            pd.to_datetime(profiles["timestamp"]).diff().dropna().dt.total_seconds().median() / 3600.0
        )
    else:
        dt_hours = float(profiles.get("resolution_minutes", pd.Series([60])).iloc[0]) / 60.0
    mapping = {
        "灌溉与水泵": "irrigation_load_mw",
        "粮食烘干与加工": "grain_processing_load_mw",
        "仓储与冷链": "storage_cold_chain_load_mw",
        "公共与辅助": "public_auxiliary_load_mw",
        "园区合计": "total_meter_load_mw",
    }
    rows: list[dict[str, float | str]] = []
    annual_hours = len(profiles) * dt_hours
    for name, column in mapping.items():
        annual_energy = float(profiles[column].sum() * dt_hours)
        peak = float(profiles[column].max())
        load_factor = 100.0 * annual_energy / max(peak * annual_hours, 1e-9)
        rows.append(
            {
                "负荷类别": name,
                "年用电量/兆瓦时": annual_energy,
                "峰值/兆瓦": peak,
                "负荷率/%": load_factor,
            }
        )
    return pd.DataFrame(rows)
