"""
Handler DB boundary: use run_with_unit_of_work (opens unit_of_work + user-facing DB errors).

Bootstrap/scripts without a chat message: async with unit_of_work() as uow.
"""

from collections.abc import Awaitable, Callable
from typing import TypeVar

from aiogram import types
from sqlalchemy.exc import InterfaceError, SQLAlchemyError

from friends_bot_service.core.config import settings
from friends_bot_service.core.database import session_factory
from friends_bot_service.repositories.unit_of_work import (
    SqlAlchemyUnitOfWork,
    unit_of_work_factory,
)

unit_of_work = unit_of_work_factory(session_factory)

_T = TypeVar("_T")


async def run_with_unit_of_work(
    callback: Callable[[SqlAlchemyUnitOfWork], Awaitable[_T]],
    *,
    message: types.Message | None = None,
    on_db_unavailable: Callable[[], Awaitable[None]] | None = None,
) -> _T | None:
    """
    Opens one unit of work per call and maps database errors to a user message
    or a custom callback (for example callback.answer on master flows).
    """

    try:
        async with unit_of_work() as uow:
            result = await callback(uow)
            return result
    except (InterfaceError, ConnectionError, SQLAlchemyError):
        import logging

        logging.getLogger(__name__).exception("DATABASE_OFFLINE")
        if message is not None:
            await message.answer("⚠️ Сервис временно недоступен. Попробуйте позже.")
        elif on_db_unavailable is not None:
            await on_db_unavailable()
        return None


def registration_enabled() -> bool:
    return settings.REGISTRATION_ENABLED
