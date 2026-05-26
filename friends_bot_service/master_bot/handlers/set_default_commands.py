import logging

from aiogram import types

from friends_bot_service.bot_admin import usecases as admin_usecases
from friends_bot_service.infra.bootstrap import db
from friends_bot_service.infra.repositories.unit_of_work import SqlAlchemyUnitOfWork
from friends_bot_service.infra.texts import master_text, system_text
from friends_bot_service.master_bot import usecases

from .common import _cipher, build_set_default_commands_keyboard, get_bot_name

_logger = logging.getLogger(__name__)
_list_owner_bots = admin_usecases.ListOwnerBots()
_sync_commands = usecases.SyncBotCommands(_cipher)


async def set_default_commands(
    message: types.Message,
    update_id: str | None = None,
):
    """Starts the default command sync flow."""

    user = message.from_user

    if user is None:
        _logger.warning(
            "Update id=%s: default command sync declined; Cause: user not found",
            update_id,
        )
        return

    async def load_owner_bots(uow: SqlAlchemyUnitOfWork):
        result = await _list_owner_bots.execute(
            admin_usecases.ListOwnerBotsData(owner_id=user.id),
            uow.bots,
        )
        return list(result.bots)

    try:
        db_bots = await db.run_with_unit_of_work(load_owner_bots)
    except db.DatabaseUnavailableError:
        await message.answer(system_text.DB_UNAVAILABLE_MESSAGE)
        return

    if not db_bots:
        await message.answer(master_text.NO_BOTS_FOR_COMMAND_SYNC)
        return

    if len(db_bots) == 1:
        registered_bot = db_bots[0]
        try:
            success = await _sync_commands.sync_registered_bot(registered_bot)
        except Exception:
            _logger.exception(
                "Update id=%s: single command sync failed; Bot id=%s",
                update_id,
                registered_bot.bot_id,
            )
            await message.answer(master_text.COMMANDS_UPDATE_FAILED)
            return

        if success:
            await message.answer(
                master_text.commands_updated_for_bot(get_bot_name(registered_bot))
            )
            return

        await message.answer(master_text.COMMANDS_UPDATE_FAILED)
        return

    await message.answer(
        master_text.CHOOSE_BOT_FOR_COMMAND_SYNC,
        reply_markup=build_set_default_commands_keyboard(db_bots),
    )
