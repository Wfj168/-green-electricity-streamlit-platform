from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_v2_compose_has_frontend_api_worker_and_persistent_volume() -> None:
    compose = ROOT.joinpath("compose.v2.yaml").read_text(encoding="utf-8")

    assert "api:" in compose
    assert "worker:" in compose
    assert "frontend:" in compose
    assert "v2-platform-data:/app/var" in compose
    assert "PLATFORM_AUTH_MODE" in compose
    assert "condition: service_healthy" in compose


def test_v2_frontend_proxy_supports_spa_and_hides_source_maps() -> None:
    nginx = ROOT.joinpath("deploy/nginx.v2.conf").read_text(encoding="utf-8")
    dockerfile = ROOT.joinpath("deploy/frontend.Dockerfile").read_text(encoding="utf-8")

    assert "try_files $uri $uri/ /index.html" in nginx
    assert "proxy_pass http://api:8000" in nginx
    assert "\\.map$" in nginx
    assert "VITE_AUTH_REQUIRED" in dockerfile


def test_v2_api_container_runs_unprivileged_with_healthcheck_in_compose() -> None:
    api_dockerfile = ROOT.joinpath("deploy/api.Dockerfile").read_text(encoding="utf-8")
    compose = ROOT.joinpath("compose.v2.yaml").read_text(encoding="utf-8")

    assert "USER platform" in api_dockerfile
    assert "src.api.main:app" in api_dockerfile
    assert "http://127.0.0.1:8000/ready" in compose
