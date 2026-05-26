from unittest.mock import AsyncMock

import pytest

from friends_bot_service.bot_admin.usecases.list_owner_bots import (
    ListOwnerBots,
    ListOwnerBotsData,
)
from tests.usecases.factories import registered_bot


@pytest.mark.asyncio
async def test_list_owner_bots_returns_active_bots_for_owner():
    repo = AsyncMock()
    bots = (
        registered_bot(bot_id=1, username="first_bot"),
        registered_bot(bot_id=2, username="second_bot"),
    )
    repo.list_active_for_owner = AsyncMock(return_value=bots)
    use_case = ListOwnerBots()

    result = await use_case.execute(ListOwnerBotsData(owner_id=20), repo)

    assert result.bots == bots
    repo.list_active_for_owner.assert_awaited_once_with(20)
