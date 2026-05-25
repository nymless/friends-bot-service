import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.domain import GameType
from friends_bot_service.models.game_models import GameStats, Player
from friends_bot_service.repositories.sqlalchemy.stats_repository import (
    SqlAlchemyStatsRepository,
)


@pytest.fixture
def stats(db_session: AsyncSession) -> SqlAlchemyStatsRepository:
    return SqlAlchemyStatsRepository(db_session)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("game_type", "expected_rows"),
    [
        (GameType.WINNER, [("Alice", 5), ("Bob", 3)]),
        (GameType.LOSER, [("Bob", 7), ("Alice", 1)]),
    ],
)
async def test_get_top_stats_returns_sorted_rows_for_requested_game_type(
    db_session: AsyncSession,
    stats: SqlAlchemyStatsRepository,
    game_type: GameType,
    expected_rows: list[tuple[str, int]],
):
    db_session.add_all(
        [
            Player(bot_id=1, chat_id=10, user_id=1, full_name="Alice"),
            Player(bot_id=1, chat_id=10, user_id=2, full_name="Bob"),
            Player(bot_id=1, chat_id=10, user_id=3, full_name="Carol"),
            Player(bot_id=2, chat_id=10, user_id=1, full_name="Other Bot Alice"),
            GameStats(
                bot_id=1,
                chat_id=10,
                user_id=1,
                win_count=5,
                lose_count=1,
            ),
            GameStats(
                bot_id=1,
                chat_id=10,
                user_id=2,
                win_count=3,
                lose_count=7,
            ),
            GameStats(
                bot_id=1,
                chat_id=10,
                user_id=3,
                win_count=0,
                lose_count=0,
            ),
            GameStats(
                bot_id=2,
                chat_id=10,
                user_id=1,
                win_count=99,
                lose_count=99,
            ),
        ]
    )
    await db_session.commit()

    rows = await stats.top_for_chat(1, 10, game_type)

    assert [(row.full_name, row.count) for row in rows] == expected_rows
