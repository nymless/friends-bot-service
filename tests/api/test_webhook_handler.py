from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from friends_bot_service.infra.api.app_state import WebhookAppState
from friends_bot_service.infra.api.webhook_handler import router


def create_test_app(*, bot=None, secret_token: str = "test-secret") -> FastAPI:
    """Builds a minimal FastAPI app for webhook handler tests."""

    app = FastAPI()
    app.state = WebhookAppState(
        dp=AsyncMock(),
        manager=SimpleNamespace(get_bot=lambda bot_id: bot),
        webhook_secret_token=secret_token,
        master_dp=AsyncMock(),
        master_bot=SimpleNamespace(session=SimpleNamespace(close=AsyncMock())),
    )
    app.include_router(router)
    return app


def test_webhook_rejects_request_with_invalid_secret_token():
    app = create_test_app(bot=SimpleNamespace(id=123))

    with (
        TestClient(app) as client,
        patch(
            "friends_bot_service.infra.api.webhook_handler.Update.model_validate"
        ) as model_validate_mock,
    ):
        response = client.post(
            "/webhook/123",
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
            json={"update_id": 1},
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "forbidden"}
    model_validate_mock.assert_not_called()


def test_webhook_ignores_unknown_bot_after_secret_check():
    app = create_test_app(bot=None)

    with (
        TestClient(app) as client,
        patch(
            "friends_bot_service.infra.api.webhook_handler.Update.model_validate"
        ) as model_validate_mock,
    ):
        response = client.post(
            "/webhook/999",
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
            json={"update_id": 1},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    model_validate_mock.assert_not_called()


def test_webhook_accepts_request_with_valid_secret_token():
    bot = SimpleNamespace(id=123)
    app = create_test_app(bot=bot)
    state: WebhookAppState = app.state
    update = SimpleNamespace(update_id=1)

    with (
        TestClient(app) as client,
        patch(
            "friends_bot_service.infra.api.webhook_handler.Update.model_validate",
            return_value=update,
        ) as model_validate_mock,
        patch(
            "friends_bot_service.infra.api.webhook_handler._feed_update",
            new=AsyncMock(),
        ) as feed_update_mock,
    ):
        response = client.post(
            "/webhook/123",
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
            json={"update_id": 1},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    model_validate_mock.assert_called_once_with({"update_id": 1})
    feed_update_mock.assert_awaited_once_with(state, bot, update)
