from unittest.mock import AsyncMock

import pytest

from friends_bot_service.draw_entrant.usecases.unregister import (
    UnregisterDrawEntrant,
    UnregisterDrawEntrantOutcome,
)
from tests.usecases.factories import draw_entrant_key, registered_draw_entrant


@pytest.mark.asyncio
async def test_unregister_returns_not_found_when_entrant_missing():
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=None)
    use_case = UnregisterDrawEntrant()
    data = draw_entrant_key(user_id=42)

    result = await use_case.execute(data, repo)

    assert result.outcome is UnregisterDrawEntrantOutcome.NOT_FOUND
    repo.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_unregister_returns_already_inactive_when_entrant_is_inactive():
    repo = AsyncMock()
    repo.get = AsyncMock(
        return_value=registered_draw_entrant(user_id=42, is_active=False)
    )
    use_case = UnregisterDrawEntrant()
    data = draw_entrant_key(user_id=42)

    result = await use_case.execute(data, repo)

    assert result.outcome is UnregisterDrawEntrantOutcome.ALREADY_INACTIVE
    repo.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_unregister_deactivates_active_entrant_and_saves():
    repo = AsyncMock()
    registered = registered_draw_entrant(user_id=42, is_active=True)
    repo.get = AsyncMock(return_value=registered)
    use_case = UnregisterDrawEntrant()
    data = draw_entrant_key(user_id=42)

    result = await use_case.execute(data, repo)

    assert result.outcome is UnregisterDrawEntrantOutcome.SUCCESS
    assert registered.is_active is False
    repo.save.assert_awaited_once_with(registered)
