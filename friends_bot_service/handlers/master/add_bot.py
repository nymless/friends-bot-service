from typing import cast

from aiogram import Bot, types
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.filters import Command, CommandObject

from friends_bot_service.bootstrap.db import (
    DatabaseUnavailableError,
    run_with_unit_of_work,
)
from friends_bot_service.core.config import settings
from friends_bot_service.infrastructure import default_token_cipher
from friends_bot_service.repositories.unit_of_work import SqlAlchemyUnitOfWork
from friends_bot_service.texts.master_text import (
    BOT_REGISTRATION_DISABLED,
    BOT_TOKEN_VERIFY_FAILED,
    BOT_USERNAME_MISSING,
    bot_registered_success,
    bot_registered_with_commands_warning,
    token_command_usage,
)
from friends_bot_service.texts.system import (
    DB_UNAVAILABLE_MESSAGE,
    INVALID_BOT_TOKEN,
    TELEGRAM_NETWORK_ERROR,
)
from friends_bot_service.usecases.bot_admin import (
    RegisterBot,
    RegisterBotCommand,
    RegisterBotOutcome,
)
from friends_bot_service.usecases.ports import BotRuntimePort

from .common import logger, router, sync_default_commands, try_delete_token_message

_cipher = default_token_cipher()


@router.message(Command("add_bot"))
async def handle_add_bot(
    message: types.Message,
    command: CommandObject,
    manager: BotRuntimePort,
    update_id: str | None = None,
):
    """Registers a bot: /add_bot <token from @BotFather>."""

    if not settings.REGISTRATION_ENABLED:
        logger.info(
            f"Handler [upd={update_id}] [command=add_bot] "
            "[details=registration_disabled]"
        )
        await message.answer(BOT_REGISTRATION_DISABLED)
        if (command.args or "").strip():
            await try_delete_token_message(message, update_id=update_id, flow="add_bot")
        return

    raw = (command.args or "").strip()
    if not raw:
        await message.answer(token_command_usage("add_bot"))
        return

    token = raw

    try:
        if message.from_user is None:
            logger.warning(
                f"Handler [upd={update_id}] [command=add_bot] [details=user_not_found]"
            )
            return

        logger.info(
            f"Handler [upd={update_id}] [command=add_bot] [details=token_received]"
        )

        try:
            async with Bot(token=token) as temp_bot:
                bot_info = await temp_bot.get_me()

        except TelegramNetworkError:
            logger.error(
                f"Handler [upd={update_id}] [command=add_bot] [details=network_error]"
            )
            await message.answer(TELEGRAM_NETWORK_ERROR)
            return

        except TelegramUnauthorizedError:
            logger.warning(
                f"Handler [upd={update_id}] [command=add_bot] [details=invalid_token]"
            )
            await message.answer(INVALID_BOT_TOKEN)
            return

        except Exception:
            logger.exception(
                f"Handler [upd={update_id}] "
                "[command=add_bot] [details=unexpected_registration_failed]"
            )
            await message.answer(BOT_TOKEN_VERIFY_FAILED)
            return

        bot_username = bot_info.username
        if bot_username is None:
            logger.error(
                f"Handler [upd={update_id}] [command=add_bot] "
                "[details=bot_username_missing]"
            )
            await message.answer(BOT_USERNAME_MISSING)
            return

        owner_id = message.from_user.id
        register_bot = RegisterBot(settings.REGISTRATION_ENABLED)

        async def _persist(uow: SqlAlchemyUnitOfWork):
            result = await register_bot.execute(
                RegisterBotCommand(
                    bot_id=bot_info.id,
                    username=bot_username,
                    encrypted_token=_cipher.encrypt(token),
                    owner_id=owner_id,
                ),
                uow.bots,
            )
            if result.outcome != RegisterBotOutcome.SUCCESS:
                await uow.rollback()
                return result
            await uow.commit()
            return result

        try:
            persist_result = await run_with_unit_of_work(_persist)
        except DatabaseUnavailableError:
            await message.answer(DB_UNAVAILABLE_MESSAGE)
            return
        if persist_result.outcome == RegisterBotOutcome.REGISTRATION_DISABLED:
            await message.answer(BOT_REGISTRATION_DISABLED)
            return
        if persist_result.outcome != RegisterBotOutcome.SUCCESS:
            return

        started_bot = cast(Bot, await manager.start_bot(token))
        commands_synced = await sync_default_commands(started_bot, bot_info.id)

        logger.info(
            f"Handler [upd={update_id}] [command=add_bot] [details=bot_registered] "
            f"[bot_username={bot_username}] [bot_id={bot_info.id}]"
        )

        if commands_synced:
            await message.answer(bot_registered_success(bot_username))
            return

        await message.answer(bot_registered_with_commands_warning(bot_username))
    finally:
        await try_delete_token_message(message, update_id=update_id, flow="add_bot")
