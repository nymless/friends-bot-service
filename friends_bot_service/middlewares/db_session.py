import logging

from aiogram import BaseMiddleware, types
from sqlalchemy.exc import InterfaceError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


class DbSessionMiddleware(BaseMiddleware):
    """Middleware for database session distribution to handlers.

    - Injects the session into the handler context.
    - Releases the session after the handler is executed.
    """

    def __init__(self, session_pool: async_sessionmaker[AsyncSession]):
        self.session_pool = session_pool

    async def __call__(self, handler, event, data):
        try:
            async with self.session_pool() as session:
                data["session"] = session
                return await handler(event, data)
        except (InterfaceError, ConnectionError, SQLAlchemyError):
            logger.exception("DATABASE_OFFLINE")

            if isinstance(event, types.Message):
                await event.answer("⚠️ Сервис временно недоступен. Попробуйте позже.")

            return
