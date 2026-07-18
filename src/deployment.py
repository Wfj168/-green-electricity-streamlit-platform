from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import sys
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class DeploymentCheck:
    key: str
    level: str
    title: str
    detail: str

    @property
    def failed(self) -> bool:
        return self.level == "error"


def validate_api_url(value: str) -> str | None:
    """Return a user-facing configuration error for an API base URL."""
    clean_value = value.strip()
    if not clean_value:
        return None
    parsed = urlparse(clean_value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "后台服务地址必须是完整的 http:// 或 https:// 地址"
    if parsed.username or parsed.password:
        return "后台服务地址不得包含账号或密码，请改用访问令牌"
    if parsed.query or parsed.fragment:
        return "后台服务地址不得包含查询参数或页面片段"
    return None


def _path_check(key: str, title: str, configured_path: str) -> DeploymentCheck:
    path = Path(configured_path).expanduser()
    parent = path if path.suffix == "" else path.parent
    candidate = parent
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    writable = candidate.exists() and os.access(candidate, os.W_OK)
    if writable:
        return DeploymentCheck(key, "ok", title, f"可写位置：{path}")
    return DeploymentCheck(key, "error", title, f"路径不可写或上级目录不存在：{path}")


def collect_deployment_checks(
    profile: str = "ui",
    environ: Mapping[str, str] | None = None,
    require_api: bool = False,
) -> list[DeploymentCheck]:
    """Collect deterministic checks without opening a network connection."""
    if profile not in {"ui", "api", "all"}:
        raise ValueError("profile必须是ui、api或all")
    env = os.environ if environ is None else environ
    checks: list[DeploymentCheck] = []

    python_ok = sys.version_info >= (3, 11)
    checks.append(
        DeploymentCheck(
            "python",
            "ok" if python_ok else "error",
            "Python运行时",
            f"当前版本 {sys.version_info.major}.{sys.version_info.minor}，要求3.11或更高版本",
        )
    )

    if profile in {"ui", "all"}:
        api_url = env.get("PLATFORM_API_URL", "").strip().rstrip("/")
        api_error = validate_api_url(api_url)
        if api_error:
            checks.append(DeploymentCheck("api_url", "error", "后台服务地址", api_error))
        elif not api_url:
            checks.append(
                DeploymentCheck(
                    "api_url",
                    "error" if require_api else "warning",
                    "后台服务地址",
                    "未配置后台服务，前台将以单机演示模式运行",
                )
            )
        else:
            checks.append(DeploymentCheck("api_url", "ok", "后台服务地址", api_url))

        auth_mode = env.get("PLATFORM_AUTH_MODE", "disabled").strip().lower()
        access_token = env.get("PLATFORM_ACCESS_TOKEN", "").strip()
        if api_url and auth_mode == "token" and not access_token:
            checks.append(
                DeploymentCheck("access_token", "error", "前台访问令牌", "令牌认证模式下必须配置访问令牌")
            )
        elif access_token:
            checks.append(DeploymentCheck("access_token", "ok", "前台访问令牌", "已配置且内容未显示"))

    if profile in {"api", "all"}:
        auth_mode = env.get("PLATFORM_AUTH_MODE", "disabled").strip().lower()
        if auth_mode not in {"disabled", "token"}:
            checks.append(
                DeploymentCheck("auth_mode", "error", "认证模式", "必须配置为disabled或token")
            )
        elif auth_mode == "disabled":
            checks.append(
                DeploymentCheck("auth_mode", "warning", "认证模式", "认证未启用，仅可用于本机或受控内网")
            )
        else:
            secret = env.get("PLATFORM_AUTH_SECRET", "")
            bootstrap_key = env.get("PLATFORM_BOOTSTRAP_KEY", "")
            checks.append(
                DeploymentCheck(
                    "auth_secret",
                    "ok" if len(secret) >= 32 else "error",
                    "认证签名密钥",
                    "长度符合要求" if len(secret) >= 32 else "长度必须不少于32个字符",
                )
            )
            checks.append(
                DeploymentCheck(
                    "bootstrap_key",
                    "ok" if len(bootstrap_key) >= 16 else "error",
                    "令牌启动密钥",
                    "长度符合要求" if len(bootstrap_key) >= 16 else "长度必须不少于16个字符",
                )
            )

        try:
            token_ttl = int(env.get("PLATFORM_TOKEN_TTL_SECONDS", "28800"))
        except ValueError:
            token_ttl = 0
        checks.append(
            DeploymentCheck(
                "token_ttl",
                "ok" if token_ttl > 0 else "error",
                "令牌有效期",
                f"{token_ttl}秒" if token_ttl > 0 else "必须是正整数秒数",
            )
        )
        checks.append(
            _path_check("database", "平台数据库", env.get("PLATFORM_DB_PATH", "var/platform.db"))
        )
        checks.append(
            _path_check("artifacts", "结果文件目录", env.get("PLATFORM_ARTIFACT_DIR", "var/artifacts"))
        )

    return checks
