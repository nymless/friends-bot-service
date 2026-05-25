from typing import cast

from aiogram import Bot, types
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.filters import Command, CommandObject

from friends_bot_service.bootstrap.dependencies import (
    registration_enabled,
    run_with_unit_of_work,
)
from friends_bot_service.infrastructure import default_token_cipher
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

    if not registration_enabled():
        logger.info(
            f"Handler [upd={update_id}] [command=add_bot] "
            "[details=registration_disabled]"
        )
        await message.answer("Регистрация ботов временно закрыта.")
        if (command.args or "").strip():
            await try_delete_token_message(message, update_id=update_id, flow="add_bot")
        return

    raw = (command.args or "").strip()
    if not raw:
        await message.answer(
            "Отправьте одним сообщением: `/add_bot` и токен через пробел. "
            "Токен выдаёт @BotFather."
        )
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
            await message.answer(
                "❌ Ошибка сети Telegram: пожалуйста, попробуйте позже."
            )
            return

        except TelegramUnauthorizedError:
            logger.warning(
                f"Handler [upd={update_id}] [command=add_bot] [details=invalid_token]"
            )
            await message.answer("❌ Ошибка: неверный или неактивный токен.")
            return

        except Exception:
            logger.exception(
                f"Handler [upd={update_id}] "
                "[command=add_bot] [details=unexpected_registration_failed]"
            )
            await message.answer("❌ Ошибка: не удалось верифицировать токен.")
            return

        bot_username = bot_info.username
        if bot_username is None:
            logger.error(
                f"Handler [upd={update_id}] [command=add_bot] "
                "[details=bot_username_missing]"
            )
            await message.answer("❌ Ошибка: у бота отсутствует username.")
            return

        owner_id = message.from_user.id
        register_bot = RegisterBot(registration_enabled())

        async def _persist(uow):
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

        persist_result = await run_with_unit_of_work(_persist, message=message)
        if persist_result is None:
            return
        if persist_result.outcome == RegisterBotOutcome.REGISTRATION_DISABLED:
            await message.answer("Регистрация ботов временно закрыта.")
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
            await message.answer(f"✅ Бот @{bot_username} успешно зарегистрирован!")
            return

        await message.answer(
            f"✅ Бот @{bot_username} успешно зарегистрирован!\n"
            "Команды обновить не удалось. Попробуй /set_default_commands позже."
        )
    finally:
        await try_delete_token_message(message, update_id=update_id, flow="add_bot")
