from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import BotCommandScopeAllGroupChats

from friends_bot_service.infra.texts.commands import BOT_COMMANDS
from friends_bot_service.master_bot.usecases.sync_commands import SyncBotCommands
from tests.usecases.factories import registered_bot
from tests.usecases.master_bot.helpers import FakeTempBot


@pytest.mark.asyncio
async def test_sync_runtime_bot_sets_commands_and_returns_true():
    cipher = AsyncMock()
    bot = AsyncMock()
    use_case = SyncBotCommands(cipher)

    result = await use_case.sync_runtime_bot(bot, 99)

    assert result is True
    bot.set_my_commands.assert_awaited_once_with(
        BOT_COMMANDS,
        scope=BotCommandScopeAllGroupChats(),
    )


@pytest.mark.asyncio
async def test_sync_runtime_bot_returns_false_when_telegram_call_fails():
    cipher = AsyncMock()
    bot = AsyncMock()
    bot.set_my_commands = AsyncMock(side_effect=RuntimeError("telegram down"))
    use_case = SyncBotCommands(cipher)

    result = await use_case.sync_runtime_bot(bot, 99)

    assert result is False


@pytest.mark.asyncio
async def test_sync_registered_bot_decrypts_token_and_syncs_commands():
    cipher = AsyncMock()
    cipher.decrypt = lambda token: f"plain:{token}"
    fake_bot = FakeTempBot()
    use_case = SyncBotCommands(cipher)
    bot = registered_bot(bot_id=99, encrypted_token="enc-token")

    with patch(
        "friends_bot_service.master_bot.usecases.sync_commands.Bot",
        return_value=fake_bot,
    ):
        result = await use_case.sync_registered_bot(bot)

    assert result is True
    fake_bot.set_my_commands.assert_awaited_once_with(
        BOT_COMMANDS,
        scope=BotCommandScopeAllGroupChats(),
    )


@pytest.mark.asyncio
async def test_sync_all_registered_bots_collects_failed_bot_names():
    cipher = AsyncMock()
    use_case = SyncBotCommands(cipher)
    first_bot = registered_bot(bot_id=1, username="first_bot")
    second_bot = registered_bot(bot_id=2, username="second_bot")

    with patch.object(
        use_case,
        "sync_registered_bot",
        new=AsyncMock(side_effect=[True, False]),
    ):
        failed = await use_case.sync_all_registered_bots(
            [first_bot, second_bot],
            bot_name=lambda bot: f"@{bot.username}",
        )

    assert failed == ["@second_bot"]


@pytest.mark.asyncio
async def test_sync_all_registered_bots_collects_exceptions_as_failures():
    cipher = AsyncMock()
    use_case = SyncBotCommands(cipher)
    bot = registered_bot(bot_id=1, username="broken_bot")

    with patch.object(
        use_case,
        "sync_registered_bot",
        new=AsyncMock(side_effect=RuntimeError("sync failed")),
    ):
        failed = await use_case.sync_all_registered_bots(
            [bot],
            bot_name=lambda registered: f"@{registered.username}",
        )

    assert failed == ["@broken_bot"]
