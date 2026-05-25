import logging

from aiogram import Bot, Router, types
from aiogram.filters import Command

from friends_bot_service.bootstrap.db import (
    DatabaseUnavailableError,
    run_with_unit_of_work,
)
from friends_bot_service.domain import GameType
from friends_bot_service.texts.system import DB_UNAVAILABLE_MESSAGE
from friends_bot_service.usecases.stats import (
    ShowStats,
    ShowStatsCommand,
    ShowStatsOutcome,
)

logger = logging.getLogger(__name__)

_show_stats = ShowStats()


async def show_winner_statistics(
    message: types.Message,
    bot: Bot,
    update_id: str | None = None,
):
    """Shows the winner statistics."""

    async def _run(uow):
        command = ShowStatsCommand(
            bot_id=bot.id,
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else None,
            game_type=GameType.WINNER,
        )
        result = await _show_stats.execute(command, uow.stats)

        if result.outcome == ShowStatsOutcome.USER_MISSING:
            logger.warning(
                f"Handler [upd={update_id}] [command=stats] [details=user_not_found]"
            )
            return

        logger.info(
            f"Handler [upd={update_id}] [command=stats] "
            "[details=winner_stats_requested]"
        )
        await _answer_stats(message, result)

    try:
        await run_with_unit_of_work(_run)
    except DatabaseUnavailableError:
        await message.answer(DB_UNAVAILABLE_MESSAGE)


async def show_loser_statistics(
    message: types.Message,
    bot: Bot,
    update_id: str | None = None,
):
    """Shows the loser statistics."""

    async def _run(uow):
        command = ShowStatsCommand(
            bot_id=bot.id,
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else None,
            game_type=GameType.LOSER,
        )
        result = await _show_stats.execute(command, uow.stats)

        if result.outcome == ShowStatsOutcome.USER_MISSING:
            logger.warning(
                f"Handler [upd={update_id}] [command=loserstats] "
                "[details=user_not_found]"
            )
            return

        logger.info(
            f"Handler [upd={update_id}]  "
            "[command=loserstats] [details=loser_stats_requested]"
        )
        await _answer_stats(message, result)

    try:
        await run_with_unit_of_work(_run)
    except DatabaseUnavailableError:
        await message.answer(DB_UNAVAILABLE_MESSAGE)


async def _answer_stats(message: types.Message, result) -> None:
    if result.outcome == ShowStatsOutcome.EMPTY:
        await message.answer(result.message or "")
        return

    lines = [
        f"{i}) {row.full_name} — {row.count} раз(а)"
        for i, row in enumerate(result.lines, 1)
    ]
    await message.answer((result.message or "") + "\n".join(lines))


def get_router() -> Router:
    """Creates a router with statistics handlers."""

    router = Router()
    router.message.register(show_winner_statistics, Command("stats"))
    router.message.register(show_loser_statistics, Command("loserstats"))
    return router
