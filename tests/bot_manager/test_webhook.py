from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from friends_bot_service.infra.bot_manager.webhook import WebhookBotManager


@pytest.mark.asyncio
async def test_start_bot_sets_webhook_with_secret_token():
    """
    Verify webhook bot startup configuration.

    Scenario:
    - WebhookBotManager.start_bot is called for a new bot

    Expected behavior:
    - Telegram webhook is registered for the bot-specific URL
    - the configured secret token is sent to Telegram
    - the bot becomes active in the manager
    """

    # Prepare a fake aiogram bot instance returned by Bot(token).
    fake_bot = SimpleNamespace(
        get_me=AsyncMock(return_value=SimpleNamespace(id=321, username="game_bot")),
        set_webhook=AsyncMock(),
        session=SimpleNamespace(close=AsyncMock()),
    )
    manager = WebhookBotManager("https://example.com", "secret-token")

    # Run startup through the patched aiogram Bot constructor.
    with patch(
        "friends_bot_service.infra.bot_manager.webhook.Bot",
        return_value=fake_bot,
    ):
        bot = await manager.start_bot("321:token")

    # The webhook must include the secret token for request authentication.
    assert bot is fake_bot
    fake_bot.set_webhook.assert_awaited_once_with(
        url="https://example.com/webhook/321",
        secret_token="secret-token",
    )
    assert manager.get_bot(321) is fake_bot
