from collections.abc import Callable
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.draw.domain import GameType
from friends_bot_service.infra.models.draw_models import DrawEntrantORM, DrawStatsORM
from friends_bot_service.infra.repositories.sqlalchemy import (
    draw_repository as draw_repository_module,
)
from friends_bot_service.infra.repositories.sqlalchemy.draw_repository import (
    SqlAlchemyDrawRepository,
)


@pytest.fixture
def games(db_session: AsyncSession) -> SqlAlchemyDrawRepository:
    return SqlAlchemyDrawRepository(db_session)


@pytest.mark.asyncio
async def test_get_game_stats_returns_today_result_for_requested_game_type(
    db_session: AsyncSession,
    games: SqlAlchemyDrawRepository,
):
    today = date.today()
    db_session.add(
        DrawStatsORM(bot_id=1, chat_id=10, user_id=100, win_count=1, last_win=today)
    )
    await db_session.commit()

    has_winner = await games.has_draw_today(1, 10, GameType.WINNER, today)
    has_loser = await games.has_draw_today(1, 10, GameType.LOSER, today)

    assert has_winner is True
    assert has_loser is False


@pytest.mark.asyncio
async def test_get_players_excludes_users_with_today_result(
    db_session: AsyncSession,
    games: SqlAlchemyDrawRepository,
):
    today = date.today()
    db_session.add_all(
        [
            DrawEntrantORM(bot_id=1, chat_id=10, user_id=100, full_name="User 100"),
            DrawEntrantORM(bot_id=1, chat_id=10, user_id=200, full_name="User 200"),
            DrawStatsORM(
                bot_id=1, chat_id=10, user_id=200, win_count=1, last_win=today
            ),
        ]
    )
    await db_session.commit()

    players = await games.list_eligible_players(1, 10, today)

    assert [player.user_id for player in players] == [100]


@pytest.mark.asyncio
async def test_get_players_isolated_by_chat(
    db_session: AsyncSession,
    games: SqlAlchemyDrawRepository,
):
    today = date.today()
    db_session.add_all(
        [
            DrawEntrantORM(bot_id=1, chat_id=10, user_id=777, full_name="Shared User"),
            DrawEntrantORM(bot_id=1, chat_id=20, user_id=777, full_name="Shared User"),
            DrawStatsORM(
                bot_id=1, chat_id=10, user_id=777, lose_count=1, last_lose=today
            ),
        ]
    )
    await db_session.commit()

    chat_one_players = await games.list_eligible_players(1, 10, today)
    chat_two_players = await games.list_eligible_players(1, 20, today)

    assert chat_one_players == []
    assert [player.user_id for player in chat_two_players] == [777]


@pytest.mark.asyncio
async def test_get_players_isolated_by_bot(
    db_session: AsyncSession,
    games: SqlAlchemyDrawRepository,
):
    today = date.today()
    db_session.add_all(
        [
            DrawEntrantORM(bot_id=1, chat_id=10, user_id=777, full_name="Shared User"),
            DrawEntrantORM(bot_id=2, chat_id=10, user_id=777, full_name="Shared User"),
            DrawStatsORM(
                bot_id=1, chat_id=10, user_id=777, lose_count=1, last_lose=today
            ),
        ]
    )
    await db_session.commit()

    bot_one_players = await games.list_eligible_players(1, 10, today)
    bot_two_players = await games.list_eligible_players(2, 10, today)

    assert bot_one_players == []
    assert [player.user_id for player in bot_two_players] == [777]


@pytest.mark.asyncio
async def test_get_players_excludes_inactive_players(
    db_session: AsyncSession,
    games: SqlAlchemyDrawRepository,
):
    today = date.today()
    db_session.add_all(
        [
            DrawEntrantORM(bot_id=1, chat_id=10, user_id=100, full_name="Active User"),
            DrawEntrantORM(
                bot_id=1,
                chat_id=10,
                user_id=200,
                full_name="Inactive User",
                is_active=False,
            ),
        ]
    )
    await db_session.commit()

    players = await games.list_eligible_players(1, 10, today)

    assert [player.user_id for player in players] == [100]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("game_type", "count_attr", "date_attr", "other_count_attr", "other_date_attr"),
    [
        (GameType.WINNER, "win_count", "last_win", "lose_count", "last_lose"),
        (GameType.LOSER, "lose_count", "last_lose", "win_count", "last_win"),
    ],
)
async def test_update_game_stats_creates_and_increments_stats_row(
    db_session: AsyncSession,
    games: SqlAlchemyDrawRepository,
    patch_sqlite_upsert: Callable[..., None],
    game_type: GameType,
    count_attr: str,
    date_attr: str,
    other_count_attr: str,
    other_date_attr: str,
):
    patch_sqlite_upsert(draw_repository_module)

    today = date.today()
    await games.record_draw_result(1, 10, 100, game_type, today)
    await games.record_draw_result(1, 10, 100, game_type, today)
    await db_session.commit()

    result = await db_session.execute(
        select(DrawStatsORM).where(
            DrawStatsORM.bot_id == 1,
            DrawStatsORM.chat_id == 10,
            DrawStatsORM.user_id == 100,
        )
    )
    stats = result.scalar_one()

    assert getattr(stats, count_attr) == 2
    assert getattr(stats, date_attr) == today
    assert getattr(stats, other_count_attr) == 0
    assert getattr(stats, other_date_attr) is None


@pytest.mark.asyncio
async def test_unique_winner_constraint_prevents_two_winners_same_day(
    db_session: AsyncSession,
):
    today = date.today()
    db_session.add(
        DrawStatsORM(bot_id=123, chat_id=456, user_id=1, last_win=today, win_count=1)
    )
    await db_session.commit()

    db_session.add(
        DrawStatsORM(bot_id=123, chat_id=456, user_id=2, last_win=today, win_count=1)
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()
