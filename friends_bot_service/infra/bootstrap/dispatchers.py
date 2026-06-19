from aiogram import Dispatcher, F
from aiogram.enums.chat_type import ChatType
from aiogram.fsm.storage.memory import MemoryStorage

from friends_bot_service.draw.handlers.router import create_router as create_draw_router
from friends_bot_service.draw_entrant.handlers.router import (
    create_router as create_draw_entrant_router,
)
from friends_bot_service.draw_stats.handlers.router import (
    create_router as create_draw_stats_router,
)
from friends_bot_service.infra.handlers import error
from friends_bot_service.infra.middlewares.inbound_command_log import (
    register_inbound_command_log_middleware,
)
from friends_bot_service.infra.middlewares.update_id import UpdateIdMiddleware
from friends_bot_service.infra.observability import register_handler_metrics_middleware
from friends_bot_service.master_bot.handlers.router import (
    create_router as create_master_bot_router,
)


def get_bot_dispatcher() -> Dispatcher:
    """Creates the dispatcher used by game bots."""

    dp = Dispatcher(storage=MemoryStorage())
    dp.message.filter(
        F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.from_user
    )
    dp.update.middleware(UpdateIdMiddleware())
    register_handler_metrics_middleware(dp, "draw")
    register_inbound_command_log_middleware(dp)
    dp.include_routers(
        create_draw_entrant_router(),
        create_draw_stats_router(),
        create_draw_router(),
        error.create_router(),
    )
    return dp


def get_master_bot_dispatcher() -> Dispatcher:
    """Creates the dispatcher used for the master bot."""

    master_dp = Dispatcher()
    master_dp.message.filter(F.chat.type == ChatType.PRIVATE, F.from_user)
    master_dp.update.middleware(UpdateIdMiddleware())
    register_handler_metrics_middleware(master_dp, "master")
    register_inbound_command_log_middleware(master_dp)
    master_dp.include_routers(
        create_master_bot_router(),
        error.create_router(),
    )
    return master_dp
