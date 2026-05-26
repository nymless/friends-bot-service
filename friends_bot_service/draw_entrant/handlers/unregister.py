import logging

from aiogram import Bot, types

from friends_bot_service.draw_entrant import usecases
from friends_bot_service.infra.bootstrap import db
from friends_bot_service.infra.repositories.unit_of_work import SqlAlchemyUnitOfWork
from friends_bot_service.infra.texts import draw_entrant_text as text
from friends_bot_service.infra.texts import system_text

_logger = logging.getLogger(__name__)
_unregister = usecases.UnregisterDrawEntrant()


async def unregister(
    message: types.Message,
    bot: Bot,
    update_id: str | None = None,
):
    """Cancels a draw entrant registration by soft unregistration."""

    user = message.from_user

    if user is None:
        _logger.warning(
            (
                "Update id=%s: draw entrant unregistration declined; "
                "Cause: user not found."
            ),
            update_id,
        )
        return

    async def run(uow: SqlAlchemyUnitOfWork):
        data = usecases.UnregisterDrawEntrantData(
            bot_id=bot.id,
            chat_id=message.chat.id,
            user_id=user.id,
        )
        result = await _unregister.execute(data, uow.draw_entrant)

        outcome = usecases.UnregisterDrawEntrantOutcome
        if (
            result.outcome is outcome.NOT_FOUND
            or result.outcome is outcome.ALREADY_INACTIVE
        ):
            await message.answer(text.DRAW_ENTRANT_ALREADY_NOT_IN_LIST)
            return

        await uow.commit()
        _logger.info("Update id=%s: draw entrant unregistration succeed.", update_id)
        await message.answer(text.DRAW_ENTRANT_UNREGISTERED)

    try:
        await db.run_with_unit_of_work(run)
    except db.DatabaseUnavailableError:
        await message.answer(system_text.DB_UNAVAILABLE_MESSAGE)
