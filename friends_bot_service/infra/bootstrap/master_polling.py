from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any

from aiogram import Bot, Dispatcher

from friends_bot_service.bot_admin.interfaces import BotRuntimePort


@dataclass(frozen=True, slots=True)
class MasterBotPollingContext:
    """Workflow dependencies injected into master-bot handlers during polling."""

    manager: BotRuntimePort


def start_master_bot_polling(
    master_dp: Dispatcher,
    master_bot: Bot,
    context: MasterBotPollingContext,
) -> Coroutine[Any, Any, None]:
    """Starts master-bot polling with typed workflow dependencies."""

    return master_dp.start_polling(master_bot, manager=context.manager)
