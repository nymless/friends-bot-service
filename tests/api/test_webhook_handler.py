from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from friends_bot_service.api.webhook_handler import router


def create_test_app(*, bot=None, secret_token: str = "test-secret") -> FastAPI:
    """Builds a minimal FastAPI app for webhook handler tests."""

    app = FastAPI()
    app.state.dp = AsyncMock()
    app.state.manager = SimpleNamespace(get_bot=lambda bot_id: bot)
    app.state.webhook_secret_token = secret_token
    app.include_router(router)
    return app


def test_webhook_rejects_request_with_invalid_secret_token():
    """
    Verify webhook protection against forged requests.

    Scenario:
    - the webhook endpoint receives a request with the wrong secret header

    Expected behavior:
    - the request is rejected with HTTP 403
    - update parsing is skipped
    """

    # Prepare an app with an active bot and a known secret.
    app = create_test_app(bot=SimpleNamespace(id=123))

    # The request must be rejected before any update validation runs.
    with (
        TestClient(app) as client,
        patch(
            "friends_bot_service.api.webhook_handler.Update.model_validate"
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
    """
    Verify webhook behavior for an inactive or unknown bot.

    Scenario:
    - the webhook endpoint receives a request with a valid secret header
    - no active bot is registered for the requested bot_id

    Expected behavior:
    - the endpoint returns the ignored status
    - update parsing is skipped
    """

    # Prepare an app where the bot manager cannot resolve the bot_id.
    app = create_test_app(bot=None)

    # A valid secret should pass the security check, then the endpoint exits early.
    with (
        TestClient(app) as client,
        patch(
            "friends_bot_service.api.webhook_handler.Update.model_validate"
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
    """
    Verify successful webhook delivery for a known bot.

    Scenario:
    - the webhook endpoint receives a request with the correct secret header
    - the requested bot exists in the manager

    Expected behavior:
    - the update is validated
    - dispatcher processing is scheduled in the background
    - the endpoint returns the ok status
    """

    # Prepare an app with an active bot and a fixed update object.
    bot = SimpleNamespace(id=123)
    app = create_test_app(bot=bot)
    update = SimpleNamespace(update_id=1)

    # Simulate successful update validation and background dispatch.
    with (
        TestClient(app) as client,
        patch(
            "friends_bot_service.api.webhook_handler.Update.model_validate",
            return_value=update,
        ) as model_validate_mock,
        patch(
            "friends_bot_service.api.webhook_handler._feed_update",
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
    feed_update_mock.assert_awaited_once_with(app.state.dp, bot, update)
