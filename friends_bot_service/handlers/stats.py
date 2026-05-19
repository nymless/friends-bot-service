import logging

from aiogram import Bot, Router, types
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.enums.enums import GameType
from friends_bot_service.repositories import stats_repo
from friends_bot_service.texts.stats_text import STATS_MESSAGES

logger = logging.getLogger(__name__)


async def show_statistics(
    message: types.Message,
    session: AsyncSession,
    bot_id: int,
    chat_id: int,
    game_type: GameType,
):
    """Shows the statistics for a given bot_id, chat_id and game_type."""

    stats = await stats_repo.get_top_stats(session, bot_id, chat_id, game_type)

    if not stats:
        await message.answer("Статистика пока пуста. Сначала сыграйте в игру!")
        return

    title = STATS_MESSAGES[game_type]

    # Build the response in the format: 1) Name — N times
    lines = []
    for i, (name, count) in enumerate(stats, 1):
        lines.append(f"{i}) {name} — {count} раз(а)")

    response = title + "\n".join(lines)
    await message.answer(response)


async def show_winner_statistics(
    message: types.Message,
    bot: Bot,
    session: AsyncSession,
    update_id: str | None = None,
):
    """Shows the winner statistics."""

    if message.from_user is None:
        logger.warning(
            f"Handler [upd={update_id}] [command=stats] [details=user_not_found]"
        )
        return

    bot_id = bot.id
    chat_id = message.chat.id

    logger.info(
        f"Handler [upd={update_id}] [command=stats] [details=winner_stats_requested]"
    )
    await show_statistics(message, session, bot_id, chat_id, GameType.WINNER)


async def show_loser_statistics(
    message: types.Message,
    bot: Bot,
    session: AsyncSession,
    update_id: str | None = None,
):
    """Shows the loser statistics."""

    if message.from_user is None:
        logger.warning(
            f"Handler [upd={update_id}] [command=loserstats] [details=user_not_found]"
        )
        return

    bot_id = bot.id
    chat_id = message.chat.id

    logger.info(
        f"Handler [upd={update_id}]  "
        "[command=loserstats] [details=loser_stats_requested]"
    )
    await show_statistics(message, session, bot_id, chat_id, GameType.LOSER)


def get_router() -> Router:
    """Creates a router with statistics handlers."""

    router = Router()
    router.message.register(show_winner_statistics, Command("stats"))
    router.message.register(show_loser_statistics, Command("loserstats"))
    return router
