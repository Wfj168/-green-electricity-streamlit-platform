from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import create_app
from src.application.v2_model_facade import V2ModelFacade


def test_v2_overview_is_model_derived_and_traceable() -> None:
    payload = V2ModelFacade().overview()

    assert payload["meta"]["dataStatus"] == "演示"
    assert payload["meta"]["currency"] == "CNY"
    assert payload["meta"]["sourceReference"]
    assert payload["meta"]["runId"]
    assert payload["meta"]["modelVersion"]
    assert payload["meta"]["parameterVersion"]
    assert len(payload["loads"]) == 4
    assert len(payload["trend"]) == 24
    assert payload["annualSummary"]["max_bus_balance_error_mw"] <= 1e-7
    assert abs(payload["metrics"]["busBalanceErrorMw"]) <= 1e-7
    assert payload["metrics"]["directInjectedMw"] >= payload["metrics"]["directDeliveredMw"]


def test_v2_parameter_registry_exposes_sources_and_methods() -> None:
    payload = V2ModelFacade().parameters()

    assert payload["meta"]["count"] == len(payload["parameters"])
    assert payload["meta"]["currency"] == "CNY"
    assert payload["meta"]["count"] >= 70
    assert all(item["source_reference"] for item in payload["parameters"])
    assert all(item["setting_method"] for item in payload["parameters"])


def test_v2_api_exposes_overview_and_rejects_bad_resolution(tmp_path) -> None:
    client = TestClient(create_app(tmp_path / "v2-api.db"))

    response = client.get("/api/v2/overview")
    assert response.status_code == 200
    assert response.json()["meta"]["currency"] == "CNY"
    assert client.get("/api/v2/parameters").status_code == 200
    invalid = client.get("/api/v2/overview?resolution_minutes=10")
    assert invalid.status_code == 422
    assert "15、30或60分钟" in invalid.json()["detail"]


def test_v2_forecast_center_has_96_point_traceable_series() -> None:
    payload = V2ModelFacade().forecast_center()

    assert payload["meta"]["dataStatus"] == "演示"
    assert payload["meta"]["intervalMinutes"] == 15
    assert payload["meta"]["horizonPoints"] == 96
    assert [item["code"] for item in payload["series"]] == [
        "load",
        "pv",
        "direct",
        "weather",
        "price",
        "task",
    ]
    assert all(len(item["values"]) == 96 for item in payload["series"])
    assert all(item["evaluation"] for item in payload["series"])


def test_v2_asset_register_is_explicitly_pending_field_verification() -> None:
    payload = V2ModelFacade().asset_register()

    assert payload["meta"]["dataStatus"] == "待现场核验"
    assert len(payload["energyAssets"]) == 4
    assert len(payload["agriculturalAssets"]) == 4
    assert len(payload["meters"]) == 8
    assert all(item["qualityStatus"] == "待接入" for item in payload["meters"])
