from unittest.mock import AsyncMock


async def invoke_run_with_unit_of_work(callback):
    """Runs a handler callback with a mocked unit of work."""

    uow = AsyncMock()
    uow.users = AsyncMock()
    uow.bots = AsyncMock()
    uow.games = AsyncMock()
    uow.stats = AsyncMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    return await callback(uow)
