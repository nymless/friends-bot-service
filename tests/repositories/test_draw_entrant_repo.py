from collections.abc import Callable

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.draw_entrant.domain import DrawEntrant, DrawEntrantKey
from friends_bot_service.infra.models.draw_models import DrawEntrantORM
from friends_bot_service.infra.repositories.sqlalchemy import (
    draw_entrant_repository as draw_entrant_repository_module,
)
from friends_bot_service.infra.repositories.sqlalchemy.draw_entrant_repository import (
    SqlAlchemyDrawEntrantRepository,
)


@pytest.fixture
def users(db_session: AsyncSession) -> SqlAlchemyDrawEntrantRepository:
    return SqlAlchemyDrawEntrantRepository(db_session)


@pytest.mark.asyncio
async def test_get_db_user_returns_matching_player_and_none_for_missing(
    db_session: AsyncSession,
    users: SqlAlchemyDrawEntrantRepository,
):
    db_session.add(
        DrawEntrantORM(bot_id=1, chat_id=10, user_id=100, full_name="Lookup User")
    )
    await db_session.commit()

    existing_player = await users.get(DrawEntrantKey(1, 10, 100))
    missing_player = await users.get(DrawEntrantKey(1, 10, 999))

    assert existing_player is not None
    assert existing_player.user_id == 100
    assert missing_player is None


@pytest.mark.asyncio
async def test_list_active_players_for_chat_scopes_bot_chat_and_skips_inactive(
    db_session: AsyncSession,
    users: SqlAlchemyDrawEntrantRepository,
):
    db_session.add_all(
        [
            DrawEntrantORM(
                bot_id=1,
                chat_id=10,
                user_id=1,
                username="one",
                full_name="Active One",
                is_active=True,
            ),
            DrawEntrantORM(
                bot_id=1,
                chat_id=10,
                user_id=2,
                username="two",
                full_name="Inactive",
                is_active=False,
            ),
            DrawEntrantORM(
                bot_id=1,
                chat_id=99,
                user_id=3,
                username="three",
                full_name="Other chat",
                is_active=True,
            ),
        ]
    )
    await db_session.commit()

    roster = await users.list_active_for_chat(1, 10)
    user_ids = [p.user_id for p in roster]

    assert user_ids == [1]


@pytest.mark.asyncio
async def test_upsert_db_user_creates_new_player(
    db_session: AsyncSession,
    users: SqlAlchemyDrawEntrantRepository,
    patch_sqlite_upsert: Callable[..., None],
):
    patch_sqlite_upsert(draw_entrant_repository_module)

    player = await users.upsert_active(
        DrawEntrant(
            bot_id=1,
            chat_id=10,
            user_id=100,
            username="first_user",
            full_name="First User",
        )
    )
    await db_session.commit()

    result = await db_session.execute(
        select(DrawEntrantORM).where(
            DrawEntrantORM.bot_id == 1,
            DrawEntrantORM.chat_id == 10,
            DrawEntrantORM.user_id == 100,
        )
    )
    players = result.scalars().all()

    assert player.bot_id == 1
    assert player.chat_id == 10
    assert player.user_id == 100
    assert player.username == "first_user"
    assert player.full_name == "First User"
    assert player.is_active is True
    assert len(players) == 1


@pytest.mark.asyncio
async def test_upsert_db_user_preserves_null_username(
    db_session: AsyncSession,
    users: SqlAlchemyDrawEntrantRepository,
    patch_sqlite_upsert: Callable[..., None],
):
    patch_sqlite_upsert(draw_entrant_repository_module)

    player = await users.upsert_active(
        DrawEntrant(
            bot_id=1,
            chat_id=10,
            user_id=101,
            username=None,
            full_name="No Username",
        )
    )
    await db_session.commit()

    result = await db_session.execute(
        select(DrawEntrantORM).where(
            DrawEntrantORM.bot_id == 1,
            DrawEntrantORM.chat_id == 10,
            DrawEntrantORM.user_id == 101,
        )
    )
    db_player = result.scalar_one()

    assert player.username is None
    assert db_player.username is None
    assert db_player.full_name == "No Username"


@pytest.mark.asyncio
async def test_upsert_db_user_updates_existing_player_and_reactivates_it(
    db_session: AsyncSession,
    users: SqlAlchemyDrawEntrantRepository,
    patch_sqlite_upsert: Callable[..., None],
):
    patch_sqlite_upsert(draw_entrant_repository_module)

    db_session.add(
        DrawEntrantORM(
            bot_id=1,
            chat_id=10,
            user_id=100,
            username="old_user",
            full_name="Old Name",
            is_active=False,
        )
    )
    await db_session.commit()

    player = await users.upsert_active(
        DrawEntrant(
            bot_id=1,
            chat_id=10,
            user_id=100,
            username="new_user",
            full_name="New Name",
        )
    )
    await db_session.commit()

    result = await db_session.execute(
        select(DrawEntrantORM).where(
            DrawEntrantORM.bot_id == 1,
            DrawEntrantORM.chat_id == 10,
            DrawEntrantORM.user_id == 100,
        )
    )
    players = result.scalars().all()

    assert player.username == "new_user"
    assert player.full_name == "New Name"
    assert player.is_active is True
    assert len(players) == 1
    assert players[0].username == "new_user"
    assert players[0].full_name == "New Name"
    assert players[0].is_active is True
