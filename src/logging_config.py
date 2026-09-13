"""Structured logging with request correlation and secret redaction."""

import contextvars
import json
import logging
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

request_id_context: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)
SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "password",
    "password_hash",
    "refresh_token",
    "secret",
    "secret_key",
    "token", "id_token", "access_token", "new_password", "client_secret", "code", "grant", "verifier",
}


def redact(value: Any, key: str | None = None) -> Any:
    if key and key.lower() in SENSITIVE_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {item_key: redact(item_value, item_key) for item_key, item_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, (dict, list, tuple)):
            record.msg = redact(deepcopy(record.msg))
        if isinstance(record.args, dict):
            record.args = redact(deepcopy(record.args))
        # Redact query strings in uvicorn/httpx access messages for auth routes.
        if isinstance(record.args, tuple):
            record.args = tuple(v.split("?")[0] + "?[REDACTED]" if isinstance(v, str) and "/auth/" in v and "?" in v else v for v in record.args)
        record.request_id = request_id_context.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = record.msg if isinstance(record.msg, (dict, list)) else record.getMessage()
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", request_id_context.get()),
            "message": redact(message),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(SensitiveDataFilter())
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("uvicorn.access").addFilter(SensitiveDataFilter())
