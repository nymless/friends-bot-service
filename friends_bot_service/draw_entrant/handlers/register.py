import logging

from aiogram import Bot, types

from friends_bot_service.draw_entrant import usecases
from friends_bot_service.infra.bootstrap import db
from friends_bot_service.infra.core.config import settings
from friends_bot_service.infra.repositories.unit_of_work import SqlAlchemyUnitOfWork
from friends_bot_service.infra.texts import draw_entrant_text as text
from friends_bot_service.infra.texts import system_text

_logger = logging.getLogger(__name__)
_register_draw_entrant = usecases.RegisterDrawEntrant()


async def register(
    message: types.Message,
    bot: Bot,
    update_id: str | None = None,
):
    """Registers or reactivates a user as a draw entrant."""

    user = message.from_user

    if user is None:
        _logger.warning(
            "Update id=%s: draw entrant registration declined; Cause: user not found.",
            update_id,
        )
        return

    if not settings.REGISTRATION_ENABLED:
        _logger.info(
            (
                "Update id=%s: draw entrant registration declined; "
                "Cause: global registration shutdown."
            ),
            update_id,
        )
        await message.answer(text.DRAW_ENTRANT_REGISTRATION_DISABLED)
        return

    async def run(uow: SqlAlchemyUnitOfWork):

        data = usecases.RegisterDrawEntrantData(
            bot_id=bot.id,
            chat_id=message.chat.id,
            user_id=user.id,
            username=user.username,
            full_name=user.full_name,
        )

        await _register_draw_entrant.execute(data, uow.draw_entrant)

        await uow.commit()
        _logger.info("Update id=%s: draw entrant registration succeed.", update_id)
        await message.answer(text.DRAW_ENTRANT_REGISTERED)

    try:
        await db.run_with_unit_of_work(run)
    except db.DatabaseUnavailableError:
        await message.answer(system_text.DB_UNAVAILABLE_MESSAGE)
