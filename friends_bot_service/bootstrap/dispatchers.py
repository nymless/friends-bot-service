from aiogram import Dispatcher, F
from aiogram.enums.chat_type import ChatType
from aiogram.fsm.storage.memory import MemoryStorage

from friends_bot_service.core.database import session_factory
from friends_bot_service.handlers import error, game, master, stats, user
from friends_bot_service.middlewares.db_session import DbSessionMiddleware
from friends_bot_service.middlewares.logging import LoggingMiddleware


def get_bot_dispatcher() -> Dispatcher:
    """Creates the dispatcher used by game bots."""

    dp = Dispatcher(storage=MemoryStorage())
    dp.message.filter(
        F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.from_user
    )
    dp.update.middleware(LoggingMiddleware())
    dp.update.middleware(DbSessionMiddleware(session_factory))
    dp.include_routers(
        user.get_router(),
        stats.get_router(),
        game.get_router(),
        error.get_error_router(),
    )
    return dp


def get_master_bot_dispatcher() -> Dispatcher:
    """Creates the dispatcher used by the master bot."""

    master_dp = Dispatcher()
    master_dp.message.filter(F.chat.type == ChatType.PRIVATE, F.from_user)
    master_dp.update.middleware(LoggingMiddleware())
    master_dp.update.middleware(DbSessionMiddleware(session_factory))
    master_dp.include_routers(master.router, error.get_error_router())
    return master_dp
