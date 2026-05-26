from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.infra.models.bot_models import RegisteredBot
from friends_bot_service.infra.repositories.sqlalchemy import (
    bot_repository as bot_repository_module,
)
from friends_bot_service.infra.repositories.sqlalchemy.bot_repository import (
    SqlAlchemyBotRepository,
)


@pytest.fixture
def bots(db_session: AsyncSession) -> SqlAlchemyBotRepository:
    return SqlAlchemyBotRepository(db_session)


@pytest.mark.asyncio
async def test_upsert_bot_creates_new_registered_bot(
    db_session: AsyncSession,
    bots: SqlAlchemyBotRepository,
    patch_sqlite_upsert: Callable[..., None],
):
    """
    Verify bot upsert for a new bot.

    Scenario:
    - bots.upsert is called for a bot that does not exist yet
    - test patches repo-local INSERT to SQLite dialect

    Expected behavior:
    - a new bot row is created
    - returned object contains the inserted values
    - exactly one matching row exists in the database
    """

    patch_sqlite_upsert(bot_repository_module)

    bot = await bots.upsert(
        bot_id=999,
        username="first_bot",
        encrypted_token="token-1",
        owner_id=777,
    )
    await db_session.commit()

    result = await db_session.execute(
        select(RegisteredBot).where(RegisteredBot.bot_id == 999)
    )
    db_bots = result.scalars().all()

    assert bot.bot_id == 999
    assert bot.username == "first_bot"
    assert bot.encrypted_token == "token-1"
    assert bot.owner_id == 777
    assert bot.is_active is True
    assert len(db_bots) == 1


@pytest.mark.asyncio
async def test_deactivate_bot_for_owner_deactivates_matching_bot(
    db_session: AsyncSession,
    bots: SqlAlchemyBotRepository,
):
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

    deactivated = await bots.deactivate_for_owner(999, 777)
    await db_session.commit()

    result = await db_session.execute(
        select(RegisteredBot).where(RegisteredBot.bot_id == 999)
    )
    bot = result.scalar_one()

    assert deactivated is True
    assert bot.is_active is False


@pytest.mark.asyncio
async def test_deactivate_bot_for_owner_returns_false_for_wrong_owner(
    db_session: AsyncSession,
    bots: SqlAlchemyBotRepository,
):
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

    deactivated = await bots.deactivate_for_owner(999, 555)
    await db_session.commit()

    result = await db_session.execute(
        select(RegisteredBot).where(RegisteredBot.bot_id == 999)
    )
    bot = result.scalar_one()

    assert deactivated is False
    assert bot.is_active is True


@pytest.mark.asyncio
async def test_upsert_bot_updates_existing_bot_and_reactivates_it(
    db_session: AsyncSession,
    bots: SqlAlchemyBotRepository,
    patch_sqlite_upsert: Callable[..., None],
):
    patch_sqlite_upsert(bot_repository_module)

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

    bot = await bots.upsert(
        bot_id=999,
        username="new_bot",
        encrypted_token="new-token",
        owner_id=777,
    )
    await db_session.commit()

    result = await db_session.execute(
        select(RegisteredBot).where(RegisteredBot.bot_id == 999)
    )
    db_bots = result.scalars().all()

    assert bot.username == "new_bot"
    assert bot.encrypted_token == "new-token"
    assert bot.owner_id == 777
    assert bot.is_active is True
    assert len(db_bots) == 1
    assert db_bots[0].username == "new_bot"
    assert db_bots[0].encrypted_token == "new-token"
    assert db_bots[0].owner_id == 777
    assert db_bots[0].is_active is True


@pytest.mark.asyncio
async def test_touch_bot_last_game_attempt_updates_timestamp(
    db_session: AsyncSession,
    bots: SqlAlchemyBotRepository,
):
    db_session.add(
        RegisteredBot(
            bot_id=999,
            username="activity_bot",
            encrypted_token="token-1",
            owner_id=777,
        )
    )
    await db_session.commit()

    await bots.touch_last_game_attempt(999)
    await db_session.commit()

    result = await db_session.execute(
        select(RegisteredBot).where(RegisteredBot.bot_id == 999)
    )
    bot = result.scalar_one()

    assert bot.last_game_attempt_at is not None


@pytest.mark.asyncio
async def test_deactivate_stale_bots_uses_last_attempt_or_created_at(
    db_session: AsyncSession,
    bots: SqlAlchemyBotRepository,
):
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

    deactivated = await bots.deactivate_stale(cutoff)
    await db_session.commit()

    result = await db_session.execute(select(RegisteredBot))
    db_bots = {bot.bot_id: bot for bot in result.scalars().all()}

    assert set(deactivated) == {
        (1, "stale_by_created"),
        (2, "stale_by_attempt"),
    }
    assert db_bots[1].is_active is False
    assert db_bots[2].is_active is False
    assert db_bots[3].is_active is True
    assert db_bots[4].is_active is False


@pytest.mark.asyncio
async def test_get_active_bots_for_owner_returns_only_active_owned_bots(
    db_session: AsyncSession,
    bots: SqlAlchemyBotRepository,
):
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

    active_bots = await bots.list_active_for_owner(100)

    assert {bot.bot_id for bot in active_bots} == {1}
    assert all(bot.owner_id == 100 for bot in active_bots)
    assert all(bot.is_active for bot in active_bots)


@pytest.mark.asyncio
async def test_get_active_bot_for_owner_returns_only_matching_active_bot(
    db_session: AsyncSession,
    bots: SqlAlchemyBotRepository,
):
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

    matching_bot = await bots.get_active_for_owner(100, 1)
    inactive_bot = await bots.get_active_for_owner(100, 2)
    foreign_bot = await bots.get_active_for_owner(100, 3)

    assert matching_bot is not None
    assert matching_bot.bot_id == 1
    assert inactive_bot is None
    assert foreign_bot is None
