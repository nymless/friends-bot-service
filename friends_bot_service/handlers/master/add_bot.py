from aiogram import Bot, F, types
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.bot_manager.base import BotManager
from friends_bot_service.core.config import settings
from friends_bot_service.core.security import encrypt_token
from friends_bot_service.repositories import bot_repo

from .common import (
    MasterStates,
    logger,
    router,
    sync_default_commands,
    try_delete_token_message,
)


@router.message(Command("add_bot"))
async def request_token(message: types.Message, state: FSMContext, update_id: str):
    """Requests a token to add a bot to the service."""
    await state.clear()

    if not settings.REGISTRATION_ENABLED:
        logger.info(
            f"Handler [upd={update_id}] [command=add_bot] "
            "[details=registration_disabled]"
        )
        await message.answer("Регистрация ботов временно закрыта.")
        return

    logger.info(f"Handler [upd={update_id}] [command=add_bot] [details=token_request]")

    await message.answer("Пришли мне токен бота, полученный от @BotFather.")


@router.message(~StateFilter(MasterStates.remove_token_state), F.text.contains(":"))
async def handle_token(
    message: types.Message,
    manager: BotManager,
    session: AsyncSession,
    update_id: str,
):
    """Handles a token and registers a new bot."""
    try:
        if message.text is None:
            logger.warning(
                f"Handler [upd={update_id}] [command=add_bot] [details=token_missing]"
            )
            await message.answer("❌ Ошибка: не удалось прочитать токен.")
            return

        if message.from_user is None:
            logger.warning(
                f"Handler [upd={update_id}] [command=add_bot] [details=user_not_found]"
            )
            return

        if not settings.REGISTRATION_ENABLED:
            logger.info(
                f"Handler [upd={update_id}] [command=add_bot] "
                "[details=registration_disabled]"
            )
            await message.answer("Регистрация ботов временно закрыта.")
            return

        token = message.text.strip()

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

        encrypted = encrypt_token(token)
        bot_username = bot_info.username
        if bot_username is None:
            logger.error(
                f"Handler [upd={update_id}] [command=add_bot] "
                "[details=bot_username_missing]"
            )
            await message.answer("❌ Ошибка: у бота отсутствует username.")
            return

        await bot_repo.upsert_bot(
            session=session,
            bot_id=bot_info.id,
            username=bot_username,
            encrypted_token=encrypted,
            owner_id=message.from_user.id,
        )

        await session.commit()
        bot = await manager.start_bot(token)
        commands_synced = await sync_default_commands(bot, bot_info.id)

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
