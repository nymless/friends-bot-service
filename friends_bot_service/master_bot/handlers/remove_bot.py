import logging

from aiogram import types
from aiogram.filters import CommandObject

from friends_bot_service.bot_admin import usecases as admin_usecases
from friends_bot_service.bot_admin.interfaces import BotRuntimePort
from friends_bot_service.infra.bootstrap import db
from friends_bot_service.infra.repositories.unit_of_work import SqlAlchemyUnitOfWork
from friends_bot_service.infra.texts import master_text, system_text
from friends_bot_service.master_bot import usecases

from .common import try_delete_token_message

_logger = logging.getLogger(__name__)
_remove_bot = usecases.RemoveBot()


async def remove_bot(
    message: types.Message,
    command: CommandObject,
    manager: BotRuntimePort,
    update_id: str | None = None,
):
    """Disconnects a bot: /remove_bot <token from @BotFather>."""

    user = message.from_user

    if user is None:
        _logger.warning(
            "Update id=%s: bot removal declined; Cause: user not found.",
            update_id,
        )
        return

    raw = (command.args or "").strip()
    if not raw:
        await message.answer(master_text.token_command_usage("remove_bot"))
        return

    token = raw

    try:
        _logger.info("Update id=%s: bot token received", update_id)

        verify_outcome, bot_info = await usecases.verify_bot_token(token)
        if verify_outcome is usecases.VerifyBotTokenOutcome.NETWORK_ERROR:
            _logger.error(
                "Update id=%s: bot removal failed; Cause: network error", update_id
            )
            await message.answer(system_text.TELEGRAM_NETWORK_ERROR)
            return
        if verify_outcome is usecases.VerifyBotTokenOutcome.INVALID_TOKEN:
            _logger.warning(
                "Update id=%s: bot removal failed; Cause: invalid token", update_id
            )
            await message.answer(system_text.INVALID_BOT_TOKEN)
            return
        if verify_outcome is usecases.VerifyBotTokenOutcome.UNEXPECTED:
            _logger.exception("Update id=%s: unexpected bot removal failure", update_id)
            await message.answer(master_text.BOT_TOKEN_CHECK_FAILED)
            return
        if verify_outcome is usecases.VerifyBotTokenOutcome.USERNAME_MISSING:
            _logger.error(
                "Update id=%s: bot removal declined; Cause: bot username missing",
                update_id,
            )
            await message.answer(master_text.BOT_USERNAME_MISSING)
            return

        assert bot_info is not None
        remove_data = usecases.RemoveBotData(
            bot_id=bot_info.bot_id,
            owner_id=user.id,
        )

        async def deactivate(uow: SqlAlchemyUnitOfWork):
            outcome = await _remove_bot.deactivate(remove_data, uow.bots)
            if outcome is not admin_usecases.RemoveBotOutcome.SUCCESS:
                await uow.rollback()
                return outcome
            await uow.commit()
            return outcome

        try:
            deactivate_outcome = await db.run_with_unit_of_work(deactivate)
        except db.DatabaseUnavailableError:
            await message.answer(system_text.DB_UNAVAILABLE_MESSAGE)
            return

        if deactivate_outcome is admin_usecases.RemoveBotOutcome.NOT_FOUND:
            await message.answer(master_text.REMOVE_BOT_NOT_FOUND)
            return

        await _remove_bot.stop_runtime(bot_info.bot_id, manager)

        _logger.info(
            "Update id=%s: bot deactivated; Bot username=%s; Bot id=%s",
            update_id,
            bot_info.username,
            bot_info.bot_id,
        )

        await message.answer(master_text.bot_removed_success(bot_info.username))
    finally:
        await try_delete_token_message(message, update_id, "remove_bot")
