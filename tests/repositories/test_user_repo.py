from collections.abc import Callable

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.models.game_models import Player
from friends_bot_service.repositories import user_repo


@pytest.mark.asyncio
async def test_get_db_user_returns_matching_player_and_none_for_missing(
    db_session: AsyncSession,
):
    """
    Verify direct player lookup by full repository key.

    Scenario:
    - one player exists in the database
    - the repository is queried once with the exact key
    - the repository is queried once with a missing key

    Expected behavior:
    - the matching player is returned for the exact key
    - None is returned for the missing key
    """

    # Create one player row that can be looked up by bot, chat and user.
    db_session.add(Player(bot_id=1, chat_id=10, user_id=100, full_name="Lookup User"))
    await db_session.commit()

    # Query the repository with a matching key and a missing key.
    existing_player = await user_repo.get_db_user(db_session, 1, 10, 100)
    missing_player = await user_repo.get_db_user(db_session, 1, 10, 999)

    # The exact key must resolve to the row, while the missing key must return None.
    assert existing_player is not None
    assert existing_player.user_id == 100
    assert missing_player is None


@pytest.mark.asyncio
async def test_list_active_players_for_chat_scopes_bot_chat_and_skips_inactive(
    db_session: AsyncSession,
):
    """
    Verify roster listing scopes to bot and chat and omits inactive players.
    """

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

    roster = await user_repo.list_active_players_for_chat(db_session, 1, 10)
    user_ids = [p.user_id for p in roster]

    assert user_ids == [1]


@pytest.mark.asyncio
async def test_upsert_db_user_creates_new_player(
    db_session: AsyncSession,
    patch_sqlite_upsert: Callable[..., None],
):
    """
    Verify player upsert for a new user.

    Scenario:
    - user_repo.upsert_db_user is called for a player that does not exist yet
    - test patches repo-local INSERT to SQLite dialect

    Expected behavior:
    - a new player row is created
    - returned object contains the inserted values
    - exactly one matching row exists in the database
    """

    # Switch this repository test to SQLite-compatible INSERT .. ON CONFLICT.
    patch_sqlite_upsert(user_repo)

    # Upsert a brand new player.
    player = await user_repo.upsert_db_user(
        db_session,
        bot_id=1,
        chat_id=10,
        user_id=100,
        username="first_user",
        full_name="First User",
    )
    await db_session.commit()

    # Load matching rows directly to verify the persisted state.
    result = await db_session.execute(
        select(Player).where(
            Player.bot_id == 1,
            Player.chat_id == 10,
            Player.user_id == 100,
        )
    )
    players = result.scalars().all()

    # The upsert must create one active row with the expected data.
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
    patch_sqlite_upsert: Callable[..., None],
):
    """
    Verify player upsert when username is missing.

    Scenario:
    - user_repo.upsert_db_user is called with username=None
    - test patches repo-local INSERT to SQLite dialect

    Expected behavior:
    - the row is inserted successfully
    - username stays NULL in the returned object and in the database
    """

    # Switch this repository test to SQLite-compatible INSERT .. ON CONFLICT.
    patch_sqlite_upsert(user_repo)

    # Upsert a player who has no Telegram username.
    player = await user_repo.upsert_db_user(
        db_session,
        bot_id=1,
        chat_id=10,
        user_id=101,
        username=None,
        full_name="No Username",
    )
    await db_session.commit()

    # Load the row directly to verify that NULL username was preserved.
    result = await db_session.execute(
        select(Player).where(
            Player.bot_id == 1,
            Player.chat_id == 10,
            Player.user_id == 101,
        )
    )
    db_player = result.scalar_one()

    # Both returned and persisted objects must keep username as None.
    assert player.username is None
    assert db_player.username is None
    assert db_player.full_name == "No Username"


@pytest.mark.asyncio
async def test_upsert_db_user_updates_existing_player_and_reactivates_it(
    db_session: AsyncSession,
    patch_sqlite_upsert: Callable[..., None],
):
    """
    Verify player upsert for an existing inactive user.

    Scenario:
    - a player row already exists with old profile data
    - that row is inactive
    - user_repo.upsert_db_user is called again with new values

    Expected behavior:
    - the existing row is updated instead of duplicated
    - username and full_name are refreshed
    - is_active becomes True again
    """

    # Switch this repository test to SQLite-compatible INSERT .. ON CONFLICT.
    patch_sqlite_upsert(user_repo)

    # Create an inactive player row that should be updated by the upsert.
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

    # Upsert the same player with fresh profile data.
    player = await user_repo.upsert_db_user(
        db_session,
        bot_id=1,
        chat_id=10,
        user_id=100,
        username="new_user",
        full_name="New Name",
    )
    await db_session.commit()

    # Load matching rows directly to verify the persisted state.
    result = await db_session.execute(
        select(Player).where(
            Player.bot_id == 1,
            Player.chat_id == 10,
            Player.user_id == 100,
        )
    )
    players = result.scalars().all()

    # The upsert must reuse the row, reactivate it and refresh profile data.
    assert player.username == "new_user"
    assert player.full_name == "New Name"
    assert player.is_active is True
    assert len(players) == 1
    assert players[0].username == "new_user"
    assert players[0].full_name == "New Name"
    assert players[0].is_active is True
