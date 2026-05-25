import logging

from aiogram import Bot, Router, types
from aiogram.filters import Command

from friends_bot_service.bootstrap.db import (
    DatabaseUnavailableError,
    run_with_unit_of_work,
)
from friends_bot_service.core.config import settings
from friends_bot_service.texts.player_text import (
    PLAYER_ALREADY_NOT_IN_LIST,
    PLAYER_LIST_EMPTY,
    PLAYER_LIST_HEADER,
    PLAYER_REGISTERED,
    PLAYER_REGISTRATION_DISABLED,
    PLAYER_UNREGISTERED,
)
from friends_bot_service.texts.system import DB_UNAVAILABLE_MESSAGE
from friends_bot_service.usecases.user import (
    ListPlayers,
    ListPlayersCommand,
    ListPlayersOutcome,
    RegisterPlayer,
    RegisterPlayerCommand,
    RegisterPlayerOutcome,
    UnregisterPlayer,
    UnregisterPlayerCommand,
    UnregisterPlayerOutcome,
)

logger = logging.getLogger(__name__)

_unregister_player = UnregisterPlayer()
_list_players = ListPlayers()


async def register(
    message: types.Message,
    bot: Bot,
    update_id: str | None = None,
):
    """Registers a user with soft registration."""

    async def _run(uow):
        command = RegisterPlayerCommand(
            bot_id=bot.id,
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else None,
            username=message.from_user.username if message.from_user else None,
            full_name=message.from_user.full_name if message.from_user else "",
        )
        result = await RegisterPlayer(settings.REGISTRATION_ENABLED).execute(
            command, uow.users
        )

        if result.outcome == RegisterPlayerOutcome.USER_MISSING:
            logger.warning(
                f"Handler [upd={update_id}] [command=reg] [details=user_not_found]"
            )
            return

        if result.outcome == RegisterPlayerOutcome.REGISTRATION_DISABLED:
            logger.info(
                f"Handler [upd={update_id}] [command=reg] "
                "[details=registration_disabled]"
            )
            await message.answer(PLAYER_REGISTRATION_DISABLED)
            return

        await uow.commit()
        logger.info(f"Handler [upd={update_id}] [command=reg] [details=user_activated]")
        await message.answer(PLAYER_REGISTERED)

    try:
        await run_with_unit_of_work(_run)
    except DatabaseUnavailableError:
        await message.answer(DB_UNAVAILABLE_MESSAGE)


async def unregister(
    message: types.Message,
    bot: Bot,
    update_id: str | None = None,
):
    """Unregisters a user with soft unregistration."""

    async def _run(uow):
        command = UnregisterPlayerCommand(
            bot_id=bot.id,
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else None,
        )
        result = await _unregister_player.execute(command, uow.users)

        if result.outcome == UnregisterPlayerOutcome.USER_MISSING:
            logger.warning(
                f"Handler [upd={update_id}] [command=delete] [details=user_not_found]"
            )
            return

        if result.outcome == UnregisterPlayerOutcome.NOT_FOUND:
            logger.info(
                f"Handler [upd={update_id}] [command=delete] "
                "[details=db_user_not_found]"
            )
            await message.answer(PLAYER_ALREADY_NOT_IN_LIST)
            return

        if result.outcome == UnregisterPlayerOutcome.ALREADY_INACTIVE:
            logger.info(
                f"Handler [upd={update_id}] [command=delete] [details=already_inactive]"
            )
            await message.answer(PLAYER_ALREADY_NOT_IN_LIST)
            return

        await uow.commit()
        logger.info(
            f"Handler [upd={update_id}] [command=delete] [details=user_deactivated]"
        )
        await message.answer(PLAYER_UNREGISTERED)

    try:
        await run_with_unit_of_work(_run)
    except DatabaseUnavailableError:
        await message.answer(DB_UNAVAILABLE_MESSAGE)


async def list_players(
    message: types.Message,
    bot: Bot,
    update_id: str | None = None,
):
    """Lists active registered players for this bot and chat."""

    async def _run(uow):
        command = ListPlayersCommand(
            bot_id=bot.id,
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else None,
        )
        result = await _list_players.execute(command, uow.users)

        if result.outcome == ListPlayersOutcome.USER_MISSING:
            logger.warning(
                f"Handler [upd={update_id}] [command=list] [details=user_not_found]"
            )
            return

        logger.info(
            f"Handler [upd={update_id}] [command=list] [details=list_requested]"
        )

        if result.outcome == ListPlayersOutcome.EMPTY:
            await message.answer(PLAYER_LIST_EMPTY)
            return

        lines = []
        for i, player in enumerate(result.players, 1):
            if player.username:
                lines.append(f"{i}) {player.full_name} @{player.username}")
            else:
                lines.append(f"{i}) {player.full_name}")

        await message.answer(PLAYER_LIST_HEADER + "\n".join(lines))

    try:
        await run_with_unit_of_work(_run)
    except DatabaseUnavailableError:
        await message.answer(DB_UNAVAILABLE_MESSAGE)


def get_router() -> Router:
    """Creates a router with user command handlers."""

    router = Router()
    router.message.register(register, Command("reg"))
    router.message.register(unregister, Command("delete"))
    router.message.register(list_players, Command("list"))
    return router
