from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.models.bot_models import RegisteredBot
from friends_bot_service.repositories import bot_repo


@pytest.mark.asyncio
async def test_upsert_bot_creates_new_registered_bot(
    db_session: AsyncSession,
    patch_sqlite_upsert: Callable[..., None],
):
    """
    Verify bot upsert for a new bot.

    Scenario:
    - bot_repo.upsert_bot is called for a bot that does not exist yet
    - test patches repo-local INSERT to SQLite dialect

    Expected behavior:
    - a new bot row is created
    - returned object contains the inserted values
    - exactly one matching row exists in the database
    """

    # Switch this repository test to SQLite-compatible INSERT .. ON CONFLICT.
    patch_sqlite_upsert(bot_repo)

    # Upsert a brand new registered bot.
    bot = await bot_repo.upsert_bot(
        db_session,
        bot_id=999,
        username="first_bot",
        encrypted_token="token-1",
        owner_id=777,
    )
    await db_session.commit()

    # Load matching rows directly to verify the persisted state.
    result = await db_session.execute(
        select(RegisteredBot).where(RegisteredBot.bot_id == 999)
    )
    bots = result.scalars().all()

    # The upsert must create one active row with the expected data.
    assert bot.bot_id == 999
    assert bot.username == "first_bot"
    assert bot.encrypted_token == "token-1"
    assert bot.owner_id == 777
    assert bot.is_active is True
    assert len(bots) == 1


@pytest.mark.asyncio
async def test_deactivate_bot_for_owner_deactivates_matching_bot(
    db_session: AsyncSession,
):
    """
    Verify bot deactivation for the correct owner.

    Scenario:
    - one active bot exists in the database
    - deactivate_bot_for_owner is called with the matching owner_id

    Expected behavior:
    - the method returns True
    - the bot becomes inactive in the database
    """

    # Create one active bot owned by the caller.
    db_session.add(
        RegisteredBot(
            bot_id=999,
            username="owned_bot",
            encrypted_token="token-1",
            owner_id=777,
            is_active=True,
        )
    )
    await db_session.commit()

    # Deactivate the bot using the correct owner id.
    deactivated = await bot_repo.deactivate_bot_for_owner(db_session, 999, 777)
    await db_session.commit()

    # Load the row directly to verify the new state.
    result = await db_session.execute(
        select(RegisteredBot).where(RegisteredBot.bot_id == 999)
    )
    bot = result.scalar_one()

    # The method must succeed and persist the inactive flag.
    assert deactivated is True
    assert bot.is_active is False


@pytest.mark.asyncio
async def test_deactivate_bot_for_owner_returns_false_for_wrong_owner(
    db_session: AsyncSession,
):
    """
    Verify that bot deactivation is blocked for a different owner.

    Scenario:
    - one active bot exists in the database
    - deactivate_bot_for_owner is called with a non-matching owner_id

    Expected behavior:
    - the method returns False
    - the bot stays active in the database
    """

    # Create one active bot with a different owner.
    db_session.add(
        RegisteredBot(
            bot_id=999,
            username="owned_bot",
            encrypted_token="token-1",
            owner_id=777,
            is_active=True,
        )
    )
    await db_session.commit()

    # Try to deactivate the bot using the wrong owner id.
    deactivated = await bot_repo.deactivate_bot_for_owner(db_session, 999, 555)
    await db_session.commit()

    # Load the row directly to verify that nothing changed.
    result = await db_session.execute(
        select(RegisteredBot).where(RegisteredBot.bot_id == 999)
    )
    bot = result.scalar_one()

    # The method must report failure and keep the bot active.
    assert deactivated is False
    assert bot.is_active is True


@pytest.mark.asyncio
async def test_upsert_bot_updates_existing_bot_and_reactivates_it(
    db_session: AsyncSession,
    patch_sqlite_upsert: Callable[..., None],
):
    """
    Verify bot upsert for an existing inactive bot.

    Scenario:
    - a bot row already exists with old public data and token
    - that row is inactive
    - bot_repo.upsert_bot is called again with new values

    Expected behavior:
    - the existing row is updated instead of duplicated
    - username and encrypted token are refreshed
    - is_active becomes True again
    """

    # Switch this repository test to SQLite-compatible INSERT .. ON CONFLICT.
    patch_sqlite_upsert(bot_repo)

    # Create an inactive bot row that should be updated by the upsert.
    db_session.add(
        RegisteredBot(
            bot_id=999,
            username="old_bot",
            encrypted_token="old-token",
            owner_id=777,
            is_active=False,
        )
    )
    await db_session.commit()

    # Upsert the same bot with fresh username and token.
    bot = await bot_repo.upsert_bot(
        db_session,
        bot_id=999,
        username="new_bot",
        encrypted_token="new-token",
        owner_id=777,
    )
    await db_session.commit()

    # Load matching rows directly to verify the persisted state.
    result = await db_session.execute(
        select(RegisteredBot).where(RegisteredBot.bot_id == 999)
    )
    bots = result.scalars().all()

    # The upsert must reuse the row, reactivate it and refresh bot data.
    assert bot.username == "new_bot"
    assert bot.encrypted_token == "new-token"
    assert bot.owner_id == 777
    assert bot.is_active is True
    assert len(bots) == 1
    assert bots[0].username == "new_bot"
    assert bots[0].encrypted_token == "new-token"
    assert bots[0].owner_id == 777
    assert bots[0].is_active is True


@pytest.mark.asyncio
async def test_touch_bot_last_game_attempt_updates_timestamp(db_session: AsyncSession):
    """
    Verify that bot activity timestamp is updated after a game attempt.

    Scenario:
    - one bot exists with last_game_attempt_at unset
    - touch_bot_last_game_attempt is called for that bot

    Expected behavior:
    - last_game_attempt_at becomes non-null
    """

    # Create one bot with no recorded game activity yet.
    db_session.add(
        RegisteredBot(
            bot_id=999,
            username="activity_bot",
            encrypted_token="token-1",
            owner_id=777,
        )
    )
    await db_session.commit()

    # Update the bot's last game attempt timestamp.
    await bot_repo.touch_bot_last_game_attempt(db_session, 999)
    await db_session.commit()

    # Load the row directly to verify the activity timestamp.
    result = await db_session.execute(
        select(RegisteredBot).where(RegisteredBot.bot_id == 999)
    )
    bot = result.scalar_one()

    # The timestamp must be filled after the touch operation.
    assert bot.last_game_attempt_at is not None


@pytest.mark.asyncio
async def test_deactivate_stale_bots_uses_last_attempt_or_created_at(
    db_session: AsyncSession,
):
    """
    Verify stale bot deactivation based on activity timestamp fallback rules.

    Scenario:
    - one bot is stale by created_at because it has no last_game_attempt_at
    - one bot is stale by last_game_attempt_at
    - one bot is still fresh because its last_game_attempt_at is recent
    - one bot is already inactive

    Expected behavior:
    - only the two active stale bots are deactivated
    - returned tuples contain only those deactivated bots
    """

    # Prepare bots covering all stale/fresh combinations used by the query.
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=60)
    db_session.add_all(
        [
            RegisteredBot(
                bot_id=1,
                username="stale_by_created",
                encrypted_token="token-1",
                owner_id=100,
                created_at=cutoff - timedelta(days=1),
                updated_at=cutoff - timedelta(days=1),
                is_active=True,
            ),
            RegisteredBot(
                bot_id=2,
                username="stale_by_attempt",
                encrypted_token="token-2",
                owner_id=100,
                created_at=now,
                updated_at=now,
                last_game_attempt_at=cutoff - timedelta(days=1),
                is_active=True,
            ),
            RegisteredBot(
                bot_id=3,
                username="fresh_by_attempt",
                encrypted_token="token-3",
                owner_id=100,
                created_at=cutoff - timedelta(days=90),
                updated_at=cutoff - timedelta(days=90),
                last_game_attempt_at=now,
                is_active=True,
            ),
            RegisteredBot(
                bot_id=4,
                username="already_inactive",
                encrypted_token="token-4",
                owner_id=100,
                created_at=cutoff - timedelta(days=90),
                updated_at=cutoff - timedelta(days=90),
                is_active=False,
            ),
        ]
    )
    await db_session.commit()

    # Run the stale bot cleanup query.
    deactivated = await bot_repo.deactivate_stale_bots(db_session, cutoff)
    await db_session.commit()

    # Load all bots back to verify their final active flags.
    result = await db_session.execute(select(RegisteredBot))
    bots = {bot.bot_id: bot for bot in result.scalars().all()}

    # Only active stale bots must be returned and deactivated.
    assert set(deactivated) == {
        (1, "stale_by_created"),
        (2, "stale_by_attempt"),
    }
    assert bots[1].is_active is False
    assert bots[2].is_active is False
    assert bots[3].is_active is True
    assert bots[4].is_active is False


@pytest.mark.asyncio
async def test_get_active_bots_for_owner_returns_only_active_owned_bots(
    db_session: AsyncSession,
):
    """
    Verify active bot listing for a specific owner.

    Scenario:
    - one owner has both active and inactive bots
    - another owner has an active bot

    Expected behavior:
    - only active bots of the requested owner are returned
    """

    # Create active and inactive bots for multiple owners.
    db_session.add_all(
        [
            RegisteredBot(
                bot_id=1,
                username="active_owned",
                encrypted_token="token-1",
                owner_id=100,
                is_active=True,
            ),
            RegisteredBot(
                bot_id=2,
                username="inactive_owned",
                encrypted_token="token-2",
                owner_id=100,
                is_active=False,
            ),
            RegisteredBot(
                bot_id=3,
                username="active_other_owner",
                encrypted_token="token-3",
                owner_id=200,
                is_active=True,
            ),
        ]
    )
    await db_session.commit()

    # Load active bots for the selected owner.
    bots = await bot_repo.get_active_bots_for_owner(db_session, 100)

    # The result must include only the active bot belonging to that owner.
    assert {bot.bot_id for bot in bots} == {1}
    assert all(bot.owner_id == 100 for bot in bots)
    assert all(bot.is_active for bot in bots)


@pytest.mark.asyncio
async def test_get_active_bot_for_owner_returns_only_matching_active_bot(
    db_session: AsyncSession,
):
    """
    Verify single active bot lookup for a specific owner.

    Scenario:
    - one active matching bot exists
    - one inactive bot exists for the same owner
    - one active bot exists for another owner

    Expected behavior:
    - the matching active bot is returned
    - inactive or foreign-owner bots return None
    """

    # Create bots covering matching, inactive and foreign-owner cases.
    db_session.add_all(
        [
            RegisteredBot(
                bot_id=1,
                username="active_owned",
                encrypted_token="token-1",
                owner_id=100,
                is_active=True,
            ),
            RegisteredBot(
                bot_id=2,
                username="inactive_owned",
                encrypted_token="token-2",
                owner_id=100,
                is_active=False,
            ),
            RegisteredBot(
                bot_id=3,
                username="active_other_owner",
                encrypted_token="token-3",
                owner_id=200,
                is_active=True,
            ),
        ]
    )
    await db_session.commit()

    # Query the repository for matching, inactive and wrong-owner cases.
    matching_bot = await bot_repo.get_active_bot_for_owner(db_session, 100, 1)
    inactive_bot = await bot_repo.get_active_bot_for_owner(db_session, 100, 2)
    foreign_bot = await bot_repo.get_active_bot_for_owner(db_session, 100, 3)

    # Only the matching active bot must be returned.
    assert matching_bot is not None
    assert matching_bot.bot_id == 1
    assert inactive_bot is None
    assert foreign_bot is None
