from aiogram import F, Router
from aiogram.filters import Command

from .add_bot import add_bot
from .common import (
    SET_DEFAULT_COMMANDS_ALL_CALLBACK,
    SET_DEFAULT_COMMANDS_BOT_PREFIX,
)
from .remove_bot import remove_bot
from .set_default_commands import set_default_commands
from .set_default_commands_all import set_default_commands_for_all_bots
from .set_default_commands_selected import set_default_commands_for_selected_bot


def create_router() -> Router:
    router = Router()
    router.message.register(add_bot, Command("add_bot"))
    router.message.register(remove_bot, Command("remove_bot"))
    router.message.register(set_default_commands, Command("set_default_commands"))
    router.callback_query.register(
        set_default_commands_for_selected_bot,
        F.data.startswith(SET_DEFAULT_COMMANDS_BOT_PREFIX),
    )
    router.callback_query.register(
        set_default_commands_for_all_bots,
        F.data == SET_DEFAULT_COMMANDS_ALL_CALLBACK,
    )
    return router


router = create_router()
