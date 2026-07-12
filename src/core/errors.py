from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    field: str
    message: str


class PlatformError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        issues: list[ValidationIssue] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.issues = issues or []
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "issues": [asdict(issue) for issue in self.issues],
            "details": self.details,
        }


class InputValidationError(PlatformError):
    def __init__(self, issues: list[ValidationIssue]) -> None:
        summary = "；".join(f"{issue.field}: {issue.message}" for issue in issues[:5])
        if len(issues) > 5:
            summary += f"；另有{len(issues) - 5}项"
        super().__init__("INPUT_VALIDATION_ERROR", f"输入校验失败：{summary}", issues=issues)
