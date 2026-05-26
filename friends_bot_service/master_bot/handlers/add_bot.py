import logging

from aiogram import types
from aiogram.filters import CommandObject

from friends_bot_service.bot_admin import usecases as admin_usecases
from friends_bot_service.bot_admin.interfaces import BotRuntimePort
from friends_bot_service.infra.bootstrap import db
from friends_bot_service.infra.core.config import settings
from friends_bot_service.infra.repositories.unit_of_work import SqlAlchemyUnitOfWork
from friends_bot_service.infra.texts import master_text, system_text
from friends_bot_service.master_bot import usecases

from .common import _cipher, try_delete_token_message

_logger = logging.getLogger(__name__)
_add_bot = usecases.AddBot(_cipher)


async def add_bot(
    message: types.Message,
    command: CommandObject,
    manager: BotRuntimePort,
    update_id: str | None = None,
):
    """Registers a bot: /add_bot <token from @BotFather>."""

    user = message.from_user

    if user is None:
        _logger.warning(
            "Update id=%s: bot registration declined; Cause: user not found.",
            update_id,
        )
        return

    if not settings.REGISTRATION_ENABLED:
        _logger.info(
            (
                "Update id=%s: bot registration declined; "
                "Cause: global registration shutdown."
            ),
            update_id,
        )
        await message.answer(master_text.BOT_REGISTRATION_DISABLED)
        if (command.args or "").strip():
            await try_delete_token_message(message, update_id, "add_bot")
        return

    raw = (command.args or "").strip()
    if not raw:
        await message.answer(master_text.token_command_usage("add_bot"))
        return

    token = raw

    try:
        _logger.info("Update id=%s: bot token received", update_id)

        verify_outcome, bot_info = await usecases.verify_bot_token(token)
        if verify_outcome is usecases.VerifyBotTokenOutcome.NETWORK_ERROR:
            _logger.error("Update id=%s: network error", update_id)
            await message.answer(system_text.TELEGRAM_NETWORK_ERROR)
            return
        if verify_outcome is usecases.VerifyBotTokenOutcome.INVALID_TOKEN:
            _logger.warning("Update id=%s: invalid token", update_id)
            await message.answer(system_text.INVALID_BOT_TOKEN)
            return
        if verify_outcome is usecases.VerifyBotTokenOutcome.UNEXPECTED:
            _logger.exception(
                "Update id=%s: unexpected bot registration failure", update_id
            )
            await message.answer(master_text.BOT_TOKEN_VERIFY_FAILED)
            return
        if verify_outcome is usecases.VerifyBotTokenOutcome.USERNAME_MISSING:
            _logger.error(
                "Update id=%s: bot registration declined; Cause: bot username missing",
                update_id,
            )
            await message.answer(master_text.BOT_USERNAME_MISSING)
            return

        assert bot_info is not None
        add_data = usecases.AddBotData(
            bot_id=bot_info.bot_id,
            username=bot_info.username,
            token=token,
            owner_id=user.id,
        )

        async def persist(uow: SqlAlchemyUnitOfWork):
            outcome = await _add_bot.persist(add_data, uow.bots)
            if outcome is not admin_usecases.RegisterBotOutcome.SUCCESS:
                await uow.rollback()
                return outcome
            await uow.commit()
            return outcome

        try:
            persist_outcome = await db.run_with_unit_of_work(persist)
        except db.DatabaseUnavailableError:
            await message.answer(system_text.DB_UNAVAILABLE_MESSAGE)
            return

        if persist_outcome is not admin_usecases.RegisterBotOutcome.SUCCESS:
            return

        activate_result = await _add_bot.activate(add_data, manager)

        _logger.info(
            "Update id=%s: bot registered; Bot username=%s; Bot id=%s",
            update_id,
            bot_info.username,
            bot_info.bot_id,
        )

        if activate_result.outcome is usecases.AddBotOutcome.SUCCESS:
            await message.answer(master_text.bot_registered_success(bot_info.username))
            return

        await message.answer(
            master_text.bot_registered_with_commands_warning(bot_info.username)
        )
    finally:
        await try_delete_token_message(message, update_id, "add_bot")
