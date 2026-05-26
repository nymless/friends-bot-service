from unittest.mock import AsyncMock

import pytest

from friends_bot_service.bot_admin.usecases.remove_bot import (
    RemoveBot,
    RemoveBotData,
    RemoveBotOutcome,
)


@pytest.mark.asyncio
async def test_remove_bot_returns_not_found_when_deactivation_fails():
    repo = AsyncMock()
    repo.deactivate_for_owner = AsyncMock(return_value=False)
    use_case = RemoveBot()

    result = await use_case.execute(RemoveBotData(bot_id=99, owner_id=20), repo)

    assert result.outcome is RemoveBotOutcome.NOT_FOUND
    repo.deactivate_for_owner.assert_awaited_once_with(99, 20)


@pytest.mark.asyncio
async def test_remove_bot_returns_success_when_deactivation_succeeds():
    repo = AsyncMock()
    repo.deactivate_for_owner = AsyncMock(return_value=True)
    use_case = RemoveBot()

    result = await use_case.execute(RemoveBotData(bot_id=99, owner_id=20), repo)

    assert result.outcome is RemoveBotOutcome.SUCCESS
