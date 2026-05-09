import asyncio
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch

import pytest

from friends_bot_service.enums.enums import GameType
from friends_bot_service.handlers.game import (
    start_game,
    start_loser_game,
    start_winner_game,
)
from friends_bot_service.texts.game_text import WINNER_MESSAGES


class DummyTypingContext:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return None


def build_message(chat_id: int = 10, user_id: int = 20) -> AsyncMock:
    """Builds a minimal aiogram message mock for handler tests."""

    # Create a mock that behaves like aiogram Message for our handlers.
    message = AsyncMock()

    # Fill only the fields that the handlers actually read.
    message.chat.id = chat_id
    message.from_user = SimpleNamespace(id=user_id)
    message.message_thread_id = None
    return message


@pytest.mark.asyncio
async def test_start_game_reports_if_already_run():
    """
    Verify the early-exit branch when today's draw already exists.

    Scenario:
    - start_game is called for a bot and chat
    - repository reports that today's result is already stored

    Expected behavior:
    - the handler sends "already chosen" message
    - player loading does not happen
    - statistics update does not happen
    """

    # Prepare a minimal message, bot and session.
    message = build_message()
    bot = SimpleNamespace(id=1)
    session = AsyncMock()

    # Simulate the repository state where today's result already exists.
    with (
        patch(
            "friends_bot_service.handlers.game.game_repo.get_game_stats",
            new=AsyncMock(return_value=object()),
        ) as get_game_stats,
        patch(
            "friends_bot_service.handlers.game.game_repo.get_players",
            new=AsyncMock(),
        ) as get_players,
        patch(
            "friends_bot_service.handlers.game.game_repo.update_game_stats",
            new=AsyncMock(),
        ) as update_game_stats,
    ):
        await start_game(message, bot, session, 1, 10, GameType.WINNER)

    # The handler must stop before loading players or writing new stats.
    get_game_stats.assert_awaited_once()
    get_players.assert_not_awaited()
    update_game_stats.assert_not_awaited()
    session.commit.assert_not_awaited()
    message.answer.assert_awaited_once_with("Сегодня выбор уже сделан!")


@pytest.mark.asyncio
async def test_start_game_reports_if_no_players():
    """
    Verify the early-exit branch when no eligible players are available.

    Scenario:
    - start_game is called for a bot and chat
    - repository reports no existing result for today
    - repository returns an empty player list

    Expected behavior:
    - the handler reports that nobody registered
    - statistics update does not happen
    - commit does not happen
    """

    # Prepare a minimal message, bot and session.
    message = build_message()
    bot = SimpleNamespace(id=1)
    session = AsyncMock()

    # Simulate the repository state where no game exists yet,
    # but no players are available.
    with (
        patch(
            "friends_bot_service.handlers.game.game_repo.get_game_stats",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "friends_bot_service.handlers.game.game_repo.get_players",
            new=AsyncMock(return_value=[]),
        ) as get_players,
        patch(
            "friends_bot_service.handlers.game.game_repo.update_game_stats",
            new=AsyncMock(),
        ) as update_game_stats,
    ):
        await start_game(message, bot, session, 1, 10, GameType.WINNER)

    # The handler must report the empty player list and stop there.
    get_players.assert_awaited_once()
    update_game_stats.assert_not_awaited()
    session.commit.assert_not_awaited()
    message.answer.assert_awaited_once_with("Никто не зарегистрировался!")


@pytest.mark.asyncio
@pytest.mark.parametrize("game_type", [GameType.WINNER, GameType.LOSER])
async def test_start_game_success_flow(game_type: GameType):
    """
    Verify the full successful start_game flow for both game types.

    Scenario:
    - there is no result for today
    - exactly one eligible player is available
    - all external effects are mocked

    Expected behavior:
    - typing action is started
    - suspense messages are sent in order
    - the final winner message is sent
    - statistics are updated and committed
    """

    # Prepare the input objects and one deterministic winner candidate.
    message = build_message()
    bot = SimpleNamespace(id=1)
    session = AsyncMock()
    player = SimpleNamespace(user_id=777, full_name="Test Name")

    # Mock all external effects so only the control flow is under test.
    with (
        patch(
            "friends_bot_service.handlers.game.game_repo.get_game_stats",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "friends_bot_service.handlers.game.game_repo.get_players",
            new=AsyncMock(return_value=[player]),
        ),
        patch(
            "friends_bot_service.handlers.game.game_repo.update_game_stats",
            new=AsyncMock(),
        ) as update_game_stats,
        patch(
            "friends_bot_service.handlers.game.ChatActionSender.typing",
            return_value=DummyTypingContext(),
        ) as typing_mock,
        patch(
            "friends_bot_service.handlers.game.random.choice",
            return_value=player,
        ),
        patch(
            "friends_bot_service.handlers.game.asyncio.sleep",
            new=AsyncMock(),
        ) as sleep_mock,
    ):
        await start_game(message, bot, session, 1, 10, game_type)

    # The handler must show typing, persist the result and commit once.
    typing_mock.assert_called_once_with(chat_id=10, bot=bot, message_thread_id=None)
    update_game_stats.assert_awaited_once_with(session, 1, 10, 777, game_type, ANY)
    session.commit.assert_awaited_once()
    assert sleep_mock.await_count == len(WINNER_MESSAGES[game_type])

    # The outgoing message sequence must match the configured suspense text exactly.
    sent_messages = [call.args[0] for call in message.answer.await_args_list]
    assert sent_messages == [
        *WINNER_MESSAGES[game_type][:-1],
        WINNER_MESSAGES[game_type][-1] + "Test Name",
    ]


@pytest.mark.asyncio
async def test_start_winner_game_rejects_unregistered_user():
    """
    Verify that start_winner_game rejects an unregistered user.

    Scenario:
    - a user sends the winner command
    - repository does not find that user in the player list

    Expected behavior:
    - the handler answers with a rejection message
    - bot activity timestamp is not touched
    - nested game logic is not started
    """

    # Prepare a command call from a user who is not in the player list.
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=30)
    session = AsyncMock()

    # Simulate "user not found" and guard against any deeper calls.
    with (
        patch(
            "friends_bot_service.handlers.game.user_repo.get_db_user",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "friends_bot_service.handlers.game.bot_repo.touch_bot_last_game_attempt",
            new=AsyncMock(),
        ) as touch_bot_last_game_attempt,
        patch(
            "friends_bot_service.handlers.game.start_game",
            new=AsyncMock(),
        ) as start_game_mock,
    ):
        await start_winner_game(message, bot, session, "upd-1")

    # The handler must answer immediately without touching bot activity or game flow.
    touch_bot_last_game_attempt.assert_not_awaited()
    start_game_mock.assert_not_awaited()
    session.commit.assert_not_awaited()
    message.answer.assert_awaited_once_with("Тебя нет в списках игроков.")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler", "game_type"),
    [
        (start_winner_game, GameType.WINNER),
        (start_loser_game, GameType.LOSER),
    ],
)
async def test_game_command_starts_game_for_registered_user(handler, game_type):
    """
    Verify that command handlers delegate to start_game for registered users.

    Scenario:
    - a registered user sends either /run or /loser
    - the user lookup succeeds

    Expected behavior:
    - bot activity timestamp is updated
    - the session is committed
    - start_game is called with the correct GameType
    """

    # Prepare a valid command call for a registered user.
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=30)
    session = AsyncMock()

    # Simulate a successful user lookup and intercept the nested start_game call.
    with (
        patch(
            "friends_bot_service.handlers.game.user_repo.get_db_user",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "friends_bot_service.handlers.game.bot_repo.touch_bot_last_game_attempt",
            new=AsyncMock(),
        ) as touch_bot_last_game_attempt,
        patch(
            "friends_bot_service.handlers.game.start_game",
            new=AsyncMock(),
        ) as start_game_mock,
    ):
        await handler(message, bot, session, "upd-1")

    # The wrapper handler must update bot activity, commit it and call start_game.
    touch_bot_last_game_attempt.assert_awaited_once_with(session, 30)
    session.commit.assert_awaited_once()
    start_game_mock.assert_awaited_once_with(message, bot, session, 30, 10, game_type)


@pytest.mark.asyncio
async def test_start_game_serializes_parallel_calls_for_same_bot_and_chat():
    """
    Verify that the in-memory lock serializes concurrent draws in one bot/chat pair.

    Scenario:
    - two start_game calls begin in parallel for the same bot and chat
    - the first call records the result and flips the shared test state
    - the second call then sees that today's result already exists

    Expected behavior:
    - repository checks happen for both calls
    - only one call loads players
    - only one call updates statistics and commits
    """

    # Prepare two concurrent calls for the same bot and chat.
    message_one = build_message(chat_id=10, user_id=20)
    message_two = build_message(chat_id=10, user_id=21)
    bot = SimpleNamespace(id=1)
    session = AsyncMock()
    player = SimpleNamespace(user_id=777, full_name="Winner")
    state = {"has_stats": False}

    # Before the first update there are no stats; after it, the draw is considered done.
    async def fake_get_game_stats(*args, **kwargs):
        return object() if state["has_stats"] else None

    async def fake_get_players(*args, **kwargs):
        return [player]

    async def fake_update_game_stats(*args, **kwargs):
        state["has_stats"] = True

    # Run both calls concurrently with all external side effects mocked.
    with (
        patch(
            "friends_bot_service.handlers.game.game_repo.get_game_stats",
            new=AsyncMock(side_effect=fake_get_game_stats),
        ) as get_game_stats,
        patch(
            "friends_bot_service.handlers.game.game_repo.get_players",
            new=AsyncMock(side_effect=fake_get_players),
        ) as get_players,
        patch(
            "friends_bot_service.handlers.game.game_repo.update_game_stats",
            new=AsyncMock(side_effect=fake_update_game_stats),
        ) as update_game_stats,
        patch(
            "friends_bot_service.handlers.game.ChatActionSender.typing",
            return_value=DummyTypingContext(),
        ),
        patch(
            "friends_bot_service.handlers.game.random.choice",
            return_value=player,
        ),
        patch(
            "friends_bot_service.handlers.game.asyncio.sleep",
            new=AsyncMock(),
        ),
    ):
        await asyncio.gather(
            start_game(message_one, bot, session, 1, 10, GameType.WINNER),
            start_game(message_two, bot, session, 1, 10, GameType.WINNER),
        )

    # Only one call should reach player loading, stats update and commit.
    assert get_game_stats.await_count == 2
    assert get_players.await_count == 1
    assert update_game_stats.await_count == 1
    assert session.commit.await_count == 1
