from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from src.application.forecast_service import DayAheadForecast


@dataclass(frozen=True, slots=True)
class IntradayRollingRequest:
    forecast: DayAheadForecast
    scenario_key: str = "R4"
    horizon_intervals: int = 16
    battery_soc_fraction: float = 0.5
    thermal_soc_fraction: float = 0.5
    seed: int = 42


@dataclass(frozen=True, slots=True)
class IntradayRollingPlan:
    run_id: str
    created_at: str
    forecast_version: str
    scenario_key: str
    interval_minutes: int
    horizon_intervals: int
    inherited_state: dict[str, float]
    model_payload: dict[str, Any]


class IntradayRollingService:
    def build_plan(self, request: IntradayRollingRequest) -> IntradayRollingPlan:
        if request.scenario_key not in {f"R{index}" for index in range(5)}:
            raise ValueError("日内运行场景必须是R0至R4")
        if not 1 <= request.horizon_intervals <= 96:
            raise ValueError("滚动窗口必须包含1至96个15分钟点")
        for name, value in {
            "battery_soc_fraction": request.battery_soc_fraction,
            "thermal_soc_fraction": request.thermal_soc_fraction,
        }.items():
            if not 0 <= value <= 1:
                raise ValueError(f"{name}必须在0至1之间")
        if request.forecast.horizon_points != 96 or len(request.forecast.data) != 96:
            raise ValueError("日内滚动必须继承完整96点日前预测")

        inherited_state = {
            "battery_soc_fraction": request.battery_soc_fraction,
            "thermal_soc_fraction": request.thermal_soc_fraction,
        }
        model_payload = {
            "schema_version": "intraday-rolling-v1",
            "model_kind": "integrated_planning",
            "scenario_key": request.scenario_key,
            "n_steps_per_hour": 4,
            "seed": request.seed,
            "forecast_version": request.forecast.version_id,
            "horizon_intervals": request.horizon_intervals,
            "overrides": {
                "bat_initial_soc": request.battery_soc_fraction,
                "ts_initial_soc": request.thermal_soc_fraction,
            },
            "forecast": request.forecast.data.to_dict(orient="records"),
        }
        identity = {
            "forecast_version": request.forecast.version_id,
            "scenario_key": request.scenario_key,
            "horizon_intervals": request.horizon_intervals,
            **inherited_state,
        }
        run_id = "intraday-" + hashlib.sha256(
            json.dumps(identity, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        return IntradayRollingPlan(
            run_id=run_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            forecast_version=request.forecast.version_id,
            scenario_key=request.scenario_key,
            interval_minutes=15,
            horizon_intervals=request.horizon_intervals,
            inherited_state=inherited_state,
            model_payload=model_payload,
        )
