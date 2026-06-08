import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.draw.domain import DrawType
from friends_bot_service.infra.models.draw_models import DrawEntrantORM, DrawStatsORM
from friends_bot_service.infra.repositories.sqlalchemy.draw_stats_repository import (
    SqlAlchemyDrawStatsRepository,
)


@pytest.fixture
def stats(db_session: AsyncSession) -> SqlAlchemyDrawStatsRepository:
    return SqlAlchemyDrawStatsRepository(db_session)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("draw_type", "expected_rows"),
    [
        (DrawType.WINNER, [("Alice", 5), ("Bob", 3)]),
        (DrawType.LOSER, [("Bob", 7), ("Alice", 1)]),
    ],
)
async def test_get_top_stats_returns_sorted_rows_for_requested_draw_type(
    db_session: AsyncSession,
    stats: SqlAlchemyDrawStatsRepository,
    draw_type: DrawType,
    expected_rows: list[tuple[str, int]],
):
    db_session.add_all(
        [
            DrawEntrantORM(bot_id=1, chat_id=10, user_id=1, full_name="Alice"),
            DrawEntrantORM(bot_id=1, chat_id=10, user_id=2, full_name="Bob"),
            DrawEntrantORM(bot_id=1, chat_id=10, user_id=3, full_name="Carol"),
            DrawEntrantORM(
                bot_id=2, chat_id=10, user_id=1, full_name="Other Bot Alice"
            ),
            DrawStatsORM(
                bot_id=1,
                chat_id=10,
                user_id=1,
                win_count=5,
                lose_count=1,
            ),
            DrawStatsORM(
                bot_id=1,
                chat_id=10,
                user_id=2,
                win_count=3,
                lose_count=7,
            ),
            DrawStatsORM(
                bot_id=1,
                chat_id=10,
                user_id=3,
                win_count=0,
                lose_count=0,
            ),
            DrawStatsORM(
                bot_id=2,
                chat_id=10,
                user_id=1,
                win_count=99,
                lose_count=99,
            ),
        ]
    )
    await db_session.commit()

    rows = await stats.top_for_chat(1, 10, draw_type)

    assert [(row.full_name, row.count) for row in rows] == expected_rows
