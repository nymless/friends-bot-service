from unittest.mock import AsyncMock

import pytest

from friends_bot_service.draw_entrant.usecases.list import (
    ListDrawEntrants,
    ListDrawEntrantsData,
    ListDrawEntrantsOutcome,
)
from tests.usecases.factories import registered_draw_entrant


@pytest.mark.asyncio
async def test_list_draw_entrants_returns_no_entrants_when_roster_is_empty():
    repo = AsyncMock()
    repo.list_active_for_chat = AsyncMock(return_value=[])
    use_case = ListDrawEntrants()

    result = await use_case.execute(ListDrawEntrantsData(bot_id=1, chat_id=10), repo)

    assert result.outcome is ListDrawEntrantsOutcome.NO_ENTRANTS
    assert result.draw_entrants == ()
    repo.list_active_for_chat.assert_awaited_once_with(1, 10)


@pytest.mark.asyncio
async def test_list_draw_entrants_returns_active_entrants():
    repo = AsyncMock()
    entrants = (
        registered_draw_entrant(user_id=1, full_name="Alice"),
        registered_draw_entrant(user_id=2, full_name="Bob"),
    )
    repo.list_active_for_chat = AsyncMock(return_value=entrants)
    use_case = ListDrawEntrants()

    result = await use_case.execute(ListDrawEntrantsData(bot_id=1, chat_id=10), repo)

    assert result.outcome is ListDrawEntrantsOutcome.SUCCESS
    assert result.draw_entrants == entrants
