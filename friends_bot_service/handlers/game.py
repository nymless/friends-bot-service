import asyncio
import logging
import random
from datetime import datetime, timezone

from aiogram import Bot, Router, types
from aiogram.filters.command import Command
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.core.lock import get_bot_chat_lock
from friends_bot_service.enums.enums import GameType
from friends_bot_service.repositories import bot_repo, game_repo, user_repo
from friends_bot_service.texts.game_text import WINNER_MESSAGES

logger = logging.getLogger(__name__)


async def start_game(
    message: types.Message,
    bot: Bot,
    session: AsyncSession,
    bot_id: int,
    chat_id: int,
    game_type: GameType,
):
    """Starts a game for a given bot_id, chat_id and game_type."""

    lock = get_bot_chat_lock((bot_id, chat_id))

    async with lock:
        today_utc = datetime.now(timezone.utc).date()

        stats = await game_repo.get_game_stats(
            session, bot_id, chat_id, game_type, today_utc
        )
        if stats:
            await message.answer("Сегодня выбор уже сделан!")
            return

        players = await game_repo.get_players(session, bot_id, chat_id, today_utc)
        if not players:
            await message.answer("Никто не зарегистрировался!")
            return

        # Pick the winner
        winner = random.choice(players)

        # Prepare the output messages
        steps = WINNER_MESSAGES[game_type][:-1]
        final_step = WINNER_MESSAGES[game_type][-1] + winner.full_name

        async with ChatActionSender.typing(
            chat_id=chat_id,
            bot=bot,
            message_thread_id=message.message_thread_id,
        ):
            # Send the suspense messages before the result
            for step in steps:
                await message.answer(step)
                await asyncio.sleep(1.5)

            # Send the final result message
            await asyncio.sleep(1.5)
            await message.answer(final_step)

        await game_repo.update_game_stats(
            session, bot_id, chat_id, winner.user_id, game_type, today_utc
        )

        await session.commit()


async def start_winner_game(
    message: types.Message,
    bot: Bot,
    session: AsyncSession,
    update_id: str | None = None,
):
    """Starts a winner game."""

    if message.from_user is None:
        logger.warning(
            f"Handler [upd={update_id}] [command=run] [details=user_not_found]"
        )
        return

    bot_id = bot.id
    chat_id = message.chat.id
    user_id = message.from_user.id

    db_user = await user_repo.get_db_user(session, bot_id, chat_id, user_id)

    if db_user is None:
        await message.answer("Тебя нет в списках игроков.")
        return

    logger.info(f"Handler [upd={update_id}] [command=run] [details=start_winner_game]")

    await bot_repo.touch_bot_last_game_attempt(session, bot_id)
    await session.commit()

    await start_game(message, bot, session, bot_id, chat_id, GameType.WINNER)


async def start_loser_game(
    message: types.Message,
    bot: Bot,
    session: AsyncSession,
    update_id: str | None = None,
):
    """Starts a loser game."""

    if message.from_user is None:
        logger.warning(
            f"Handler [upd={update_id}] [command=loser] [details=user_not_found]"
        )
        return

    bot_id = bot.id
    chat_id = message.chat.id
    user_id = message.from_user.id

    db_user = await user_repo.get_db_user(session, bot_id, chat_id, user_id)

    if db_user is None:
        await message.answer("Тебя нет в списках игроков.")
        return

    logger.info(f"Handler [upd={update_id}] [command=loser] [details=start_loser_game]")

    await bot_repo.touch_bot_last_game_attempt(session, bot_id)
    await session.commit()

    await start_game(message, bot, session, bot_id, chat_id, GameType.LOSER)


def get_router() -> Router:
    """Creates a router with game handlers."""

    router = Router()
    router.message.register(start_winner_game, Command("run"))
    router.message.register(start_loser_game, Command("loser"))
    return router
