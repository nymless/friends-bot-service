from aiogram import Bot, types
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.filters import Command, CommandObject

from friends_bot_service.bootstrap.dependencies import run_with_unit_of_work
from friends_bot_service.bot_manager.base import BotManager

from .common import logger, router, try_delete_token_message


@router.message(Command("remove_bot"))
async def handle_remove_bot(
    message: types.Message,
    command: CommandObject,
    manager: BotManager,
    update_id: str | None = None,
):
    """Disconnects a bot: /remove_bot <token from @BotFather>."""

    raw = (command.args or "").strip()
    if not raw:
        await message.answer(
            "Отправьте одним сообщением: `/remove_bot` и токен через пробел. "
            "Токен выдаёт @BotFather."
        )
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
            await message.answer(
                "❌ Ошибка сети Telegram: пожалуйста, попробуйте позже."
            )
            return

        except TelegramUnauthorizedError:
            logger.warning(
                f"Handler [upd={update_id}] [command=remove_bot] "
                "[details=invalid_token]"
            )
            await message.answer("❌ Ошибка: неверный или неактивный токен.")
            return

        except Exception:
            logger.exception(
                f"Handler [upd={update_id}] "
                "[command=remove_bot] [details=unexpected_remove_failed]"
            )
            await message.answer("❌ Ошибка: не удалось проверить токен.")
            return

        owner_id = message.from_user.id

        async def _deactivate(uow):
            deactivated = await uow.bots.deactivate_for_owner(
                bot_id=bot_info.id,
                owner_id=owner_id,
            )
            if not deactivated:
                await uow.rollback()
                return False
            await uow.commit()
            return True

        deactivated = await run_with_unit_of_work(_deactivate, message=message)
        if deactivated is None:
            return

        if not deactivated:
            await message.answer(
                "Не получилось отключить бота. Проверьте токен и что он был "
                "подключён с этого Telegram-аккаунта."
            )
            return

        await manager.stop_bot(bot_info.id)

        logger.info(
            f"Handler [upd={update_id}] [command=remove_bot] [details=bot_deactivated] "
            f"[bot_username={bot_info.username}] [bot_id={bot_info.id}]"
        )

        await message.answer(f"Бот @{bot_info.username} отключён от сервиса.")
    finally:
        await try_delete_token_message(message, update_id=update_id, flow="remove_bot")
