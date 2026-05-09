from aiogram import Bot, F, types
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.bot_manager.base import BotManager
from friends_bot_service.repositories import bot_repo

from .common import MasterStates, logger, router, try_delete_token_message


@router.message(Command("remove_bot"))
async def request_remove_token(
    message: types.Message,
    state: FSMContext,
    update_id: str,
):
    """Requests a token to remove a bot from the service."""
    await state.set_state(MasterStates.remove_token_state)

    logger.info(
        f"Handler [upd={update_id}] [command=remove_bot] [details=token_request]"
    )

    await message.answer(
        "Отправь токен бота от @BotFather, чтобы отключить его от сервиса."
    )


@router.message(MasterStates.remove_token_state, F.text.contains(":"))
async def handle_remove_token(
    message: types.Message,
    manager: BotManager,
    session: AsyncSession,
    state: FSMContext,
    update_id: str,
):
    """Handles a token and softly removes a bot from the service."""
    try:
        if message.text is None:
            logger.warning(
                f"Handler [upd={update_id}] "
                "[command=remove_bot] [details=token_missing]"
            )
            await state.clear()
            await message.answer("❌ Ошибка: не удалось прочитать токен.")
            return

        if message.from_user is None:
            logger.warning(
                f"Handler [upd={update_id}] "
                "[command=remove_bot] [details=user_not_found]"
            )
            await state.clear()
            return

        token = message.text.strip()

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
            await state.clear()
            await message.answer(
                "❌ Ошибка сети Telegram: пожалуйста, попробуйте позже."
            )
            return

        except TelegramUnauthorizedError:
            logger.warning(
                f"Handler [upd={update_id}] [command=remove_bot] "
                "[details=invalid_token]"
            )
            await state.clear()
            await message.answer("❌ Ошибка: неверный или неактивный токен.")
            return

        except Exception:
            logger.exception(
                f"Handler [upd={update_id}] "
                "[command=remove_bot] [details=unexpected_remove_failed]"
            )
            await state.clear()
            await message.answer("❌ Ошибка: не удалось проверить токен.")
            return

        deactivated = await bot_repo.deactivate_bot_for_owner(
            session=session,
            bot_id=bot_info.id,
            owner_id=message.from_user.id,
        )

        if not deactivated:
            await session.rollback()
            await state.clear()
            await message.answer(
                "Не получилось отключить бота. Проверьте токен и что он был "
                "подключён с этого Telegram-аккаунта."
            )
            return

        await session.commit()
        await manager.stop_bot(bot_info.id)
        await state.clear()

        logger.info(
            f"Handler [upd={update_id}] [command=remove_bot] [details=bot_deactivated] "
            f"[bot_username={bot_info.username}] [bot_id={bot_info.id}]"
        )

        await message.answer(f"Бот @{bot_info.username} отключён от сервиса.")
    finally:
        await try_delete_token_message(message, update_id=update_id, flow="remove_bot")
