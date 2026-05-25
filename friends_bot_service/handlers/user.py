import logging

from aiogram import Bot, Router, types
from aiogram.filters import Command

from friends_bot_service.bootstrap.dependencies import (
    registration_enabled,
    run_with_unit_of_work,
)
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
        result = await RegisterPlayer(registration_enabled()).execute(
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
            await message.answer("Регистрация игроков временно закрыта.")
            return

        await uow.commit()
        logger.info(f"Handler [upd={update_id}] [command=reg] [details=user_activated]")
        await message.answer("Ты в игре!")

    await run_with_unit_of_work(_run, message=message)


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
            await message.answer("Тебя и так нет в списках игроков.")
            return

        if result.outcome == UnregisterPlayerOutcome.ALREADY_INACTIVE:
            logger.info(
                f"Handler [upd={update_id}] [command=delete] [details=already_inactive]"
            )
            await message.answer("Тебя и так нет в списках игроков.")
            return

        await uow.commit()
        logger.info(
            f"Handler [upd={update_id}] [command=delete] [details=user_deactivated]"
        )
        await message.answer("Ты вышел из игры. Но мы всё помним... 😉")

    await run_with_unit_of_work(_run, message=message)


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
            await message.answer("Никто не зарегистрировался в игре.")
            return

        lines = []
        for i, player in enumerate(result.players, 1):
            if player.username:
                lines.append(f"{i}) {player.full_name} @{player.username}")
            else:
                lines.append(f"{i}) {player.full_name}")

        await message.answer("Участники игры в этом чате:\n" + "\n".join(lines))

    await run_with_unit_of_work(_run, message=message)


def get_router() -> Router:
    """Creates a router with user command handlers."""

    router = Router()
    router.message.register(register, Command("reg"))
    router.message.register(unregister, Command("delete"))
    router.message.register(list_players, Command("list"))
    return router
