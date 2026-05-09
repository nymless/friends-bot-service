from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.models.game_models import Player


async def get_db_user(
    session: AsyncSession, bot_id: int, chat_id: int, user_id: int
) -> Player | None:
    """
    Fetches an existing game user from the database.

    RAISES:
    - `sqlalchemy.exc.MultipleResultsFound`
    """
    stmt = select(Player).where(
        Player.bot_id == bot_id,
        Player.chat_id == chat_id,
        Player.user_id == user_id,
    )
    result = await session.execute(stmt)
    db_user = result.scalar_one_or_none()
    return db_user


async def upsert_db_user(
    session: AsyncSession,
    bot_id: int,
    chat_id: int,
    user_id: int,
    username: str | None,
    full_name: str,
) -> Player:
    """
    Atomically upserts a game user in the database.

    If the user already exists, the record is updated and activated.

    RAISES:
    - `sqlalchemy.exc.MultipleResultsFound`
    - `sqlalchemy.exc.NoResultFound`
    """
    result = await session.execute(
        insert(Player)
        .values(
            bot_id=bot_id,
            chat_id=chat_id,
            user_id=user_id,
            username=username,
            full_name=full_name,
        )
        .on_conflict_do_update(
            index_elements=["bot_id", "chat_id", "user_id"],
            set_={
                "username": username,
                "full_name": full_name,
                "is_active": True,
                "updated_at": func.now(),
            },
        )
        .returning(Player)
    )
    await session.flush()
    return result.scalar_one()
