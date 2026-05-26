import logging

from aiogram import types

from friends_bot_service.bot_admin import usecases as admin_usecases
from friends_bot_service.infra.bootstrap import db
from friends_bot_service.infra.repositories.unit_of_work import SqlAlchemyUnitOfWork
from friends_bot_service.infra.texts import master_text, system_text
from friends_bot_service.master_bot import usecases

from .common import _cipher, edit_callback_message, get_bot_name

_logger = logging.getLogger(__name__)
_list_owner_bots = admin_usecases.ListOwnerBots()
_sync_commands = usecases.SyncBotCommands(_cipher)


async def set_default_commands_for_all_bots(
    callback: types.CallbackQuery,
    update_id: str | None = None,
):
    """Updates default commands for all connected bots."""

    if callback.from_user is None:
        _logger.warning(
            "Update id=%s: default command sync for all bots declined; "
            "Cause: user not found",
            update_id,
        )
        await callback.answer(master_text.CALLBACK_USER_NOT_FOUND, show_alert=True)
        return

    async def load_owner_bots(uow: SqlAlchemyUnitOfWork):
        result = await _list_owner_bots.execute(
            admin_usecases.ListOwnerBotsData(owner_id=callback.from_user.id),
            uow.bots,
        )
        return list(result.bots)

    try:
        db_bots = await db.run_with_unit_of_work(load_owner_bots)
    except db.DatabaseUnavailableError:
        await callback.answer(system_text.DB_UNAVAILABLE_ALERT, show_alert=True)
        return

    if not db_bots:
        await callback.answer(
            master_text.NO_BOTS_FOR_COMMAND_SYNC_ALERT, show_alert=True
        )
        return

    failed_bot_names = await _sync_commands.sync_all_registered_bots(
        db_bots,
        bot_name=get_bot_name,
    )

    _logger.info(
        "Update id=%s: bulk command sync completed; Synced count=%s; Failed count=%s",
        update_id,
        len(db_bots) - len(failed_bot_names),
        len(failed_bot_names),
    )

    await callback.answer()

    if not failed_bot_names:
        await edit_callback_message(callback, master_text.COMMANDS_UPDATED_ALL)
        return

    await edit_callback_message(
        callback, master_text.commands_bulk_failure(failed_bot_names)
    )
