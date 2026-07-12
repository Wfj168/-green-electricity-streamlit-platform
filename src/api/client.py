from __future__ import annotations

import os
from typing import Any

import requests


class ApiClientError(RuntimeError):
    pass


class PlatformApiClient:
    def __init__(
        self,
        base_url: str | None = None,
        user_id: str | None = None,
        access_token: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("PLATFORM_API_URL", "")).rstrip("/")
        self.user_id = user_id or os.getenv("PLATFORM_USER_ID", "local-user")
        self.access_token = access_token or os.getenv("PLATFORM_ACCESS_TOKEN", "")
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    def _request(self, method: str, path: str, **kwargs) -> Any:
        if not self.configured:
            raise ApiClientError("尚未配置PLATFORM_API_URL")
        headers = dict(kwargs.pop("headers", {}))
        headers["X-User-ID"] = self.user_id
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        try:
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise ApiClientError(f"后台服务连接失败：{exc}") from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise ApiClientError(f"后台服务返回{response.status_code}：{detail}")
        return response.json()

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def list_projects(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/projects")

    def create_project(self, name: str, description: str = "") -> dict[str, Any]:
        return self._request("POST", "/api/v1/projects", json={"name": name, "description": description})

    def create_scenario(self, project_id: str, name: str, inputs: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST", f"/api/v1/projects/{project_id}/scenarios", json={"name": name, "inputs": inputs}
        )

    def create_job(self, project_id: str, scenario_version_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/projects/{project_id}/jobs",
            json={"scenario_version_id": scenario_version_id, "request": {}},
        )

    def list_jobs(self, project_id: str | None = None) -> list[dict[str, Any]]:
        params = {"project_id": project_id} if project_id else None
        return self._request("GET", "/api/v1/jobs", params=params)

    def get_result(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/jobs/{job_id}/result")

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/jobs/{job_id}/transition", json={"action": "cancel"})
