from aiogram import Router
from aiogram.filters import Command

from .loser_draw import start_loser_draw
from .winner_draw import start_winner_draw


def create_router() -> Router:
    router = Router()
    router.message.register(start_winner_draw, Command("run"))
    router.message.register(start_loser_draw, Command("loser"))
    return router


router = create_router()
