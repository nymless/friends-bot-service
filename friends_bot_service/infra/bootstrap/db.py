"""
Database entry point for the application (composition root).

This module binds the global SQLAlchemy session factory to SqlAlchemyUnitOfWork.
It does not contain business rules — only how a DB session is opened and closed.

Two ways to use it:

1. Handlers (Telegram commands) — `run_with_unit_of_work(callback)`:
   - opens one UoW per handler call;
   - passes uow into callback (use cases receive uow.bots, uow.draw,
     uow.draw_entrant, uow.draw_stats, …);
   - on connection/SQLAlchemy errors logs and raises DatabaseUnavailableError;
   - the handler catches that and sends the user message from texts/system_text.py.

2. Startup and scripts — `async with unit_of_work() as uow`:
   - same UoW type, but no Telegram context (runtime.load_registered_bots,
     deactivate_inactive_bots, etc.);
   - caller commits/rollbacks explicitly inside the block.

SqlAlchemyUnitOfWork itself lives in repositories/unit_of_work.py.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy.exc import InterfaceError, SQLAlchemyError

from friends_bot_service.infra.core.database import session_factory
from friends_bot_service.infra.observability.db_metrics import record_db_unavailable
from friends_bot_service.infra.repositories.unit_of_work import SqlAlchemyUnitOfWork

_T = TypeVar("_T")

_logger = logging.getLogger(__name__)


class DatabaseUnavailableError(Exception):
    """Database is unreachable; handlers should answer the user."""


def unit_of_work() -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(session_factory)


async def run_with_unit_of_work(
    callback: Callable[[SqlAlchemyUnitOfWork], Awaitable[_T]],
) -> _T:
    """Opens one unit of work per call; raises DatabaseUnavailableError on failure."""

    try:
        async with unit_of_work() as uow:
            return await callback(uow)

    except (InterfaceError, ConnectionError, SQLAlchemyError) as exc:
        _logger.exception("DATABASE_OFFLINE")
        record_db_unavailable()

        raise DatabaseUnavailableError from exc
