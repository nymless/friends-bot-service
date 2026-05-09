from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

import pytest
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from friends_bot_service.core import lock as lock_module
from friends_bot_service.models.base_model import Base


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Creates an isolated in-memory database session for a test."""

    # Create a fresh in-memory engine for this test only.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # Create all tables before yielding the session.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Open a session that keeps loaded objects available after commit.
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        # Hand the ready-to-use session to the test.
        yield session

    # Fully dispose the engine after the test finishes.
    await engine.dispose()


@pytest.fixture(autouse=True)
def clear_bot_chat_locks() -> Iterator[None]:
    """Resets in-memory game locks between tests."""

    # Clear locks before each test to avoid state leaking from previous runs.
    lock_module._chat_locks.clear()

    # Run the actual test body.
    yield

    # Clear locks again so failed tests also leave a clean state behind.
    lock_module._chat_locks.clear()


@pytest.fixture
def patch_sqlite_upsert(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., None]:
    """Patches repo-local insert functions to SQLite upsert for tests."""

    def apply(*repo_modules: Any) -> None:
        for repo_module in repo_modules:
            monkeypatch.setattr(repo_module, "insert", sqlite_insert)

    return apply
