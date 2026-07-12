from __future__ import annotations

from dataclasses import dataclass
import os
import secrets
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


ROLES = {"admin", "engineer", "viewer"}


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: str
    role: str


class AuthError(ValueError):
    pass


class AuthService:
    def __init__(
        self,
        mode: str = "disabled",
        secret: str = "",
        bootstrap_key: str = "",
        token_ttl_seconds: int = 28_800,
    ) -> None:
        if mode not in {"disabled", "token"}:
            raise ValueError("PLATFORM_AUTH_MODE必须是disabled或token")
        if mode == "token" and len(secret) < 32:
            raise ValueError("令牌模式要求PLATFORM_AUTH_SECRET至少32个字符")
        if mode == "token" and len(bootstrap_key) < 16:
            raise ValueError("令牌模式要求PLATFORM_BOOTSTRAP_KEY至少16个字符")
        self.mode = mode
        self.bootstrap_key = bootstrap_key
        self.token_ttl_seconds = token_ttl_seconds
        self.serializer = URLSafeTimedSerializer(secret or "local-development-only", salt="platform-auth-v1")

    @classmethod
    def from_env(cls) -> "AuthService":
        return cls(
            mode=os.getenv("PLATFORM_AUTH_MODE", "disabled").strip().lower(),
            secret=os.getenv("PLATFORM_AUTH_SECRET", ""),
            bootstrap_key=os.getenv("PLATFORM_BOOTSTRAP_KEY", ""),
            token_ttl_seconds=int(os.getenv("PLATFORM_TOKEN_TTL_SECONDS", "28800")),
        )

    def issue_token(self, bootstrap_key: str, user_id: str, role: str) -> str:
        if self.mode != "token":
            raise AuthError("当前未启用令牌认证")
        if not secrets.compare_digest(bootstrap_key, self.bootstrap_key):
            raise AuthError("启动密钥无效")
        if role not in ROLES:
            raise AuthError("角色必须是admin、engineer或viewer")
        clean_user_id = user_id.strip()
        if not clean_user_id:
            raise AuthError("用户标识不能为空")
        return self.serializer.dumps({"sub": clean_user_id, "role": role})

    def authenticate(self, authorization: str | None, fallback_user_id: str = "local-user") -> Principal:
        if self.mode == "disabled":
            return Principal(fallback_user_id or "local-user", "admin")
        if not authorization or not authorization.startswith("Bearer "):
            raise AuthError("缺少Bearer访问令牌")
        token = authorization.removeprefix("Bearer ").strip()
        try:
            payload: dict[str, Any] = self.serializer.loads(token, max_age=self.token_ttl_seconds)
        except SignatureExpired as exc:
            raise AuthError("访问令牌已过期") from exc
        except BadSignature as exc:
            raise AuthError("访问令牌无效") from exc
        user_id = str(payload.get("sub", "")).strip()
        role = str(payload.get("role", ""))
        if not user_id or role not in ROLES:
            raise AuthError("访问令牌内容无效")
        return Principal(user_id, role)
