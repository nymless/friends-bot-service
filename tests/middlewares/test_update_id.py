from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from friends_bot_service.infra.middlewares.update_id import UpdateIdMiddleware


@pytest.mark.asyncio
async def test_update_id_middleware_injects_update_id() -> None:
    middleware = UpdateIdMiddleware()
    handler = AsyncMock(return_value="ok")
    event = SimpleNamespace(update_id=99)
    data: dict = {}

    result = await middleware(handler, event, data)

    assert result == "ok"
    assert data["update_id"] == "99"
    handler.assert_awaited_once_with(event, data)


@pytest.mark.asyncio
async def test_update_id_middleware_sets_none_when_missing() -> None:
    middleware = UpdateIdMiddleware()
    handler = AsyncMock(return_value="ok")
    event = SimpleNamespace()
    data: dict = {}

    await middleware(handler, event, data)

    assert data["update_id"] is None
