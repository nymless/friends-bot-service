import asyncio
import logging

from aiogram import Bot, Router, types
from aiogram.filters.command import Command
from aiogram.utils.chat_action import ChatActionSender

from friends_bot_service.bootstrap.db import (
    DatabaseUnavailableError,
    run_with_unit_of_work,
)
from friends_bot_service.domain import GameType
from friends_bot_service.texts.player_text import (
    DRAW_ALREADY_PLAYED,
    DRAW_NO_PLAYERS,
    PLAYER_NOT_IN_LIST,
)
from friends_bot_service.texts.system import DB_UNAVAILABLE_MESSAGE
from friends_bot_service.usecases.game import (
    PrepareDraw,
    PrepareDrawCommand,
    PrepareDrawOutcome,
    PrepareDrawResult,
    RecordDraw,
    RecordDrawCommand,
)
from friends_bot_service.usecases.game.run_draw import TouchBotGameAttempt

logger = logging.getLogger(__name__)

_prepare_draw = PrepareDraw()
_record_draw = RecordDraw()
_touch_bot_game_attempt = TouchBotGameAttempt()


async def _run_draw(
    message: types.Message,
    bot: Bot,
    game_type: GameType,
    *,
    command_name: str,
    update_id: str | None,
) -> None:
    from_user = message.from_user
    if from_user is None:
        logger.warning(
            f"Handler [upd={update_id}] [command={command_name}] "
            "[details=user_not_found]"
        )
        return

    async def _prepare(uow) -> PrepareDrawResult:
        await _touch_bot_game_attempt.execute(bot.id, uow.bots)
        await uow.commit()

        command = PrepareDrawCommand(
            bot_id=bot.id,
            chat_id=message.chat.id,
            user_id=from_user.id,
            game_type=game_type,
        )
        return await _prepare_draw.execute(command, uow.users, uow.games)

    try:
        draw = await run_with_unit_of_work(_prepare)
    except DatabaseUnavailableError:
        await message.answer(DB_UNAVAILABLE_MESSAGE)
        return

    logger.info(
        f"Handler [upd={update_id}] [command={command_name}] "
        f"[details=start_{game_type}_game]"
    )

    if draw.outcome == PrepareDrawOutcome.NOT_REGISTERED:
        await message.answer(PLAYER_NOT_IN_LIST)
        return

    if draw.outcome == PrepareDrawOutcome.ALREADY_PLAYED:
        await message.answer(DRAW_ALREADY_PLAYED)
        return

    if draw.outcome == PrepareDrawOutcome.NO_PLAYERS:
        await message.answer(DRAW_NO_PLAYERS)
        return

    if draw.outcome != PrepareDrawOutcome.READY:
        return

    async with ChatActionSender.typing(
        chat_id=message.chat.id,
        bot=bot,
        message_thread_id=message.message_thread_id,
    ):
        for step in draw.suspense_messages:
            await message.answer(step)
            await asyncio.sleep(1.5)

        await asyncio.sleep(1.5)
        if draw.final_message is not None:
            await message.answer(draw.final_message)

    async def _persist(uow) -> None:
        assert draw.winner_user_id is not None
        assert draw.today_utc is not None
        await _record_draw.execute(
            RecordDrawCommand(
                bot_id=bot.id,
                chat_id=message.chat.id,
                winner_user_id=draw.winner_user_id,
                game_type=game_type,
                today_utc=draw.today_utc,
            ),
            uow.games,
        )
        await uow.commit()

    try:
        await run_with_unit_of_work(_persist)
    except DatabaseUnavailableError:
        await message.answer(DB_UNAVAILABLE_MESSAGE)


async def start_winner_game(
    message: types.Message,
    bot: Bot,
    update_id: str | None = None,
):
    """Starts a winner game."""

    await _run_draw(
        message,
        bot,
        GameType.WINNER,
        command_name="run",
        update_id=update_id,
    )


async def start_loser_game(
    message: types.Message,
    bot: Bot,
    update_id: str | None = None,
):
    """Starts a loser game."""

    await _run_draw(
        message,
        bot,
        GameType.LOSER,
        command_name="loser",
        update_id=update_id,
    )


def get_router() -> Router:
    """Creates a router with game handlers."""

    router = Router()
    router.message.register(start_winner_game, Command("run"))
    router.message.register(start_loser_game, Command("loser"))
    return router
