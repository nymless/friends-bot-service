from aiogram import F, types
from aiogram.filters import Command

from friends_bot_service.bootstrap.db import (
    DatabaseUnavailableError,
    run_with_unit_of_work,
)
from friends_bot_service.domain import RegisteredBot
from friends_bot_service.texts.master_text import (
    CALLBACK_BOT_NOT_OWNED,
    CALLBACK_INVALID_BOT,
    CALLBACK_USER_NOT_FOUND,
    CHOOSE_BOT_FOR_COMMAND_SYNC,
    COMMANDS_UPDATE_FAILED,
    COMMANDS_UPDATED_ALL,
    NO_BOTS_FOR_COMMAND_SYNC,
    NO_BOTS_FOR_COMMAND_SYNC_ALERT,
    commands_bulk_failure,
    commands_updated_for_bot,
)
from friends_bot_service.texts.system import (
    DB_UNAVAILABLE_ALERT,
    DB_UNAVAILABLE_MESSAGE,
)
from friends_bot_service.usecases.bot_admin import (
    GetOwnerBot,
    GetOwnerBotCommand,
    GetOwnerBotOutcome,
    ListOwnerBots,
    ListOwnerBotsCommand,
)

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

_list_owner_bots = ListOwnerBots()
_get_owner_bot = GetOwnerBot()


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
        result = await _list_owner_bots.execute(
            ListOwnerBotsCommand(owner_id=owner_id),
            uow.bots,
        )
        return list(result.bots)

    try:
        db_bots = await run_with_unit_of_work(_load)
    except DatabaseUnavailableError:
        await message.answer(DB_UNAVAILABLE_MESSAGE)
        return

    if not db_bots:
        await message.answer(NO_BOTS_FOR_COMMAND_SYNC)
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
        CHOOSE_BOT_FOR_COMMAND_SYNC,
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
        await message.answer(COMMANDS_UPDATE_FAILED)
        return

    if success:
        await message.answer(commands_updated_for_bot(get_bot_name(registered_bot)))
        return

    await message.answer(COMMANDS_UPDATE_FAILED)


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
        await callback.answer(CALLBACK_USER_NOT_FOUND, show_alert=True)
        return

    try:
        bot_id = int(callback.data.removeprefix(SET_DEFAULT_COMMANDS_BOT_PREFIX))
    except ValueError:
        logger.warning(
            f"Handler [upd={update_id}] "
            "[command=set_default_commands] [details=invalid_callback_data] "
            f"[callback_data={callback.data}]"
        )
        await callback.answer(CALLBACK_INVALID_BOT, show_alert=True)
        return

    async def _load(uow):
        return await _get_owner_bot.execute(
            GetOwnerBotCommand(owner_id=callback.from_user.id, bot_id=bot_id),
            uow.bots,
        )

    try:
        owner_bot_result = await run_with_unit_of_work(_load)
    except DatabaseUnavailableError:
        await callback.answer(DB_UNAVAILABLE_ALERT, show_alert=True)
        return

    if owner_bot_result.outcome == GetOwnerBotOutcome.NOT_FOUND:
        logger.warning(
            f"Handler [upd={update_id}] "
            "[command=set_default_commands] [details=bot_not_owned] "
            f"[bot_id={bot_id}]"
        )
        await callback.answer(CALLBACK_BOT_NOT_OWNED, show_alert=True)
        return

    registered_bot = owner_bot_result.bot
    assert registered_bot is not None

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
        await edit_callback_message(callback, COMMANDS_UPDATE_FAILED)
        return

    await callback.answer()

    if success:
        await edit_callback_message(
            callback,
            commands_updated_for_bot(get_bot_name(registered_bot)),
        )
        return

    await edit_callback_message(callback, COMMANDS_UPDATE_FAILED)


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
        await callback.answer(CALLBACK_USER_NOT_FOUND, show_alert=True)
        return

    async def _load(uow):
        result = await _list_owner_bots.execute(
            ListOwnerBotsCommand(owner_id=callback.from_user.id),
            uow.bots,
        )
        return list(result.bots)

    try:
        db_bots = await run_with_unit_of_work(_load)
    except DatabaseUnavailableError:
        await callback.answer(DB_UNAVAILABLE_ALERT, show_alert=True)
        return

    if not db_bots:
        await callback.answer(NO_BOTS_FOR_COMMAND_SYNC_ALERT, show_alert=True)
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
        await edit_callback_message(callback, COMMANDS_UPDATED_ALL)
        return

    await edit_callback_message(callback, commands_bulk_failure(failed_bot_names))
