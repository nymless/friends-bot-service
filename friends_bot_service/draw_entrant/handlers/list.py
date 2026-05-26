import logging

from aiogram import Bot, types

from friends_bot_service.draw_entrant import usecases
from friends_bot_service.infra.bootstrap import db
from friends_bot_service.infra.repositories.unit_of_work import SqlAlchemyUnitOfWork
from friends_bot_service.infra.texts import draw_entrant_text, system_text

_logger = logging.getLogger(__name__)
_list_draw_entrants = usecases.ListDrawEntrants()


async def list_draw_entrants(
    message: types.Message,
    bot: Bot,
    update_id: str | None = None,
):
    """Lists active registered players for this bot and chat."""

    user = message.from_user

    if user is None:
        _logger.warning(
            "Update id=%s: list draw entrants declined; Cause: user not found.",
            update_id,
        )
        return

    async def run(uow: SqlAlchemyUnitOfWork):
        command = usecases.ListDrawEntrantsData(
            bot_id=bot.id,
            chat_id=message.chat.id,
        )
        result = await _list_draw_entrants.execute(command, uow.draw_entrant)

        if result.outcome is usecases.ListDrawEntrantsOutcome.NO_ENTRANTS:
            await message.answer(draw_entrant_text.DRAW_ENTRANT_LIST_EMPTY)
            return

        lines = []
        for i, player in enumerate(result.draw_entrants, 1):
            if player.username:
                lines.append(f"{i}) {player.full_name} @{player.username}")
            else:
                lines.append(f"{i}) {player.full_name}")

        await message.answer(
            draw_entrant_text.DRAW_ENTRANT_LIST_HEADER + "\n".join(lines)
        )

    try:
        await db.run_with_unit_of_work(run)
    except db.DatabaseUnavailableError:
        await message.answer(system_text.DB_UNAVAILABLE_MESSAGE)
