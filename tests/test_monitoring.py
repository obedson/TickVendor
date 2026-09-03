"""Vendor-neutral monitoring delivery tests."""
from src import monitoring


def test_monitoring_emits_correlation_id_without_secret(monkeypatch):
    calls = []
    class Response:
        def raise_for_status(self): pass
    monkeypatch.setattr(monitoring.settings, "metrics_endpoint", "https://metrics.example/events")
    monkeypatch.setattr(monitoring.settings, "monitoring_api_token", None)
    monkeypatch.setattr(monitoring.httpx, "post", lambda *args, **kwargs: calls.append((args, kwargs)) or Response())
    token = monitoring.request_id_context.set("request-123")
    try:
        monitoring.emit("payment_webhook_failure", provider="paystack")
    finally:
        monitoring.request_id_context.reset(token)
    assert calls[0][1]["json"] == {
        "event": "payment_webhook_failure", "request_id": "request-123", "provider": "paystack",
    }
    assert calls[0][1]["headers"] == {}