import logging

from aiogram import Bot, Router, types
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.core.config import settings
from friends_bot_service.repositories import user_repo

logger = logging.getLogger(__name__)


async def register(
    message: types.Message, bot: Bot, session: AsyncSession, update_id: str
):
    """Registers a user with soft registration."""

    user = message.from_user

    if user is None:
        logger.warning(
            f"Handler [upd={update_id}] [command=reg] [details=user_not_found]"
        )
        return

    if not settings.REGISTRATION_ENABLED:
        logger.info(
            f"Handler [upd={update_id}] [command=reg] [details=registration_disabled]"
        )
        await message.answer("Регистрация игроков временно закрыта.")
        return

    bot_id = bot.id
    chat_id = message.chat.id
    user_id = user.id
    username = user.username
    full_name = user.full_name

    await user_repo.upsert_db_user(
        session, bot_id, chat_id, user_id, username, full_name
    )
    await session.commit()

    logger.info(f"Handler [upd={update_id}] [command=reg] [details=user_activated]")

    await message.answer("Ты в игре!")


async def unregister(
    message: types.Message, session: AsyncSession, bot: Bot, update_id: str
):
    """Unregisters a user with soft unregistration."""

    user = message.from_user

    if user is None:
        logger.warning(
            f"Handler [upd={update_id}] [command=delete] [details=user_not_found]"
        )
        return

    bot_id = bot.id
    chat_id = message.chat.id
    user_id = user.id

    db_user = await user_repo.get_db_user(session, bot_id, chat_id, user_id)

    if not db_user:
        logger.info(
            f"Handler [upd={update_id}] [command=delete] [details=db_user_not_found]"
        )
        await message.answer("Тебя и так нет в списках игроков.")
        return

    if not db_user.is_active:
        logger.info(
            f"Handler [upd={update_id}] [command=delete] [details=already_inactive]"
        )
        await message.answer("Тебя и так нет в списках игроков.")
        return

    db_user.is_active = False
    await session.commit()

    logger.info(
        f"Handler [upd={update_id}] [command=delete] [details=user_deactivated]"
    )
    await message.answer("Ты вышел из игры. Но мы всё помним... 😉")


async def list_players(
    message: types.Message, bot: Bot, session: AsyncSession, update_id: str
):
    """Lists active registered players for this bot and chat."""

    if message.from_user is None:
        logger.warning(
            f"Handler [upd={update_id}] [command=list] [details=user_not_found]"
        )
        return

    bot_id = bot.id
    chat_id = message.chat.id

    logger.info(f"Handler [upd={update_id}] [command=list] [details=list_requested]")

    players = await user_repo.list_active_players_for_chat(session, bot_id, chat_id)

    if not players:
        await message.answer("Никто не зарегистрировался в игре.")
        return

    lines = []
    for i, player in enumerate(players, 1):
        if player.username:
            lines.append(f"{i}) {player.full_name} @{player.username}")
        else:
            lines.append(f"{i}) {player.full_name}")

    await message.answer("Участники игры в этом чате:\n" + "\n".join(lines))


def get_router() -> Router:
    """Creates a router with user command handlers."""

    router = Router()
    router.message.register(register, Command("reg"))
    router.message.register(unregister, Command("delete"))
    router.message.register(list_players, Command("list"))
    return router
