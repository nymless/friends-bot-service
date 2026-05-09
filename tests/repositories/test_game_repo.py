from collections.abc import Callable
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from friends_bot_service.enums.enums import GameType
from friends_bot_service.models.game_models import GameStats, Player
from friends_bot_service.repositories import game_repo


@pytest.mark.asyncio
async def test_get_game_stats_returns_today_result_for_requested_game_type(
    db_session: AsyncSession,
):
    """
    Verify repository filtering by game type for today's stats.

    Scenario:
    - a WINNER stats for today exists in the database
    - the repository is queried once for WINNER and once for LOSER

    Expected behavior:
    - WINNER query returns the stored row
    - LOSER query returns nothing
    """

    # Prepare a single winner result for today.
    today = date.today()
    db_session.add(
        GameStats(bot_id=1, chat_id=10, user_id=100, win_count=1, last_win=today)
    )
    await db_session.commit()

    # Query the repository for both game types on the same day.
    winner_stats = await game_repo.get_game_stats(
        db_session, 1, 10, GameType.WINNER, today
    )
    loser_stats = await game_repo.get_game_stats(
        db_session, 1, 10, GameType.LOSER, today
    )

    # Winner stats should be found, loser stats should stay empty.
    assert winner_stats is not None
    assert winner_stats.user_id == 100
    assert loser_stats is None


@pytest.mark.asyncio
async def test_get_players_excludes_users_with_today_result(
    db_session: AsyncSession,
):
    """
    Verify that players with today's result are excluded from the candidate list.

    Scenario:
    - two players are active in the same bot and chat
    - one of them already has a winner result for today

    Expected behavior:
    - only the player without today's result is returned
    """

    # Create two players and mark one of them as already used today.
    today = date.today()
    db_session.add_all(
        [
            Player(bot_id=1, chat_id=10, user_id=100, full_name="User 100"),
            Player(bot_id=1, chat_id=10, user_id=200, full_name="User 200"),
            GameStats(bot_id=1, chat_id=10, user_id=200, win_count=1, last_win=today),
        ]
    )
    await db_session.commit()

    # Ask the repository for eligible players for today's draw.
    players = await game_repo.get_players(db_session, 1, 10, today)

    # Only the player without a result today should remain.
    assert [player.user_id for player in players] == [100]


@pytest.mark.asyncio
async def test_get_players_isolated_by_chat(db_session: AsyncSession):
    """
    Verify that player availability is isolated by chat.

    Scenario:
    - the same user exists in two different chats
    - only one of those chats has a result for today

    Expected behavior:
    - the user is excluded only in the affected chat
    - the other chat still sees the user as eligible
    """

    # Put the same user into two chats.
    today = date.today()
    db_session.add_all(
        [
            Player(bot_id=1, chat_id=10, user_id=777, full_name="Shared User"),
            Player(bot_id=1, chat_id=20, user_id=777, full_name="Shared User"),
            GameStats(bot_id=1, chat_id=10, user_id=777, lose_count=1, last_lose=today),
        ]
    )
    await db_session.commit()

    # Request eligible players separately for each chat.
    chat_one_players = await game_repo.get_players(db_session, 1, 10, today)
    chat_two_players = await game_repo.get_players(db_session, 1, 20, today)

    # The user must be excluded only from the chat where today's result exists.
    assert chat_one_players == []
    assert [player.user_id for player in chat_two_players] == [777]


@pytest.mark.asyncio
async def test_get_players_isolated_by_bot(db_session: AsyncSession):
    """
    Verify that player availability is isolated by bot.

    Scenario:
    - the same user exists under two different bots in the same chat
    - only one of those bots has a result for today

    Expected behavior:
    - the user is excluded only for the affected bot
    - the other bot still sees the user as eligible
    """

    # Put the same user under two bots in the same chat.
    today = date.today()
    db_session.add_all(
        [
            Player(bot_id=1, chat_id=10, user_id=777, full_name="Shared User"),
            Player(bot_id=2, chat_id=10, user_id=777, full_name="Shared User"),
            GameStats(bot_id=1, chat_id=10, user_id=777, lose_count=1, last_lose=today),
        ]
    )
    await db_session.commit()

    # Request eligible players separately for each bot.
    bot_one_players = await game_repo.get_players(db_session, 1, 10, today)
    bot_two_players = await game_repo.get_players(db_session, 2, 10, today)

    # The user must be excluded only for the bot where today's result exists.
    assert bot_one_players == []
    assert [player.user_id for player in bot_two_players] == [777]


@pytest.mark.asyncio
async def test_get_players_excludes_inactive_players(db_session: AsyncSession):
    """
    Verify that inactive players are excluded from the candidate list.

    Scenario:
    - two players exist in the same bot and chat
    - one player is active
    - the other player is inactive
    - neither player has a result for today

    Expected behavior:
    - only the active player is returned
    - the inactive player does not participate in the draw
    """

    # Create one active and one inactive player for the same bot and chat.
    today = date.today()
    db_session.add_all(
        [
            Player(bot_id=1, chat_id=10, user_id=100, full_name="Active User"),
            Player(
                bot_id=1,
                chat_id=10,
                user_id=200,
                full_name="Inactive User",
                is_active=False,
            ),
        ]
    )
    await db_session.commit()

    # Ask the repository for eligible players for today's draw.
    players = await game_repo.get_players(db_session, 1, 10, today)

    # Only the active player should be returned.
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
    patch_sqlite_upsert: Callable[..., None],
    game_type: GameType,
    count_attr: str,
    date_attr: str,
    other_count_attr: str,
    other_date_attr: str,
):
    """
    Verify atomic stats upsert for both winner and loser modes.

    Scenario:
    - update_game_stats is called twice for the same bot, chat and user
    - test patches repo-local INSERT to SQLite dialect
    - each call uses the same game type

    Expected behavior:
    - the first call creates the stats row
    - the second call increments the matching counter
    - unrelated counter and date fields stay untouched
    """

    # Switch this repository test to SQLite-compatible INSERT .. ON CONFLICT.
    patch_sqlite_upsert(game_repo)

    # Apply the same stats update twice for the same player.
    today = date.today()
    await game_repo.update_game_stats(db_session, 1, 10, 100, game_type, today)
    await game_repo.update_game_stats(db_session, 1, 10, 100, game_type, today)
    await db_session.commit()

    # Load the persisted stats row directly from the database.
    result = await db_session.execute(
        select(GameStats).where(
            GameStats.bot_id == 1,
            GameStats.chat_id == 10,
            GameStats.user_id == 100,
        )
    )
    stats = result.scalar_one()

    # The selected counter must be incremented twice,
    # while the opposite branch stays intact.
    assert getattr(stats, count_attr) == 2
    assert getattr(stats, date_attr) == today
    assert getattr(stats, other_count_attr) == 0
    assert getattr(stats, other_date_attr) is None


@pytest.mark.asyncio
async def test_unique_winner_constraint_prevents_two_winners_same_day(
    db_session: AsyncSession,
):
    """
    Verify UNIQUE INDEX constraint:
    there cannot be two winners for the same bot and chat on the same day.

    Scenario:
    - one winner for today is already stored
    - a second winner for the same bot, chat and day is inserted

    Expected behavior:
    - the second INSERT fails with IntegrityError
    """

    # Insert the first winner for the day.
    today = date.today()
    db_session.add(
        GameStats(bot_id=123, chat_id=456, user_id=1, last_win=today, win_count=1)
    )
    await db_session.commit()

    # Try to insert a second winner for the same bot, chat and day.
    db_session.add(
        GameStats(bot_id=123, chat_id=456, user_id=2, last_win=today, win_count=1)
    )

    # The database constraint must reject this commit.
    with pytest.raises(IntegrityError):
        await db_session.commit()
