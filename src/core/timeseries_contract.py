from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


REQUIRED_15MIN_COLUMNS = {
    "timestamp": "ISO-8601时间戳",
    "electric_load_mw": "电负荷/MW",
    "pv_available_mw": "光伏可用功率/MW",
    "wind_available_mw": "风电可用功率/MW",
    "electricity_price_cny_per_mwh": "电价/CNY-MWh",
}

OPTIONAL_15MIN_COLUMNS = {
    "heat_load_mwth": "热负荷/MWth",
    "cooling_load_mwc": "冷负荷/MWc",
    "temperature_c": "环境温度/摄氏度",
}


@dataclass(frozen=True, slots=True)
class DataQualityIssue:
    code: str
    severity: str
    field: str
    row: int | None
    timestamp: str | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TimeSeriesValidationResult:
    valid: bool
    data: pd.DataFrame
    issues: tuple[DataQualityIssue, ...]
    summary: dict[str, Any]

    def issues_frame(self) -> pd.DataFrame:
        return pd.DataFrame([issue.to_dict() for issue in self.issues])


class FifteenMinuteDataContract:
    frequency = pd.Timedelta(minutes=15)

    def validate(self, source: pd.DataFrame) -> TimeSeriesValidationResult:
        data = source.copy()
        issues: list[DataQualityIssue] = []
        missing = [column for column in REQUIRED_15MIN_COLUMNS if column not in data.columns]
        for column in missing:
            issues.append(
                DataQualityIssue(
                    "MISSING_COLUMN",
                    "error",
                    column,
                    None,
                    None,
                    f"缺少必填列{column}，单位要求：{REQUIRED_15MIN_COLUMNS[column]}",
                )
            )
        if missing:
            return self._result(data, issues)

        parsed_timestamp = pd.to_datetime(data["timestamp"], errors="coerce")
        for index in data.index[parsed_timestamp.isna()]:
            issues.append(
                DataQualityIssue(
                    "INVALID_TIMESTAMP",
                    "error",
                    "timestamp",
                    self._row_number(index),
                    str(data.at[index, "timestamp"]),
                    "时间戳无法解析，应使用ISO-8601格式",
                )
            )
        data["timestamp"] = parsed_timestamp

        valid_timestamps = data["timestamp"].dropna()
        duplicate_mask = valid_timestamps.duplicated(keep=False)
        for index in valid_timestamps.index[duplicate_mask]:
            issues.append(
                DataQualityIssue(
                    "DUPLICATE_TIMESTAMP",
                    "error",
                    "timestamp",
                    self._row_number(index),
                    valid_timestamps.at[index].isoformat(),
                    "时间戳重复",
                )
            )
        if not valid_timestamps.is_monotonic_increasing:
            issues.append(
                DataQualityIssue(
                    "UNSORTED_TIMESTAMP",
                    "error",
                    "timestamp",
                    None,
                    None,
                    "时间戳必须严格递增",
                )
            )

        numeric_columns = [column for column in data.columns if column != "timestamp"]
        for column in numeric_columns:
            original = data[column]
            numeric = pd.to_numeric(original, errors="coerce")
            invalid_mask = numeric.isna() & original.notna()
            for index in data.index[invalid_mask]:
                timestamp = data.at[index, "timestamp"]
                issues.append(
                    DataQualityIssue(
                        "INVALID_NUMBER",
                        "error",
                        column,
                        self._row_number(index),
                        timestamp.isoformat() if pd.notna(timestamp) else None,
                        f"{column}必须是数值，当前值为{original.at[index]}",
                    )
                )
            data[column] = numeric

        nonnegative_columns = [
            "electric_load_mw",
            "pv_available_mw",
            "wind_available_mw",
            "heat_load_mwth",
            "cooling_load_mwc",
        ]
        for column in nonnegative_columns:
            if column not in data:
                continue
            for index in data.index[data[column] < 0]:
                timestamp = data.at[index, "timestamp"]
                issues.append(
                    DataQualityIssue(
                        "NEGATIVE_ENERGY_VALUE",
                        "error",
                        column,
                        self._row_number(index),
                        timestamp.isoformat() if pd.notna(timestamp) else None,
                        f"{column}不能小于0，单位由列名限定",
                    )
                )

        unique_timestamps = valid_timestamps.drop_duplicates().sort_values()
        if len(unique_timestamps) >= 2:
            expected = pd.date_range(unique_timestamps.iloc[0], unique_timestamps.iloc[-1], freq=self.frequency)
            actual = pd.DatetimeIndex(unique_timestamps)
            missing_timestamps = expected.difference(actual)
            for timestamp in missing_timestamps[:200]:
                issues.append(
                    DataQualityIssue(
                        "MISSING_INTERVAL",
                        "error",
                        "timestamp",
                        None,
                        timestamp.isoformat(),
                        "缺少15分钟数据点",
                    )
                )
            unexpected = actual.to_series().diff().dropna()
            invalid_intervals = unexpected[unexpected != self.frequency]
            for timestamp, interval in invalid_intervals.iloc[:200].items():
                issues.append(
                    DataQualityIssue(
                        "INVALID_INTERVAL",
                        "error",
                        "timestamp",
                        None,
                        timestamp.isoformat(),
                        f"相邻间隔为{interval}，要求15分钟",
                    )
                )

        data = data.sort_values("timestamp", kind="stable").reset_index(drop=True)
        return self._result(data, issues)

    @staticmethod
    def _row_number(index: Any) -> int | None:
        try:
            return int(index) + 2
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _result(data: pd.DataFrame, issues: list[DataQualityIssue]) -> TimeSeriesValidationResult:
        timestamps = data.get("timestamp", pd.Series(dtype="datetime64[ns]")).dropna()
        error_count = sum(issue.severity == "error" for issue in issues)
        warning_count = sum(issue.severity == "warning" for issue in issues)
        summary = {
            "rows": len(data),
            "start": timestamps.min().isoformat() if not timestamps.empty and hasattr(timestamps.min(), "isoformat") else None,
            "end": timestamps.max().isoformat() if not timestamps.empty and hasattr(timestamps.max(), "isoformat") else None,
            "frequency_minutes": 15,
            "error_count": error_count,
            "warning_count": warning_count,
            "required_columns": list(REQUIRED_15MIN_COLUMNS),
        }
        return TimeSeriesValidationResult(error_count == 0, data, tuple(issues), summary)


def sample_15min_data(days: int = 14, seed: int = 42) -> pd.DataFrame:
    if days < 3:
        raise ValueError("示例数据至少生成3天")
    rng = np.random.default_rng(seed)
    periods = days * 96
    timestamp = pd.date_range("2026-01-01", periods=periods, freq="15min")
    hour = timestamp.hour.to_numpy() + timestamp.minute.to_numpy() / 60.0
    weekday = timestamp.dayofweek.to_numpy()
    load = 48.0 + 10.0 * np.sin(2 * np.pi * (hour - 7) / 24) + 4.0 * (weekday < 5)
    load = np.maximum(load + rng.normal(0.0, 0.8, periods), 5.0)
    pv = np.maximum(45.0 * np.sin(np.pi * (hour - 6) / 12), 0.0)
    wind = np.maximum(16.0 + 5.0 * np.sin(2 * np.pi * np.arange(periods) / (96 * 3)) + rng.normal(0, 1, periods), 0)
    price = 420.0 + 140.0 * ((hour >= 17) & (hour < 22)) - 80.0 * ((hour >= 0) & (hour < 6))
    heat = np.maximum(22.0 - 0.4 * (hour - 6), 8.0)
    cooling = np.maximum(5.0 + 12.0 * np.sin(np.pi * (hour - 8) / 12), 3.0)
    return pd.DataFrame(
        {
            "timestamp": timestamp,
            "electric_load_mw": load,
            "pv_available_mw": pv,
            "wind_available_mw": wind,
            "electricity_price_cny_per_mwh": price,
            "heat_load_mwth": heat,
            "cooling_load_mwc": cooling,
        }
    )
