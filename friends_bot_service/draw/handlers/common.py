import asyncio

from aiogram import Bot, types
from aiogram.utils.chat_action import ChatActionSender

from friends_bot_service.draw import domain, usecases
from friends_bot_service.infra.bootstrap import db
from friends_bot_service.infra.core.lock import get_bot_chat_lock
from friends_bot_service.infra.observability import (
    record_draw_completed,
    record_draw_rejected,
)
from friends_bot_service.infra.repositories.unit_of_work import SqlAlchemyUnitOfWork
from friends_bot_service.infra.texts import draw_entrant_text as text
from friends_bot_service.infra.texts import system_text

_prepare_draw = usecases.PrepareDraw()
_record_draw = usecases.RecordDraw()
_touch_bot_game_attempt = usecases.TouchBotGameAttempt()


async def _run_draw(
    message: types.Message,
    bot: Bot,
    game_type: domain.GameType,
) -> None:
    from_user = message.from_user
    if from_user is None:
        return

    lock = get_bot_chat_lock((bot.id, message.chat.id))
    async with lock:
        await _run_draw_locked(message, bot, game_type, from_user)


async def _run_draw_locked(
    message: types.Message,
    bot: Bot,
    game_type: domain.GameType,
    from_user: types.User,
) -> None:
    async def prepare_draw(uow: SqlAlchemyUnitOfWork) -> usecases.PrepareDrawResult:
        await _touch_bot_game_attempt.execute(bot.id, uow.bots)
        await uow.commit()

        command = usecases.PrepareDrawData(
            bot_id=bot.id,
            chat_id=message.chat.id,
            user_id=from_user.id,
            game_type=game_type,
        )
        return await _prepare_draw.execute(command, uow.draw_entrant, uow.draw)

    try:
        result = await db.run_with_unit_of_work(prepare_draw)
    except db.DatabaseUnavailableError:
        await message.answer(system_text.DB_UNAVAILABLE_MESSAGE)
        return

    outcome = usecases.PrepareDrawOutcome

    if result.outcome is outcome.NOT_REGISTERED:
        record_draw_rejected(game_type, "not_registered")
        await message.answer(text.DRAW_ENTRANT_NOT_IN_LIST)
        return

    if result.outcome is outcome.ALREADY_PLAYED:
        record_draw_rejected(game_type, "already_played")
        await message.answer(text.DRAW_ALREADY_PLAYED)
        return

    if result.outcome is outcome.NO_PLAYERS:
        record_draw_rejected(game_type, "no_entrants")
        await message.answer(text.DRAW_NO_PLAYERS)
        return

    if result.outcome is not outcome.READY:
        return

    async with ChatActionSender.typing(
        chat_id=message.chat.id,
        bot=bot,
        message_thread_id=message.message_thread_id,
    ):
        for step in result.suspense_messages:
            await message.answer(step)
            await asyncio.sleep(1.5)

        await asyncio.sleep(1.5)
        if result.final_message is not None:
            await message.answer(result.final_message)

    async def record_draw(uow: SqlAlchemyUnitOfWork) -> None:
        assert result.winner_user_id is not None
        assert result.today_utc is not None
        await _record_draw.execute(
            usecases.RecordDrawData(
                bot_id=bot.id,
                chat_id=message.chat.id,
                winner_user_id=result.winner_user_id,
                game_type=game_type,
                today_utc=result.today_utc,
            ),
            uow.draw,
        )
        await uow.commit()

    try:
        await db.run_with_unit_of_work(record_draw)
    except db.DatabaseUnavailableError:
        await message.answer(system_text.DB_UNAVAILABLE_MESSAGE)
        return

    record_draw_completed(game_type)
