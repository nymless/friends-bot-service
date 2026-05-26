from aiogram import Dispatcher, F
from aiogram.enums.chat_type import ChatType
from aiogram.fsm.storage.memory import MemoryStorage

from friends_bot_service.draw.handlers import router as draw_router
from friends_bot_service.draw_entrant.handlers import router as draw_entrant_router
from friends_bot_service.draw_stats.handlers import router as draw_stats_router
from friends_bot_service.infra.handlers import error
from friends_bot_service.infra.middlewares.inbound_command_log import (
    register_inbound_command_log_middleware,
)
from friends_bot_service.infra.middlewares.update_id import UpdateIdMiddleware
from friends_bot_service.master_bot.handlers import router as master_bot_router


def get_bot_dispatcher() -> Dispatcher:
    """Creates the dispatcher used by game bots."""

    dp = Dispatcher(storage=MemoryStorage())
    dp.message.filter(
        F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.from_user
    )
    dp.update.middleware(UpdateIdMiddleware())
    register_inbound_command_log_middleware(dp)
    dp.include_routers(
        draw_entrant_router,
        draw_stats_router,
        draw_router,
        error.router,
    )
    return dp


def get_master_bot_dispatcher() -> Dispatcher:
    """Creates the dispatcher used for the master bot."""

    master_dp = Dispatcher()
    master_dp.message.filter(F.chat.type == ChatType.PRIVATE, F.from_user)
    master_dp.update.middleware(UpdateIdMiddleware())
    register_inbound_command_log_middleware(master_dp)
    master_dp.include_routers(
        master_bot_router,
        error.router,
    )
    return master_dp
