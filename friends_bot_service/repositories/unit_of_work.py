from types import TracebackType
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from friends_bot_service.repositories.sqlalchemy import (
    SqlAlchemyBotRepository,
    SqlAlchemyGameRepository,
    SqlAlchemyStatsRepository,
    SqlAlchemyUserRepository,
)
from friends_bot_service.usecases.ports import (
    BotRepository,
    GameRepository,
    StatsRepository,
    UserRepository,
)


class SqlAlchemyUnitOfWork:
    """One database session and repositories for a single request boundary."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._session_context: Any = None
        self.users: UserRepository
        self.bots: BotRepository
        self.games: GameRepository
        self.stats: StatsRepository

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self._session_context = self._session_factory()
        session = await self._session_context.__aenter__()
        self._session = session
        self.users = SqlAlchemyUserRepository(self._session)
        self.bots = SqlAlchemyBotRepository(self._session)
        self.games = SqlAlchemyGameRepository(self._session)
        self.stats = SqlAlchemyStatsRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._session is None:
            return
        try:
            if exc_type is not None:
                await self.rollback()
        finally:
            if self._session_context is not None:
                await self._session_context.__aexit__(exc_type, exc_val, exc_tb)
            self._session = None
            self._session_context = None

    async def commit(self) -> None:
        if self._session is None:
            msg = "unit of work is not active"
            raise RuntimeError(msg)
        await self._session.commit()

    async def rollback(self) -> None:
        if self._session is None:
            return
        await self._session.rollback()
