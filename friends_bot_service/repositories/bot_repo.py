from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.models.bot_models import RegisteredBot


async def upsert_bot(
    session: AsyncSession,
    bot_id: int,
    username: str,
    encrypted_token: str,
    owner_id: int,
) -> RegisteredBot:
    """
    Registers a new bot or atomically updates and reactivates an existing one.

    RAISES:
    - `sqlalchemy.exc.MultipleResultsFound`
    - `sqlalchemy.exc.NoResultFound`
    """
    stmt = (
        insert(RegisteredBot)
        .values(
            bot_id=bot_id,
            username=username,
            encrypted_token=encrypted_token,
            owner_id=owner_id,
            is_active=True,
        )
        .on_conflict_do_update(
            index_elements=["bot_id"],
            set_={
                "username": username,
                "encrypted_token": encrypted_token,
                "is_active": True,
                "updated_at": func.now(),
            },
        )
        .returning(RegisteredBot)
    )

    result = await session.execute(stmt)
    await session.flush()
    return result.scalar_one()


async def deactivate_bot_for_owner(
    session: AsyncSession,
    bot_id: int,
    owner_id: int,
) -> bool:
    """Softly deactivates a bot for an owner."""

    stmt = (
        update(RegisteredBot)
        .where(
            RegisteredBot.bot_id == bot_id,
            RegisteredBot.owner_id == owner_id,
        )
        .values(is_active=False, updated_at=func.now())
        .returning(RegisteredBot.bot_id)
    )
    result = await session.execute(stmt)
    await session.flush()
    return result.scalar_one_or_none() is not None


async def touch_bot_last_game_attempt(
    session: AsyncSession,
    bot_id: int,
) -> None:
    """Updates the last game attempt time for a bot."""

    stmt = (
        update(RegisteredBot)
        .where(RegisteredBot.bot_id == bot_id)
        .values(last_game_attempt_at=func.now(), updated_at=func.now())
    )
    await session.execute(stmt)
    await session.flush()


async def deactivate_stale_bots(
    session: AsyncSession,
    cutoff: datetime,
) -> list[tuple[int, str]]:
    """Deactivates bots that have not been used since the cutoff."""

    stmt = (
        update(RegisteredBot)
        .where(
            RegisteredBot.is_active,
            func.coalesce(
                RegisteredBot.last_game_attempt_at,
                RegisteredBot.created_at,
            )
            < cutoff,
        )
        .values(is_active=False, updated_at=func.now())
        .returning(RegisteredBot.bot_id, RegisteredBot.username)
    )
    result = await session.execute(stmt)
    await session.flush()
    return [(bot_id, username) for bot_id, username in result.all()]


async def get_active_bots_for_owner(
    session: AsyncSession,
    owner_id: int,
) -> list[RegisteredBot]:
    """Fetches all active bots for an owner."""

    stmt = select(RegisteredBot).where(
        RegisteredBot.owner_id == owner_id,
        RegisteredBot.is_active,
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_active_bot_for_owner(
    session: AsyncSession,
    owner_id: int,
    bot_id: int,
) -> RegisteredBot | None:
    """Fetches an active bot for an owner."""

    stmt = select(RegisteredBot).where(
        RegisteredBot.owner_id == owner_id,
        RegisteredBot.bot_id == bot_id,
        RegisteredBot.is_active,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
