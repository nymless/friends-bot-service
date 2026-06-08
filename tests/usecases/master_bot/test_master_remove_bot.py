from unittest.mock import AsyncMock

import pytest

from friends_bot_service.bot_admin.usecases.remove_bot import RemoveBotOutcome
from friends_bot_service.master_bot.usecases.remove_bot import RemoveBot, RemoveBotData


@pytest.mark.asyncio
async def test_remove_bot_deactivate_returns_not_found():
    repo = AsyncMock()
    repo.deactivate_for_owner = AsyncMock(return_value=False)
    use_case = RemoveBot()

    outcome = await use_case.deactivate(RemoveBotData(bot_id=99, owner_id=20), repo)

    assert outcome is RemoveBotOutcome.NOT_FOUND


@pytest.mark.asyncio
async def test_remove_bot_deactivate_returns_success():
    repo = AsyncMock()
    repo.deactivate_for_owner = AsyncMock(return_value=True)
    use_case = RemoveBot()

    outcome = await use_case.deactivate(RemoveBotData(bot_id=99, owner_id=20), repo)

    assert outcome is RemoveBotOutcome.SUCCESS


@pytest.mark.asyncio
async def test_remove_bot_stop_runtime_stops_bot():
    runtime = AsyncMock()
    use_case = RemoveBot()

    await use_case.stop_runtime(99, runtime, token="99:plain")

    runtime.stop_bot.assert_awaited_once_with(99, token="99:plain")
