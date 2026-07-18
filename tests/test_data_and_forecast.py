from __future__ import annotations

import pytest

from src.application import ForecastService, IntradayRollingRequest, IntradayRollingService
from src.core import FifteenMinuteDataContract, sample_15min_data


def test_sample_data_satisfies_15_minute_contract() -> None:
    source = sample_15min_data(days=14, seed=42)
    result = FifteenMinuteDataContract().validate(source)

    assert result.valid is True
    assert not result.issues
    assert result.summary["rows"] == 14 * 96
    assert result.summary["frequency_minutes"] == 15


def test_contract_reports_column_row_timestamp_and_unit_errors() -> None:
    source = sample_15min_data(days=3, seed=42)
    source.loc[20, "electric_load_mw"] = -1.0
    source["pv_available_mw"] = source["pv_available_mw"].astype(object)
    source.loc[30, "pv_available_mw"] = "not-a-number"
    source = source.drop(index=40)
    result = FifteenMinuteDataContract().validate(source)

    assert result.valid is False
    issues = result.issues_frame()
    assert {"NEGATIVE_ENERGY_VALUE", "INVALID_NUMBER", "MISSING_INTERVAL"}.issubset(set(issues["code"]))
    negative = issues[issues["code"] == "NEGATIVE_ENERGY_VALUE"].iloc[0]
    assert negative["field"] == "electric_load_mw"
    assert negative["row"] == 22
    assert negative["timestamp"]

    wrong_unit = source.rename(columns={"electric_load_mw": "electric_load_kw"})
    unit_result = FifteenMinuteDataContract().validate(wrong_unit)
    assert any(issue.code == "MISSING_COLUMN" and "MW" in issue.message for issue in unit_result.issues)


def test_forecast_baselines_are_evaluated_before_day_ahead_selection() -> None:
    validated = FifteenMinuteDataContract().validate(sample_15min_data(days=14, seed=7))
    service = ForecastService()
    evaluation = service.evaluate_baselines(validated.data, validation_points=7 * 96)
    forecast = service.day_ahead(validated.data, evaluation)
    repeated = service.day_ahead(validated.data, evaluation)

    assert set(evaluation.metrics["model"]) == {"seasonal_naive", "recent_mean"}
    assert evaluation.best_model == evaluation.metrics.iloc[0]["model"]
    assert {"MAE", "RMSE", "sMAPE [%]"}.issubset(evaluation.metrics.columns)
    assert len(forecast.data) == 96
    assert forecast.horizon_points == 96
    assert forecast.version_id == repeated.version_id
    assert forecast.data["forecast_version"].nunique() == 1


def test_intraday_plan_inherits_latest_soc_and_forecast_version() -> None:
    data = FifteenMinuteDataContract().validate(sample_15min_data(days=14, seed=11)).data
    forecast_service = ForecastService()
    evaluation = forecast_service.evaluate_baselines(data, validation_points=7 * 96)
    forecast = forecast_service.day_ahead(data, evaluation)
    plan = IntradayRollingService().build_plan(
        IntradayRollingRequest(
            forecast=forecast,
            scenario_key="R4",
            horizon_intervals=16,
            battery_soc_fraction=0.63,
            thermal_soc_fraction=0.41,
        )
    )

    assert plan.interval_minutes == 15
    assert plan.horizon_intervals == 16
    assert plan.forecast_version == forecast.version_id
    assert plan.inherited_state == {"battery_soc_fraction": 0.63, "thermal_soc_fraction": 0.41}
    assert plan.model_payload["overrides"] == {"bat_initial_soc": 0.63, "ts_initial_soc": 0.41}
    assert len(plan.model_payload["forecast"]) == 96

    with pytest.raises(ValueError, match="0至1"):
        IntradayRollingService().build_plan(
            IntradayRollingRequest(forecast=forecast, battery_soc_fraction=1.2)
        )
