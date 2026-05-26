from unittest.mock import AsyncMock

import pytest

from friends_bot_service.bot_admin.usecases.register_bot import (
    RegisterBot,
    RegisterBotData,
    RegisterBotOutcome,
)


@pytest.mark.asyncio
async def test_register_bot_upserts_and_returns_success():
    repo = AsyncMock()
    use_case = RegisterBot()
    data = RegisterBotData(
        bot_id=99,
        username="game_bot",
        encrypted_token="encrypted",
        owner_id=20,
    )

    result = await use_case.execute(data, repo)

    assert result.outcome is RegisterBotOutcome.SUCCESS
    repo.upsert.assert_awaited_once_with(
        bot_id=99,
        username="game_bot",
        encrypted_token="encrypted",
        owner_id=20,
    )
