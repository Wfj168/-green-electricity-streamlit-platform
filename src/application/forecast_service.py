from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class ForecastEvaluationResult:
    target: str
    best_model: str
    metrics: pd.DataFrame
    validation: pd.DataFrame
    training_start: str
    training_end: str
    validation_start: str
    validation_end: str


@dataclass(frozen=True, slots=True)
class DayAheadForecast:
    version_id: str
    model_name: str
    target: str
    created_at: str
    training_end: str
    horizon_points: int
    data: pd.DataFrame
    evaluation_metrics: dict[str, Any]


class ForecastService:
    season_points = 96

    def evaluate_baselines(
        self,
        data: pd.DataFrame,
        target: str = "electric_load_mw",
        validation_points: int = 7 * 96,
    ) -> ForecastEvaluationResult:
        self._validate(data, target, validation_points)
        frame = data[["timestamp", target]].copy().sort_values("timestamp").reset_index(drop=True)
        series = pd.to_numeric(frame[target], errors="raise")
        frame["seasonal_naive"] = series.shift(self.season_points)
        frame["recent_mean"] = series.rolling(self.season_points, min_periods=self.season_points).mean().shift(1)
        validation = frame.iloc[-validation_points:].dropna().copy()
        if validation.empty:
            raise ValueError("有效验证数据不足，无法比较预测基准")
        rows = []
        for model in ("seasonal_naive", "recent_mean"):
            actual = validation[target].to_numpy(dtype=float)
            prediction = validation[model].to_numpy(dtype=float)
            rows.append(
                {
                    "model": model,
                    "MAE": float(np.mean(np.abs(prediction - actual))),
                    "RMSE": float(np.sqrt(np.mean((prediction - actual) ** 2))),
                    "sMAPE [%]": self._smape(actual, prediction),
                    "validation_points": len(validation),
                }
            )
        metrics = pd.DataFrame(rows).sort_values(["MAE", "RMSE"]).reset_index(drop=True)
        best_model = str(metrics.iloc[0]["model"])
        train = frame.iloc[:-validation_points]
        return ForecastEvaluationResult(
            target=target,
            best_model=best_model,
            metrics=metrics,
            validation=validation[["timestamp", target, "seasonal_naive", "recent_mean"]],
            training_start=frame.iloc[0]["timestamp"].isoformat(),
            training_end=train.iloc[-1]["timestamp"].isoformat(),
            validation_start=validation.iloc[0]["timestamp"].isoformat(),
            validation_end=validation.iloc[-1]["timestamp"].isoformat(),
        )

    def day_ahead(
        self,
        data: pd.DataFrame,
        evaluation: ForecastEvaluationResult,
        horizon_points: int = 96,
    ) -> DayAheadForecast:
        if horizon_points != 96:
            raise ValueError("日前计划必须包含96个15分钟点")
        frame = data[["timestamp", evaluation.target]].copy().sort_values("timestamp").reset_index(drop=True)
        series = pd.to_numeric(frame[evaluation.target], errors="raise")
        if len(frame) < self.season_points:
            raise ValueError("日前预测至少需要最近96个历史点")
        if evaluation.best_model == "seasonal_naive":
            values = series.iloc[-self.season_points:].to_numpy(dtype=float)
        elif evaluation.best_model == "recent_mean":
            values = np.repeat(float(series.iloc[-self.season_points:].mean()), horizon_points)
        else:
            raise ValueError(f"不支持的预测模型：{evaluation.best_model}")
        start = pd.Timestamp(frame.iloc[-1]["timestamp"]) + timedelta(minutes=15)
        timestamps = pd.date_range(start, periods=horizon_points, freq="15min")
        created_at = datetime.now(timezone.utc).isoformat()
        version_payload = {
            "algorithm": evaluation.best_model,
            "target": evaluation.target,
            "training_end": frame.iloc[-1]["timestamp"].isoformat(),
            "horizon_start": start.isoformat(),
            "horizon_points": horizon_points,
        }
        version_id = "forecast-" + hashlib.sha256(
            json.dumps(version_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        metrics = evaluation.metrics.set_index("model").loc[evaluation.best_model].to_dict()
        forecast = pd.DataFrame(
            {
                "timestamp": timestamps,
                f"forecast_{evaluation.target}": values,
                "model_name": evaluation.best_model,
                "forecast_version": version_id,
            }
        )
        return DayAheadForecast(
            version_id=version_id,
            model_name=evaluation.best_model,
            target=evaluation.target,
            created_at=created_at,
            training_end=frame.iloc[-1]["timestamp"].isoformat(),
            horizon_points=horizon_points,
            data=forecast,
            evaluation_metrics=metrics,
        )

    @staticmethod
    def _smape(actual: np.ndarray, prediction: np.ndarray) -> float:
        denominator = np.abs(actual) + np.abs(prediction)
        valid = denominator > 1e-12
        if not valid.any():
            return 0.0
        return float(200.0 * np.mean(np.abs(prediction[valid] - actual[valid]) / denominator[valid]))

    @staticmethod
    def _validate(data: pd.DataFrame, target: str, validation_points: int) -> None:
        if "timestamp" not in data or target not in data:
            raise ValueError(f"预测数据必须包含timestamp和{target}")
        if validation_points < 96:
            raise ValueError("验证集至少包含96个点")
        if len(data) < validation_points + 96:
            raise ValueError(f"数据至少需要{validation_points + 96}个15分钟点")
        if data[["timestamp", target]].isna().any().any():
            raise ValueError("预测输入不能包含空值")
