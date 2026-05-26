import logging

from aiogram import types

from friends_bot_service.bot_admin import usecases as admin_usecases
from friends_bot_service.infra.bootstrap import db
from friends_bot_service.infra.repositories.unit_of_work import SqlAlchemyUnitOfWork
from friends_bot_service.infra.texts import master_text, system_text
from friends_bot_service.master_bot import usecases

from .common import (
    SET_DEFAULT_COMMANDS_BOT_PREFIX,
    _cipher,
    edit_callback_message,
    get_bot_name,
)

_logger = logging.getLogger(__name__)
_get_owner_bot = admin_usecases.GetOwnerBot()
_sync_commands = usecases.SyncBotCommands(_cipher)


async def set_default_commands_for_selected_bot(
    callback: types.CallbackQuery,
    update_id: str | None = None,
):
    """Updates default commands for the selected bot."""

    if callback.from_user is None or callback.data is None:
        _logger.warning(
            (
                "Update id=%s: default command sync for selected bot declined; "
                "Cause: user not found or callback data is None"
            ),
            update_id,
        )
        await callback.answer(master_text.CALLBACK_USER_NOT_FOUND, show_alert=True)
        return

    try:
        bot_id = int(callback.data.removeprefix(SET_DEFAULT_COMMANDS_BOT_PREFIX))
    except ValueError:
        _logger.warning(
            "Update id=%s: default command sync for selected bot declined; "
            "Cause: invalid callback data: %s",
            update_id,
            callback.data,
        )
        await callback.answer(master_text.CALLBACK_INVALID_BOT, show_alert=True)
        return

    async def load_owner_bot(uow: SqlAlchemyUnitOfWork):
        return await _get_owner_bot.execute(
            admin_usecases.GetOwnerBotData(
                owner_id=callback.from_user.id,
                bot_id=bot_id,
            ),
            uow.bots,
        )

    try:
        owner_bot_result = await db.run_with_unit_of_work(load_owner_bot)
    except db.DatabaseUnavailableError:
        await callback.answer(system_text.DB_UNAVAILABLE_ALERT, show_alert=True)
        return

    if owner_bot_result.outcome is admin_usecases.GetOwnerBotOutcome.NOT_FOUND:
        _logger.warning(
            "Update id=%s: default command sync for selected bot declined; "
            "Cause: bot not owned; Bot id=%s",
            update_id,
            bot_id,
        )
        await callback.answer(master_text.CALLBACK_BOT_NOT_OWNED, show_alert=True)
        return

    registered_bot = owner_bot_result.bot
    assert registered_bot is not None

    try:
        success = await _sync_commands.sync_registered_bot(registered_bot)
    except Exception:
        _logger.exception(
            "Update id=%s: single command sync failed; Bot id=%s",
            update_id,
            registered_bot.bot_id,
        )
        await callback.answer()
        await edit_callback_message(callback, master_text.COMMANDS_UPDATE_FAILED)
        return

    await callback.answer()

    if success:
        await edit_callback_message(
            callback,
            master_text.commands_updated_for_bot(get_bot_name(registered_bot)),
        )
        return

    await edit_callback_message(callback, master_text.COMMANDS_UPDATE_FAILED)
