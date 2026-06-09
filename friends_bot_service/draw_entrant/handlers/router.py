from aiogram import Router
from aiogram.filters import Command

from .list import list_draw_entrants
from .register import register
from .unregister import unregister


def create_router() -> Router:
    router = Router()
    router.message.register(list_draw_entrants, Command("list"))
    router.message.register(register, Command("reg"))
    router.message.register(unregister, Command("delete"))
    return router


router = create_router()
