from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from friends_bot_service.bot_admin.domain import RegisteredBot
from friends_bot_service.infra.api.app_state import WebhookAppState
from friends_bot_service.infra.api.webhook_handler import router


def create_test_app(*, secret_token: str = "test-secret") -> FastAPI:
    master_bot = SimpleNamespace(id=999)
    app = FastAPI()
    app.state = WebhookAppState(
        dp=AsyncMock(),
        manager=AsyncMock(),
        webhook_secret_token=secret_token,
        master_dp=AsyncMock(),
        master_bot=master_bot,
    )
    app.include_router(router)
    return app


def test_webhook_rejects_request_with_invalid_secret_token():
    app = create_test_app()

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


def test_webhook_ignores_inactive_draw_bot_after_secret_check():
    app = create_test_app()

    with (
        TestClient(app) as client,
        patch(
            "friends_bot_service.infra.api.webhook_handler._load_active_draw_bot",
            new=AsyncMock(return_value=None),
        ) as load_bot_mock,
        patch(
            "friends_bot_service.infra.api.webhook_handler._feed_draw_bot_update",
            new=AsyncMock(),
        ) as feed_draw_bot_update_mock,
    ):
        response = client.post(
            "/webhook/123",
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
            json={"update_id": 1},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    load_bot_mock.assert_awaited_once_with(123)
    feed_draw_bot_update_mock.assert_not_awaited()


def test_webhook_accepts_active_draw_bot_after_secret_check():
    app = create_test_app()
    state: WebhookAppState = app.state
    registered_bot = RegisteredBot(
        bot_id=123,
        username="draw_bot",
        encrypted_token="enc-token",
        owner_id=1,
        is_active=True,
    )
    update = SimpleNamespace(update_id=1)

    with (
        TestClient(app) as client,
        patch(
            "friends_bot_service.infra.api.webhook_handler.Update.model_validate",
            return_value=update,
        ) as model_validate_mock,
        patch(
            "friends_bot_service.infra.api.webhook_handler._load_active_draw_bot",
            new=AsyncMock(return_value=registered_bot),
        ) as load_bot_mock,
        patch(
            "friends_bot_service.infra.api.webhook_handler._feed_draw_bot_update",
            new=AsyncMock(),
        ) as feed_draw_bot_update_mock,
    ):
        response = client.post(
            "/webhook/123",
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
            json={"update_id": 1},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    model_validate_mock.assert_called_once_with({"update_id": 1})
    load_bot_mock.assert_awaited_once_with(123)
    feed_draw_bot_update_mock.assert_awaited_once_with(state, registered_bot, update)


def test_webhook_routes_master_bot_updates_to_master_dispatcher():
    app = create_test_app()
    state: WebhookAppState = app.state
    update = SimpleNamespace(update_id=2)

    with (
        TestClient(app) as client,
        patch(
            "friends_bot_service.infra.api.webhook_handler.Update.model_validate",
            return_value=update,
        ),
        patch(
            "friends_bot_service.infra.api.webhook_handler._feed_master_update",
            new=AsyncMock(),
        ) as feed_master_update_mock,
        patch(
            "friends_bot_service.infra.api.webhook_handler._load_active_draw_bot",
            new=AsyncMock(),
        ) as load_bot_mock,
    ):
        response = client.post(
            "/webhook/999",
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
            json={"update_id": 2},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    feed_master_update_mock.assert_awaited_once_with(state, update)
    load_bot_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_feed_master_update_uses_master_dispatcher():
    master_bot = SimpleNamespace(id=999)
    master_dp = AsyncMock()
    manager = AsyncMock()
    state = WebhookAppState(
        dp=AsyncMock(),
        manager=manager,
        webhook_secret_token="test-secret",
        master_dp=master_dp,
        master_bot=master_bot,
    )
    update = SimpleNamespace(update_id=3)

    from friends_bot_service.infra.api.webhook_handler import _feed_master_update

    await _feed_master_update(state, update)
    master_dp.feed_update.assert_awaited_once_with(
        master_bot,
        update,
        manager=manager,
    )


@pytest.mark.asyncio
async def test_feed_draw_bot_update_creates_bot_from_db_record_and_closes_session():
    registered_bot = RegisteredBot(
        bot_id=123,
        username="draw_bot",
        encrypted_token="enc-token",
        owner_id=1,
        is_active=True,
    )
    fake_bot = SimpleNamespace(
        id=123,
        session=SimpleNamespace(close=AsyncMock()),
    )
    draw_dp = AsyncMock()
    state = WebhookAppState(
        dp=draw_dp,
        manager=AsyncMock(),
        webhook_secret_token="test-secret",
        master_dp=AsyncMock(),
        master_bot=SimpleNamespace(id=999),
    )
    update = SimpleNamespace(update_id=4)

    with (
        patch(
            "friends_bot_service.infra.api.webhook_handler._token_cipher.decrypt",
            return_value="123:plain",
        ),
        patch(
            "friends_bot_service.infra.api.webhook_handler.Bot",
            return_value=fake_bot,
        ),
    ):
        from friends_bot_service.infra.api.webhook_handler import _feed_draw_bot_update

        await _feed_draw_bot_update(state, registered_bot, update)

    draw_dp.feed_update.assert_awaited_once_with(fake_bot, update)
    fake_bot.session.close.assert_awaited_once()
