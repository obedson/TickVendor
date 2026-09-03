"""Vendor-neutral monitoring hooks using structured HTTP events."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from src.config import settings
from src.logging_config import request_id_context

logger = logging.getLogger("tickvendor.monitoring")


def emit(event: str, **fields: Any) -> None:
    payload = {"event": event, "request_id": request_id_context.get(), **fields}
    logger.info(payload)
    if settings.metrics_endpoint:
        headers = {}
        if settings.monitoring_api_token:
            headers["Authorization"] = f"Bearer {settings.monitoring_api_token.get_secret_value()}"
        httpx.post(settings.metrics_endpoint, json=payload, headers=headers, timeout=3).raise_for_status()


def capture_exception(exc: Exception, **fields: Any) -> None:
    payload = {"exception_type": type(exc).__name__, **fields}
    logger.exception({"event": "exception", "request_id": request_id_context.get(), **payload})
    try:
        emit("exception", **payload)
    except Exception:  # noqa: BLE001 - monitoring failures must not mask product errors
        logger.warning({"event": "monitoring_delivery_failed"})
