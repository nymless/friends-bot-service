from unittest.mock import AsyncMock

import pytest

from friends_bot_service.bot_admin.usecases.get_owner_bot import (
    GetOwnerBot,
    GetOwnerBotData,
    GetOwnerBotOutcome,
)
from tests.usecases.factories import registered_bot


@pytest.mark.asyncio
async def test_get_owner_bot_returns_not_found_when_bot_is_missing():
    repo = AsyncMock()
    repo.get_active_for_owner = AsyncMock(return_value=None)
    use_case = GetOwnerBot()

    result = await use_case.execute(GetOwnerBotData(owner_id=20, bot_id=99), repo)

    assert result.outcome is GetOwnerBotOutcome.NOT_FOUND
    assert result.bot is None


@pytest.mark.asyncio
async def test_get_owner_bot_returns_registered_bot():
    repo = AsyncMock()
    bot = registered_bot(bot_id=99, username="owned_bot")
    repo.get_active_for_owner = AsyncMock(return_value=bot)
    use_case = GetOwnerBot()

    result = await use_case.execute(GetOwnerBotData(owner_id=20, bot_id=99), repo)

    assert result.outcome is GetOwnerBotOutcome.SUCCESS
    assert result.bot is bot
