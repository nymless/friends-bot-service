from aiogram import Bot, types
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.filters import Command, CommandObject

from friends_bot_service.bootstrap.db import (
    DatabaseUnavailableError,
    run_with_unit_of_work,
)
from friends_bot_service.texts.master_text import (
    BOT_TOKEN_CHECK_FAILED,
    REMOVE_BOT_NOT_FOUND,
    bot_removed_success,
    token_command_usage,
)
from friends_bot_service.texts.system import (
    DB_UNAVAILABLE_MESSAGE,
    INVALID_BOT_TOKEN,
    TELEGRAM_NETWORK_ERROR,
)
from friends_bot_service.usecases.bot_admin import (
    RemoveBot,
    RemoveBotCommand,
    RemoveBotOutcome,
)
from friends_bot_service.usecases.ports import BotRuntimePort

from .common import logger, router, try_delete_token_message

_remove_bot = RemoveBot()


@router.message(Command("remove_bot"))
async def handle_remove_bot(
    message: types.Message,
    command: CommandObject,
    manager: BotRuntimePort,
    update_id: str | None = None,
):
    """Disconnects a bot: /remove_bot <token from @BotFather>."""

    raw = (command.args or "").strip()
    if not raw:
        await message.answer(token_command_usage("remove_bot"))
        return

    token = raw

    try:
        if message.from_user is None:
            logger.warning(
                f"Handler [upd={update_id}] "
                "[command=remove_bot] [details=user_not_found]"
            )
            return

        logger.info(
            f"Handler [upd={update_id}] [command=remove_bot] [details=token_received]"
        )

        try:
            async with Bot(token=token) as temp_bot:
                bot_info = await temp_bot.get_me()

        except TelegramNetworkError:
            logger.error(
                f"Handler [upd={update_id}] [command=remove_bot] "
                "[details=network_error]"
            )
            await message.answer(TELEGRAM_NETWORK_ERROR)
            return

        except TelegramUnauthorizedError:
            logger.warning(
                f"Handler [upd={update_id}] [command=remove_bot] "
                "[details=invalid_token]"
            )
            await message.answer(INVALID_BOT_TOKEN)
            return

        except Exception:
            logger.exception(
                f"Handler [upd={update_id}] "
                "[command=remove_bot] [details=unexpected_remove_failed]"
            )
            await message.answer(BOT_TOKEN_CHECK_FAILED)
            return

        owner_id = message.from_user.id

        async def _deactivate(uow):
            result = await _remove_bot.execute(
                RemoveBotCommand(bot_id=bot_info.id, owner_id=owner_id),
                uow.bots,
            )
            if result.outcome != RemoveBotOutcome.SUCCESS:
                await uow.rollback()
                return result
            await uow.commit()
            return result

        try:
            deactivate_result = await run_with_unit_of_work(_deactivate)
        except DatabaseUnavailableError:
            await message.answer(DB_UNAVAILABLE_MESSAGE)
            return

        if deactivate_result.outcome == RemoveBotOutcome.NOT_FOUND:
            await message.answer(REMOVE_BOT_NOT_FOUND)
            return

        await manager.stop_bot(bot_info.id)

        logger.info(
            f"Handler [upd={update_id}] [command=remove_bot] [details=bot_deactivated] "
            f"[bot_username={bot_info.username}] [bot_id={bot_info.id}]"
        )

        username = bot_info.username
        assert username is not None
        await message.answer(bot_removed_success(username))
    finally:
        await try_delete_token_message(message, update_id=update_id, flow="remove_bot")
