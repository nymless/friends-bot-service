from aiogram import F, types
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.repositories import bot_repo

from .common import (
    SET_DEFAULT_COMMANDS_ALL_CALLBACK,
    SET_DEFAULT_COMMANDS_BOT_PREFIX,
    build_set_default_commands_keyboard,
    edit_callback_message,
    get_bot_name,
    logger,
    router,
    sync_commands_for_bot,
)


@router.message(Command("set_default_commands"))
async def set_default_commands(
    message: types.Message,
    session: AsyncSession,
    update_id: str | None = None,
):
    """Starts the default command sync flow."""

    # Make sure the request comes from a user
    if message.from_user is None:
        logger.warning(
            f"Handler [upd={update_id}] "
            "[command=set_default_commands] [details=user_not_found]"
        )
        return

    # Read the bot owner id
    owner_id = message.from_user.id

    logger.info(
        f"Handler [upd={update_id}] "
        "[command=set_default_commands] [details=sync_requested]"
    )

    # Load the owner's active bots
    db_bots = await bot_repo.get_active_bots_for_owner(session, owner_id)

    if not db_bots:
        await message.answer(
            "У тебя пока нет подключённых ботов для обновления команд."
        )
        return

    # If there is only one bot, update it immediately
    if len(db_bots) == 1:
        registered_bot = db_bots[0]

        logger.info(
            f"Handler [upd={update_id}] "
            "[command=set_default_commands] [details=single_sync_requested] "
            f"[bot_id={registered_bot.bot_id}]"
        )

        try:
            success = await sync_commands_for_bot(registered_bot)
        except Exception:
            logger.exception(
                f"Handler [upd={update_id}] "
                "[command=set_default_commands] [details=single_sync_failed] "
                f"[bot_id={registered_bot.bot_id}]"
            )
            await message.answer("Не удалось обновить команды. Попробуй позже.")
            return

        if success:
            await message.answer(
                f"Команды для {get_bot_name(registered_bot)} обновлены."
            )
            return

        await message.answer("Не удалось обновить команды. Попробуй позже.")
        return

    logger.info(
        f"Handler [upd={update_id}] "
        "[command=set_default_commands] [details=selection_requested] "
        f"[bots_count={len(db_bots)}]"
    )

    # If there are multiple bots, show a selection keyboard
    await message.answer(
        "Выбери бота, для которого нужно обновить команды, или обнови их у всех.",
        reply_markup=build_set_default_commands_keyboard(db_bots),
    )


@router.callback_query(F.data.startswith(SET_DEFAULT_COMMANDS_BOT_PREFIX))
async def set_default_commands_for_selected_bot(
    callback: types.CallbackQuery,
    session: AsyncSession,
    update_id: str | None = None,
):
    """Updates default commands for the selected bot."""

    # Make sure the callback comes from a user and has data
    if callback.from_user is None or callback.data is None:
        logger.warning(
            f"Handler [upd={update_id}] "
            "[command=set_default_commands] [details=callback_user_not_found]"
        )
        await callback.answer("Не удалось определить пользователя.", show_alert=True)
        return

    # Extract the bot id from callback data
    try:
        bot_id = int(callback.data.removeprefix(SET_DEFAULT_COMMANDS_BOT_PREFIX))
    except ValueError:
        logger.warning(
            f"Handler [upd={update_id}] "
            "[command=set_default_commands] [details=invalid_callback_data] "
            f"[callback_data={callback.data}]"
        )
        await callback.answer("Некорректный бот.", show_alert=True)
        return

    # Load the bot record from the database
    registered_bot = await bot_repo.get_active_bot_for_owner(
        session=session,
        owner_id=callback.from_user.id,
        bot_id=bot_id,
    )

    # Make sure the bot is active and accessible to this user
    if registered_bot is None:
        logger.warning(
            f"Handler [upd={update_id}] "
            "[command=set_default_commands] [details=bot_not_owned] "
            f"[bot_id={bot_id}]"
        )
        await callback.answer("Этот бот недоступен для управления.", show_alert=True)
        return

    logger.info(
        f"Handler [upd={update_id}] "
        "[command=set_default_commands] [details=single_sync_requested] "
        f"[bot_id={registered_bot.bot_id}]"
    )

    # Update default commands for the selected bot
    try:
        success = await sync_commands_for_bot(registered_bot)
    except Exception:
        logger.exception(
            f"Handler [upd={update_id}] "
            "[command=set_default_commands] [details=single_sync_failed] "
            f"[bot_id={registered_bot.bot_id}]"
        )
        await callback.answer()
        await edit_callback_message(
            callback,
            "Не удалось обновить команды. Попробуй позже.",
        )
        return

    await callback.answer()

    # Replace the selection message with the result
    if success:
        await edit_callback_message(
            callback,
            f"Команды для {get_bot_name(registered_bot)} обновлены.",
        )
        return

    await edit_callback_message(
        callback,
        "Не удалось обновить команды. Попробуй позже.",
    )


@router.callback_query(F.data == SET_DEFAULT_COMMANDS_ALL_CALLBACK)
async def set_default_commands_for_all_bots(
    callback: types.CallbackQuery,
    session: AsyncSession,
    update_id: str | None = None,
):
    """Updates default commands for all connected bots."""

    # Make sure the callback comes from a user
    if callback.from_user is None:
        logger.warning(
            f"Handler [upd={update_id}] "
            "[command=set_default_commands] [details=callback_user_not_found]"
        )
        await callback.answer("Не удалось определить пользователя.", show_alert=True)
        return

    # Load the owner's active bots
    db_bots = await bot_repo.get_active_bots_for_owner(session, callback.from_user.id)

    # Stop early if there are no bots to update
    if not db_bots:
        await callback.answer(
            "У тебя нет подключённых ботов для обновления команд.",
            show_alert=True,
        )
        return

    # Collect bot names for failed updates
    failed_bot_names: list[str] = []

    logger.info(
        f"Handler [upd={update_id}] "
        "[command=set_default_commands] [details=bulk_sync_requested] "
        f"[bots_count={len(db_bots)}]"
    )

    # Update default commands for each bot
    for registered_bot in db_bots:
        try:
            success = await sync_commands_for_bot(registered_bot)
        except Exception:
            logger.exception(
                f"Handler [upd={update_id}] "
                "[command=set_default_commands] [details=sync_failed] "
                f"[bot_id={registered_bot.bot_id}]"
            )
            failed_bot_names.append(get_bot_name(registered_bot))
            continue

        if not success:
            failed_bot_names.append(get_bot_name(registered_bot))

    logger.info(
        f"Handler [upd={update_id}] "
        "[command=set_default_commands] [details=bulk_sync_completed] "
        f"[synced_count={len(db_bots) - len(failed_bot_names)}] "
        f"[failed_count={len(failed_bot_names)}]"
    )

    await callback.answer()

    if not failed_bot_names:
        await edit_callback_message(callback, "Команды обновлены у всех ботов.")
        return

    await edit_callback_message(
        callback,
        "Не удалось обновить команды для:\n- " + "\n- ".join(failed_bot_names),
    )
