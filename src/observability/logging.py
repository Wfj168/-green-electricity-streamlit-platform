from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
import sys
from typing import Any


EXTRA_FIELDS = (
    "event",
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "job_id",
    "worker_id",
    "project_id",
    "error_code",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_json_logging(level: str | None = None) -> None:
    root = logging.getLogger()
    configured = any(getattr(handler, "_platform_json_handler", False) for handler in root.handlers)
    root.setLevel((level or os.getenv("PLATFORM_LOG_LEVEL", "INFO")).upper())
    if configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler._platform_json_handler = True  # type: ignore[attr-defined]
    root.addHandler(handler)
