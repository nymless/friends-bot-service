from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from friends_bot_service.infra.bot_manager.webhook import WebhookBotManager


@pytest.mark.asyncio
async def test_start_bot_sets_webhook_with_secret_token():
    fake_bot = SimpleNamespace(
        get_me=AsyncMock(return_value=SimpleNamespace(id=321, username="draw_bot")),
        set_webhook=AsyncMock(),
        session=SimpleNamespace(close=AsyncMock()),
    )
    manager = WebhookBotManager("https://example.com", "secret-token")

    with patch(
        "friends_bot_service.infra.bot_manager.webhook.Bot",
        return_value=fake_bot,
    ):
        bot = await manager.start_bot("321:token")

    assert bot is fake_bot
    fake_bot.set_webhook.assert_awaited_once_with(
        url="https://example.com/webhook/321",
        secret_token="secret-token",
    )


@pytest.mark.asyncio
async def test_register_webhook_sets_webhook_for_existing_bot():
    fake_bot = SimpleNamespace(
        id=111,
        get_me=AsyncMock(return_value=SimpleNamespace(id=111, username="master_bot")),
        set_webhook=AsyncMock(),
        session=SimpleNamespace(close=AsyncMock()),
    )
    manager = WebhookBotManager("https://example.com", "secret-token")

    bot = await manager.register_webhook(fake_bot)

    assert bot is fake_bot
    fake_bot.set_webhook.assert_awaited_once_with(
        url="https://example.com/webhook/111",
        secret_token="secret-token",
    )


@pytest.mark.asyncio
async def test_stop_bot_deletes_webhook_and_closes_session():
    fake_bot = SimpleNamespace(
        delete_webhook=AsyncMock(),
        session=SimpleNamespace(close=AsyncMock()),
    )
    manager = WebhookBotManager("https://example.com", "secret-token")

    with patch(
        "friends_bot_service.infra.bot_manager.webhook.Bot",
        return_value=fake_bot,
    ):
        await manager.stop_bot(321, token="321:token")

    fake_bot.delete_webhook.assert_awaited_once()
    fake_bot.session.close.assert_awaited_once()
