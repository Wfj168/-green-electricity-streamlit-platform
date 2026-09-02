from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import json
import os
import secrets
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


ROLES = {"admin", "engineer", "operator", "viewer", "auditor"}
PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 210_000


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
        accounts: dict[str, dict[str, Any]] | None = None,
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
        self.accounts = accounts or {}
        self.serializer = URLSafeTimedSerializer(secret or "local-development-only", salt="platform-auth-v1")

    @classmethod
    def from_env(cls) -> "AuthService":
        accounts: dict[str, dict[str, Any]] = {}
        raw_accounts = os.getenv("PLATFORM_USERS_JSON", "").strip()
        if raw_accounts:
            try:
                parsed = json.loads(raw_accounts)
            except json.JSONDecodeError as exc:
                raise ValueError("PLATFORM_USERS_JSON不是合法JSON") from exc
            if not isinstance(parsed, list):
                raise ValueError("PLATFORM_USERS_JSON必须是账号数组")
            for item in parsed:
                if not isinstance(item, dict):
                    raise ValueError("账号配置必须是对象")
                username = str(item.get("username", "")).strip()
                role = str(item.get("role", ""))
                password_hash = str(item.get("password_hash", ""))
                if not username or role not in ROLES or not password_hash:
                    raise ValueError("账号必须配置username、有效role和password_hash")
                accounts[username] = {
                    "password_hash": password_hash,
                    "role": role,
                    "display_name": str(item.get("display_name", username)).strip() or username,
                    "active": bool(item.get("active", True)),
                }
        return cls(
            mode=os.getenv("PLATFORM_AUTH_MODE", "disabled").strip().lower(),
            secret=os.getenv("PLATFORM_AUTH_SECRET", ""),
            bootstrap_key=os.getenv("PLATFORM_BOOTSTRAP_KEY", ""),
            token_ttl_seconds=int(os.getenv("PLATFORM_TOKEN_TTL_SECONDS", "28800")),
            accounts=accounts,
        )

    @staticmethod
    def hash_password(password: str, *, salt: bytes | None = None, iterations: int = PASSWORD_ITERATIONS) -> str:
        if len(password) < 10:
            raise ValueError("密码长度至少10个字符")
        if iterations < 100_000:
            raise ValueError("密码哈希迭代次数不得低于100000")
        salt_bytes = salt or secrets.token_bytes(18)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)
        encoded_salt = base64.urlsafe_b64encode(salt_bytes).decode("ascii").rstrip("=")
        encoded_digest = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return f"{PASSWORD_SCHEME}${iterations}${encoded_salt}${encoded_digest}"

    @staticmethod
    def verify_password(password: str, encoded: str) -> bool:
        try:
            scheme, iterations_text, salt_text, expected_text = encoded.split("$", 3)
            if scheme != PASSWORD_SCHEME:
                return False
            padding = lambda value: value + "=" * (-len(value) % 4)
            salt = base64.urlsafe_b64decode(padding(salt_text))
            expected = base64.urlsafe_b64decode(padding(expected_text))
            actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations_text))
            return secrets.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False

    def _serialize_principal(self, user_id: str, role: str) -> str:
        return self.serializer.dumps({"sub": user_id, "role": role})

    def login(self, username: str, password: str) -> tuple[str, Principal, str]:
        clean_username = username.strip()
        account = self.accounts.get(clean_username)
        if self.mode == "disabled":
            dev_username = os.getenv("PLATFORM_DEV_USERNAME", "admin").strip()
            dev_password = os.getenv("PLATFORM_DEV_PASSWORD", "")
            if not dev_password:
                raise AuthError("本地开发登录未配置；公开演示可直接进入平台")
            if not secrets.compare_digest(clean_username, dev_username) or not secrets.compare_digest(password, dev_password):
                raise AuthError("账号或密码错误")
            principal = Principal(clean_username, "admin")
            return self._serialize_principal(principal.user_id, principal.role), principal, "本地管理员"
        if account is None or not account["active"] or not self.verify_password(password, account["password_hash"]):
            raise AuthError("账号或密码错误")
        principal = Principal(clean_username, str(account["role"]))
        return self._serialize_principal(principal.user_id, principal.role), principal, str(account["display_name"])

    def safe_accounts(self) -> list[dict[str, str | bool]]:
        return [
            {"username": username, "displayName": str(account["display_name"]), "role": str(account["role"]), "active": bool(account["active"])}
            for username, account in sorted(self.accounts.items())
        ]

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
        return self._serialize_principal(clean_user_id, role)

    def authenticate(self, authorization: str | None, fallback_user_id: str = "local-user") -> Principal:
        if self.mode == "disabled" and not authorization:
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
