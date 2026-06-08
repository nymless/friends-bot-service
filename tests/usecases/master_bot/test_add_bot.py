from unittest.mock import AsyncMock

import pytest

from friends_bot_service.bot_admin.usecases.register_bot import RegisterBotOutcome
from friends_bot_service.master_bot.usecases.add_bot import (
    AddBot,
    AddBotData,
    AddBotOutcome,
)


@pytest.mark.asyncio
async def test_add_bot_persist_encrypts_token_and_registers_bot():
    cipher = AsyncMock()
    cipher.encrypt = lambda token: f"enc:{token}"
    repo = AsyncMock()
    commands_sync = AsyncMock()
    use_case = AddBot(cipher, commands_sync=commands_sync)
    data = AddBotData(
        bot_id=99,
        username="draw_bot",
        token="123:plain",
        owner_id=20,
    )

    outcome = await use_case.persist(data, repo)

    assert outcome is RegisterBotOutcome.SUCCESS
    repo.upsert.assert_awaited_once_with(
        bot_id=99,
        username="draw_bot",
        encrypted_token="enc:123:plain",
        owner_id=20,
    )


@pytest.mark.asyncio
async def test_add_bot_activate_returns_success_when_commands_sync_succeeds():
    cipher = AsyncMock()
    runtime = AsyncMock()
    started_bot = AsyncMock()
    runtime.start_bot = AsyncMock(return_value=started_bot)
    commands_sync = AsyncMock()
    commands_sync.sync_runtime_bot = AsyncMock(return_value=True)
    use_case = AddBot(cipher, commands_sync=commands_sync)
    data = AddBotData(
        bot_id=99,
        username="draw_bot",
        token="123:plain",
        owner_id=20,
    )

    result = await use_case.activate(data, runtime)

    assert result.outcome is AddBotOutcome.SUCCESS
    runtime.start_bot.assert_awaited_once_with("123:plain")
    commands_sync.sync_runtime_bot.assert_awaited_once_with(started_bot, 99)


@pytest.mark.asyncio
async def test_add_bot_activate_returns_commands_sync_failed():
    cipher = AsyncMock()
    runtime = AsyncMock()
    started_bot = AsyncMock()
    runtime.start_bot = AsyncMock(return_value=started_bot)
    commands_sync = AsyncMock()
    commands_sync.sync_runtime_bot = AsyncMock(return_value=False)
    use_case = AddBot(cipher, commands_sync=commands_sync)
    data = AddBotData(
        bot_id=99,
        username="draw_bot",
        token="123:plain",
        owner_id=20,
    )

    result = await use_case.activate(data, runtime)

    assert result.outcome is AddBotOutcome.COMMANDS_SYNC_FAILED
