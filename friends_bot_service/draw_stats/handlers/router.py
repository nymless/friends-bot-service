from aiogram import Router
from aiogram.filters import Command

from .loser_stats import show_loser_statistics
from .winner_stats import show_winner_statistics

router = Router()

router.message.register(show_winner_statistics, Command("stats"))
router.message.register(show_loser_statistics, Command("loserstats"))
