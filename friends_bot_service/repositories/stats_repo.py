from collections.abc import Sequence

from sqlalchemy import Row, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.enums.enums import GameType
from friends_bot_service.models.game_models import GameStats, Player


async def get_top_stats(
    session: AsyncSession, bot_id: int, chat_id: int, game_type: GameType
) -> Sequence[Row[tuple[str, int]]]:
    """
    Returns leaderboard rows (name, count) for a given chat and game type.

    Sorting is performed at the database level.
    """
    # Pick the counter column based on the game type
    sort_column = (
        GameStats.win_count if game_type == GameType.WINNER else GameStats.lose_count
    )

    stmt = (
        select(Player.full_name, sort_column)
        .join(
            GameStats,
            (GameStats.user_id == Player.user_id)
            & (GameStats.bot_id == Player.bot_id)
            & (GameStats.chat_id == Player.chat_id),
        )
        .where(
            GameStats.bot_id == bot_id,
            GameStats.chat_id == chat_id,
            sort_column > 0,
        )
        .order_by(desc(sort_column))
    )

    result = await session.execute(stmt)
    # Return rows that behave like (name, count) tuples
    return result.all()
