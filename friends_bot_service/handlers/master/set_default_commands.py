from aiogram import F, types
from aiogram.filters import Command
from sqlalchemy.exc import InterfaceError, SQLAlchemyError

from friends_bot_service.bootstrap.dependencies import (
    run_with_unit_of_work,
    unit_of_work,
)
from friends_bot_service.domain import RegisteredBot

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
    update_id: str | None = None,
):
    """Starts the default command sync flow."""

    if message.from_user is None:
        logger.warning(
            f"Handler [upd={update_id}] "
            "[command=set_default_commands] [details=user_not_found]"
        )
        return

    owner_id = message.from_user.id

    logger.info(
        f"Handler [upd={update_id}] "
        "[command=set_default_commands] [details=sync_requested]"
    )

    async def _load(uow):
        return list(await uow.bots.list_active_for_owner(owner_id))

    db_bots = await run_with_unit_of_work(_load, message=message)
    if db_bots is None:
        return

    if not db_bots:
        await message.answer(
            "У тебя пока нет подключённых ботов для обновления команд."
        )
        return

    if len(db_bots) == 1:
        registered_bot = db_bots[0]

        logger.info(
            f"Handler [upd={update_id}] "
            "[command=set_default_commands] [details=single_sync_requested] "
            f"[bot_id={registered_bot.bot_id}]"
        )

        await _sync_one_bot(message, registered_bot, update_id=update_id)
        return

    logger.info(
        f"Handler [upd={update_id}] "
        "[command=set_default_commands] [details=selection_requested] "
        f"[bots_count={len(db_bots)}]"
    )

    await message.answer(
        "Выбери бота, для которого нужно обновить команды, или обнови их у всех.",
        reply_markup=build_set_default_commands_keyboard(db_bots),
    )


async def _sync_one_bot(
    message: types.Message,
    registered_bot: RegisteredBot,
    *,
    update_id: str | None,
) -> None:
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
        await message.answer(f"Команды для {get_bot_name(registered_bot)} обновлены.")
        return

    await message.answer("Не удалось обновить команды. Попробуй позже.")


@router.callback_query(F.data.startswith(SET_DEFAULT_COMMANDS_BOT_PREFIX))
async def set_default_commands_for_selected_bot(
    callback: types.CallbackQuery,
    update_id: str | None = None,
):
    """Updates default commands for the selected bot."""

    if callback.from_user is None or callback.data is None:
        logger.warning(
            f"Handler [upd={update_id}] "
            "[command=set_default_commands] [details=callback_user_not_found]"
        )
        await callback.answer("Не удалось определить пользователя.", show_alert=True)
        return

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

    try:
        async with unit_of_work() as uow:
            registered_bot = await uow.bots.get_active_for_owner(
                callback.from_user.id,
                bot_id,
            )
    except (InterfaceError, ConnectionError, SQLAlchemyError):
        logger.exception("DATABASE_OFFLINE")
        await callback.answer("Сервис временно недоступен.", show_alert=True)
        return

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
    update_id: str | None = None,
):
    """Updates default commands for all connected bots."""

    if callback.from_user is None:
        logger.warning(
            f"Handler [upd={update_id}] "
            "[command=set_default_commands] [details=callback_user_not_found]"
        )
        await callback.answer("Не удалось определить пользователя.", show_alert=True)
        return

    async def _load(uow):
        return list(await uow.bots.list_active_for_owner(callback.from_user.id))

    db_bots = await run_with_unit_of_work(
        _load,
        message=callback.message
        if isinstance(callback.message, types.Message)
        else None,
    )
    if db_bots is None:
        return

    if not db_bots:
        await callback.answer(
            "У тебя нет подключённых ботов для обновления команд.",
            show_alert=True,
        )
        return

    failed_bot_names: list[str] = []

    logger.info(
        f"Handler [upd={update_id}] "
        "[command=set_default_commands] [details=bulk_sync_requested] "
        f"[bots_count={len(db_bots)}]"
    )

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
