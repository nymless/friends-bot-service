from unittest.mock import AsyncMock

import pytest

from friends_bot_service.bot_admin.usecases.load_active_bots import LoadActiveBots
from tests.usecases.factories import registered_bot


@pytest.mark.asyncio
async def test_load_active_bots_starts_each_active_bot():
    repo = AsyncMock()
    runtime = AsyncMock()
    cipher = AsyncMock()
    cipher.decrypt = lambda token: f"plain:{token}"
    bots = (
        registered_bot(bot_id=1, encrypted_token="enc-1"),
        registered_bot(bot_id=2, encrypted_token="enc-2"),
    )
    repo.list_all_active = AsyncMock(return_value=bots)
    use_case = LoadActiveBots(cipher)

    result = await use_case.execute(repo, runtime)

    assert result.started_count == 2
    runtime.start_bot.assert_any_await("plain:enc-1")
    runtime.start_bot.assert_any_await("plain:enc-2")
    assert runtime.start_bot.await_count == 2


@pytest.mark.asyncio
async def test_load_active_bots_returns_zero_when_no_bots():
    repo = AsyncMock()
    runtime = AsyncMock()
    cipher = AsyncMock()
    repo.list_all_active = AsyncMock(return_value=())
    use_case = LoadActiveBots(cipher)

    result = await use_case.execute(repo, runtime)

    assert result.started_count == 0
    runtime.start_bot.assert_not_awaited()
