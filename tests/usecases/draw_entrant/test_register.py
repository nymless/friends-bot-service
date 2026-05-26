from unittest.mock import AsyncMock

import pytest

from friends_bot_service.draw_entrant.usecases.register import (
    RegisterDrawEntrant,
    RegisterDrawEntrantOutcome,
)
from tests.usecases.factories import draw_entrant


@pytest.mark.asyncio
async def test_register_draw_entrant_upserts_and_returns_success():
    repo = AsyncMock()
    use_case = RegisterDrawEntrant()
    data = draw_entrant(user_id=42, username="alice", full_name="Alice")

    result = await use_case.execute(data, repo)

    assert result.outcome is RegisterDrawEntrantOutcome.SUCCESS
    repo.upsert_active.assert_awaited_once_with(draw_entrant=data)
