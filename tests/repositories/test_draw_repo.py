from collections.abc import Callable
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.draw.domain import DrawType
from friends_bot_service.infra.models.draw_models import DrawEntrantORM, DrawStatsORM
from friends_bot_service.infra.repositories.sqlalchemy import (
    draw_repository as draw_repository_module,
)
from friends_bot_service.infra.repositories.sqlalchemy.draw_repository import (
    SqlAlchemyDrawRepository,
)


@pytest.fixture
def draws(db_session: AsyncSession) -> SqlAlchemyDrawRepository:
    return SqlAlchemyDrawRepository(db_session)


@pytest.mark.asyncio
async def test_get_draw_stats_returns_today_result_for_requested_draw_type(
    db_session: AsyncSession,
    draws: SqlAlchemyDrawRepository,
):
    today = date.today()
    db_session.add(
        DrawStatsORM(bot_id=1, chat_id=10, user_id=100, win_count=1, last_win=today)
    )
    await db_session.commit()

    has_winner = await draws.has_draw_today(1, 10, DrawType.WINNER, today)
    has_loser = await draws.has_draw_today(1, 10, DrawType.LOSER, today)

    assert has_winner is True
    assert has_loser is False


@pytest.mark.asyncio
async def test_get_draw_entrants_excludes_users_with_today_result(
    db_session: AsyncSession,
    draws: SqlAlchemyDrawRepository,
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

    draw_entrants = await draws.list_eligible_draw_entrants(1, 10, today)

    assert [draw_entrant.user_id for draw_entrant in draw_entrants] == [100]


@pytest.mark.asyncio
async def test_get_draw_entrants_isolated_by_chat(
    db_session: AsyncSession,
    draws: SqlAlchemyDrawRepository,
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

    chat_one_draw_entrants = await draws.list_eligible_draw_entrants(1, 10, today)
    chat_two_draw_entrants = await draws.list_eligible_draw_entrants(1, 20, today)

    assert chat_one_draw_entrants == []
    assert [draw_entrant.user_id for draw_entrant in chat_two_draw_entrants] == [777]


@pytest.mark.asyncio
async def test_get_draw_entrants_isolated_by_bot(
    db_session: AsyncSession,
    draws: SqlAlchemyDrawRepository,
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

    bot_one_draw_entrants = await draws.list_eligible_draw_entrants(1, 10, today)
    bot_two_draw_entrants = await draws.list_eligible_draw_entrants(2, 10, today)

    assert bot_one_draw_entrants == []
    assert [draw_entrant.user_id for draw_entrant in bot_two_draw_entrants] == [777]


@pytest.mark.asyncio
async def test_get_draw_entrants_excludes_inactive_players(
    db_session: AsyncSession,
    draws: SqlAlchemyDrawRepository,
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

    draw_entrants = await draws.list_eligible_draw_entrants(1, 10, today)

    assert [draw_entrant.user_id for draw_entrant in draw_entrants] == [100]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("draw_type", "count_attr", "date_attr", "other_count_attr", "other_date_attr"),
    [
        (DrawType.WINNER, "win_count", "last_win", "lose_count", "last_lose"),
        (DrawType.LOSER, "lose_count", "last_lose", "win_count", "last_win"),
    ],
)
async def test_update_draw_stats_creates_and_increments_stats_row(
    db_session: AsyncSession,
    draws: SqlAlchemyDrawRepository,
    patch_sqlite_upsert: Callable[..., None],
    draw_type: DrawType,
    count_attr: str,
    date_attr: str,
    other_count_attr: str,
    other_date_attr: str,
):
    patch_sqlite_upsert(draw_repository_module)

    today = date.today()
    await draws.record_draw_result(1, 10, 100, draw_type, today)
    await draws.record_draw_result(1, 10, 100, draw_type, today)
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


@pytest.mark.asyncio
async def test_has_claim_today_returns_true_after_claim(
    db_session: AsyncSession,
    draws: SqlAlchemyDrawRepository,
    patch_sqlite_upsert: Callable[..., None],
):
    patch_sqlite_upsert(draw_repository_module)
    today = date.today()

    await draws.claim_draw(1, 10, 100, DrawType.WINNER, today)
    await db_session.commit()

    assert await draws.has_claim_today(1, 10, DrawType.WINNER, today) is True
    assert await draws.has_claim_today(1, 10, DrawType.LOSER, today) is False


@pytest.mark.asyncio
async def test_claim_draw_rejects_second_claim_same_day(
    db_session: AsyncSession,
    draws: SqlAlchemyDrawRepository,
    patch_sqlite_upsert: Callable[..., None],
):
    patch_sqlite_upsert(draw_repository_module)
    today = date.today()

    await draws.claim_draw(1, 10, 100, DrawType.WINNER, today)
    await db_session.commit()

    with pytest.raises(IntegrityError):
        await draws.claim_draw(1, 10, 200, DrawType.WINNER, today)
        await db_session.commit()
