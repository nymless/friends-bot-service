from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from friends_bot_service.infra.api.app_state import WebhookAppState
from friends_bot_service.infra.api.webhook_handler import router
from friends_bot_service.infra.observability.metrics import WEBHOOK_REQUESTS_TOTAL
from friends_bot_service.infra.observability.setup import setup_webhook_observability


def create_observable_test_app(*, secret_token: str = "test-secret") -> FastAPI:
    bot = SimpleNamespace(id=123)
    app = FastAPI()
    app.state = WebhookAppState(
        dp=AsyncMock(),
        manager=SimpleNamespace(get_bot=lambda bot_id: bot),
        webhook_secret_token=secret_token,
        master_dp=AsyncMock(),
        master_bot=SimpleNamespace(session=SimpleNamespace(close=AsyncMock())),
    )
    setup_webhook_observability(app)
    app.include_router(router)
    return app


def test_webhook_app_does_not_expose_metrics_on_ingress_port():
    app = create_observable_test_app()

    with TestClient(app) as client:
        response = client.get("/metrics")

    assert response.status_code == 404


def test_webhook_middleware_records_status_label():
    app = create_observable_test_app()
    before = WEBHOOK_REQUESTS_TOTAL.labels(status="403")._value.get()

    with TestClient(app) as client:
        response = client.post(
            "/webhook/123",
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
            json={"update_id": 1},
        )

    assert response.status_code == 403
    after = WEBHOOK_REQUESTS_TOTAL.labels(status="403")._value.get()
    assert after == before + 1.0
