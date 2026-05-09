from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.enums.enums import DateCol, GameType
from friends_bot_service.models.game_models import GameStats, Player


async def get_game_stats(
    session: AsyncSession,
    bot_id: int,
    chat_id: int,
    game_type: GameType,
    today: date,
) -> GameStats | None:
    """
    Checks if today's draw has already been run.

    RAISES:
    - `sqlalchemy.exc.MultipleResultsFound`
    """
    stmt = select(GameStats).where(
        GameStats.bot_id == bot_id,
        GameStats.chat_id == chat_id,
        (
            GameStats.last_win == today
            if game_type == GameType.WINNER
            else GameStats.last_lose == today
        ),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_players(
    session: AsyncSession,
    bot_id: int,
    chat_id: int,
    today: date,
) -> Sequence[Player]:
    """Returns active players who have not won or lost today."""

    skipped_players_stmt = select(GameStats.user_id).where(
        GameStats.bot_id == bot_id,
        GameStats.chat_id == chat_id,
        (getattr(GameStats, DateCol.LAST_WIN) == today)
        | (getattr(GameStats, DateCol.LAST_LOSE) == today),
    )

    stmt = select(Player).where(
        Player.bot_id == bot_id,
        Player.chat_id == chat_id,
        Player.is_active,
        Player.user_id.not_in(skipped_players_stmt),
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def update_game_stats(
    session: AsyncSession,
    bot_id: int,
    chat_id: int,
    winner_id: int,
    game_type: GameType,
    today_utc: date,
):
    """
    Atomically updates win or loss statistics.

    RAISES:
    - `sqlalchemy.exc.IntegrityError`
    """
    # Choose columns to update based on the game type
    if game_type == GameType.WINNER:
        insert_vals = {"win_count": 1, "last_win": today_utc}
        update_vals = {"win_count": GameStats.win_count + 1, "last_win": today_utc}
    else:
        insert_vals = {"lose_count": 1, "last_lose": today_utc}
        update_vals = {"lose_count": GameStats.lose_count + 1, "last_lose": today_utc}

    # Insert a new row or increment the existing counter atomically
    stmt = (
        insert(GameStats)
        .values(bot_id=bot_id, chat_id=chat_id, user_id=winner_id, **insert_vals)
        .on_conflict_do_update(
            index_elements=["bot_id", "chat_id", "user_id"], set_=update_vals
        )
    )

    await session.execute(stmt)
    await session.flush()
