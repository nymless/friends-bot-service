import asyncio

from aiogram import Bot, types
from aiogram.utils.chat_action import ChatActionSender

from friends_bot_service.draw import domain, usecases
from friends_bot_service.infra.bootstrap import db
from friends_bot_service.infra.observability import (
    record_draw_completed,
    record_draw_rejected,
)
from friends_bot_service.infra.repositories.unit_of_work import SqlAlchemyUnitOfWork
from friends_bot_service.infra.texts import draw_entrant_text as text
from friends_bot_service.infra.texts import system_text

_claim_draw = usecases.ClaimDraw()
_touch_bot_draw_attempt = usecases.TouchBotDrawAttempt()


async def _run_draw(
    message: types.Message,
    bot: Bot,
    draw_type: domain.DrawType,
) -> None:
    from_user = message.from_user
    if from_user is None:
        return

    async def touch_bot(uow: SqlAlchemyUnitOfWork) -> None:
        await _touch_bot_draw_attempt.execute(bot.id, uow.bots)
        await uow.commit()

    try:
        await db.run_with_unit_of_work(touch_bot)
    except db.DatabaseUnavailableError:
        await message.answer(system_text.DB_UNAVAILABLE_MESSAGE)
        return

    async def claim_draw(uow: SqlAlchemyUnitOfWork) -> usecases.ClaimDrawResult:
        command = usecases.ClaimDrawData(
            bot_id=bot.id,
            chat_id=message.chat.id,
            user_id=from_user.id,
            draw_type=draw_type,
        )
        try:
            result = await _claim_draw.execute(command, uow.draw_entrant, uow.draw)
        except usecases.DrawAlreadyClaimedError:
            await uow.rollback()
            return usecases.ClaimDrawResult(
                outcome=usecases.ClaimDrawOutcome.ALREADY_PLAYED,
            )

        if result.outcome is usecases.ClaimDrawOutcome.READY:
            await uow.commit()
        else:
            await uow.rollback()

        return result

    try:
        result = await db.run_with_unit_of_work(claim_draw)
    except db.DatabaseUnavailableError:
        await message.answer(system_text.DB_UNAVAILABLE_MESSAGE)
        return

    outcome = usecases.ClaimDrawOutcome

    if result.outcome is outcome.NOT_REGISTERED:
        record_draw_rejected(draw_type, "not_registered")
        await message.answer(text.DRAW_ENTRANT_NOT_IN_LIST)
        return

    if result.outcome is outcome.ALREADY_PLAYED:
        record_draw_rejected(draw_type, "already_played")
        await message.answer(text.DRAW_ALREADY_PLAYED)
        return

    if result.outcome is outcome.NO_DRAW_ENTRANTS:
        record_draw_rejected(draw_type, "no_entrants")
        await message.answer(text.DRAW_NO_DRAW_ENTRANTS)
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

    record_draw_completed(draw_type)
