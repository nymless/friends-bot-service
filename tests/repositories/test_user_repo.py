from collections.abc import Callable

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.domain import PlayerKey
from friends_bot_service.models.game_models import Player
from friends_bot_service.repositories.sqlalchemy import (
    user_repository as user_repository_module,
)
from friends_bot_service.repositories.sqlalchemy.user_repository import (
    SqlAlchemyUserRepository,
)


@pytest.fixture
def users(db_session: AsyncSession) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(db_session)


@pytest.mark.asyncio
async def test_get_db_user_returns_matching_player_and_none_for_missing(
    db_session: AsyncSession,
    users: SqlAlchemyUserRepository,
):
    db_session.add(Player(bot_id=1, chat_id=10, user_id=100, full_name="Lookup User"))
    await db_session.commit()

    existing_player = await users.get(PlayerKey(1, 10, 100))
    missing_player = await users.get(PlayerKey(1, 10, 999))

    assert existing_player is not None
    assert existing_player.user_id == 100
    assert missing_player is None


@pytest.mark.asyncio
async def test_list_active_players_for_chat_scopes_bot_chat_and_skips_inactive(
    db_session: AsyncSession,
    users: SqlAlchemyUserRepository,
):
    db_session.add_all(
        [
            Player(
                bot_id=1,
                chat_id=10,
                user_id=1,
                username="one",
                full_name="Active One",
                is_active=True,
            ),
            Player(
                bot_id=1,
                chat_id=10,
                user_id=2,
                username="two",
                full_name="Inactive",
                is_active=False,
            ),
            Player(
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
    users: SqlAlchemyUserRepository,
    patch_sqlite_upsert: Callable[..., None],
):
    patch_sqlite_upsert(user_repository_module)

    player = await users.upsert_active(
        bot_id=1,
        chat_id=10,
        user_id=100,
        username="first_user",
        full_name="First User",
    )
    await db_session.commit()

    result = await db_session.execute(
        select(Player).where(
            Player.bot_id == 1,
            Player.chat_id == 10,
            Player.user_id == 100,
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
    users: SqlAlchemyUserRepository,
    patch_sqlite_upsert: Callable[..., None],
):
    patch_sqlite_upsert(user_repository_module)

    player = await users.upsert_active(
        bot_id=1,
        chat_id=10,
        user_id=101,
        username=None,
        full_name="No Username",
    )
    await db_session.commit()

    result = await db_session.execute(
        select(Player).where(
            Player.bot_id == 1,
            Player.chat_id == 10,
            Player.user_id == 101,
        )
    )
    db_player = result.scalar_one()

    assert player.username is None
    assert db_player.username is None
    assert db_player.full_name == "No Username"


@pytest.mark.asyncio
async def test_upsert_db_user_updates_existing_player_and_reactivates_it(
    db_session: AsyncSession,
    users: SqlAlchemyUserRepository,
    patch_sqlite_upsert: Callable[..., None],
):
    patch_sqlite_upsert(user_repository_module)

    db_session.add(
        Player(
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
        bot_id=1,
        chat_id=10,
        user_id=100,
        username="new_user",
        full_name="New Name",
    )
    await db_session.commit()

    result = await db_session.execute(
        select(Player).where(
            Player.bot_id == 1,
            Player.chat_id == 10,
            Player.user_id == 100,
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
