from __future__ import annotations

import json

from fastapi.testclient import TestClient

from src.api.main import create_app
from src.security import AuthService


def test_password_hash_is_salted_and_verifiable() -> None:
    password_hash = AuthService.hash_password("SafePassword-2026", salt=b"fixed-test-salt-01")

    assert password_hash.startswith("pbkdf2_sha256$")
    assert "SafePassword-2026" not in password_hash
    assert AuthService.verify_password("SafePassword-2026", password_hash)
    assert not AuthService.verify_password("wrong-password", password_hash)


def test_login_me_and_system_status_in_token_mode(tmp_path, monkeypatch) -> None:
    password_hash = AuthService.hash_password("SafePassword-2026", salt=b"fixed-test-salt-02")
    monkeypatch.setenv("PLATFORM_AUTH_MODE", "token")
    monkeypatch.setenv("PLATFORM_AUTH_SECRET", "s" * 32)
    monkeypatch.setenv("PLATFORM_BOOTSTRAP_KEY", "bootstrap-key-123456")
    monkeypatch.setenv(
        "PLATFORM_USERS_JSON",
        json.dumps(
            [
                {
                    "username": "admin",
                    "display_name": "系统管理员",
                    "role": "admin",
                    "password_hash": password_hash,
                    "active": True,
                }
            ]
        ),
    )
    client = TestClient(create_app(tmp_path / "auth-system.db"))

    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "SafePassword-2026"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["user"] == {"userId": "admin", "displayName": "系统管理员", "role": "admin"}
    headers = {"Authorization": f"Bearer {payload['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).json()["role"] == "admin"

    system = client.get("/api/v2/system-status", headers=headers)
    assert system.status_code == 200
    snapshot = system.json()
    assert snapshot["meta"]["dataStatus"] == "系统实时状态"
    assert snapshot["auth"]["mode"] == "token"
    assert snapshot["accounts"] == [{"username": "admin", "displayName": "系统管理员", "role": "admin", "active": True}]
    assert all("password" not in key.lower() for account in snapshot["accounts"] for key in account)
    assert any(event["action"] == "auth.login" for event in snapshot["auditEvents"])


def test_system_status_is_available_in_public_demo_mode(tmp_path) -> None:
    client = TestClient(create_app(tmp_path / "public-system.db"))

    response = client.get("/api/v2/system-status")
    assert response.status_code == 200
    assert response.json()["auth"]["modeName"] == "公开演示/本地开发"
