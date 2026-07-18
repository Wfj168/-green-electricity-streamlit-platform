from __future__ import annotations

import pytest

from src.api.client import ApiClientError, PlatformApiClient
from src.deployment import collect_deployment_checks, validate_api_url


def test_api_url_validation_accepts_http_and_rejects_unsafe_values() -> None:
    assert validate_api_url("") is None
    assert validate_api_url("http://api:8000") is None
    assert validate_api_url("https://platform.example.com/api") is None
    assert validate_api_url("api:8000") is not None
    assert validate_api_url("https://user:secret@example.com") is not None
    assert validate_api_url("https://example.com?token=secret") is not None


def test_ui_preflight_allows_standalone_demo_but_can_require_api() -> None:
    standalone = collect_deployment_checks("ui", environ={})
    api_check = next(check for check in standalone if check.key == "api_url")
    assert api_check.level == "warning"
    assert not any(check.failed for check in standalone)

    required = collect_deployment_checks("ui", environ={}, require_api=True)
    assert next(check for check in required if check.key == "api_url").failed


def test_token_mode_preflight_requires_all_secrets(tmp_path) -> None:
    environment = {
        "PLATFORM_API_URL": "http://api:8000",
        "PLATFORM_AUTH_MODE": "token",
        "PLATFORM_DB_PATH": str(tmp_path / "platform.db"),
        "PLATFORM_ARTIFACT_DIR": str(tmp_path / "artifacts"),
    }
    checks = collect_deployment_checks("all", environ=environment)
    failed_keys = {check.key for check in checks if check.failed}
    assert {"access_token", "auth_secret", "bootstrap_key"}.issubset(failed_keys)


def test_invalid_client_configuration_fails_before_network(monkeypatch) -> None:
    def unexpected_request(*args, **kwargs):
        pytest.fail("invalid configuration must not open a network connection")

    monkeypatch.setattr("requests.request", unexpected_request)
    client = PlatformApiClient(base_url="not-a-url")
    with pytest.raises(ApiClientError, match="完整"):
        client.health()


def test_client_normalizes_configuration() -> None:
    client = PlatformApiClient(
        base_url="  http://api:8000/  ",
        user_id=" demo-user ",
        access_token=" token-value ",
    )
    assert client.base_url == "http://api:8000"
    assert client.user_id == "demo-user"
    assert client.access_token == "token-value"
