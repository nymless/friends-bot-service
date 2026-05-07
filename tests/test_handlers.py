import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from friends_bot_service.database import DBHandler
from friends_bot_service.enums import GameType
from friends_bot_service.handlers import start_game, start_loser_game, start_winner_game


@pytest.fixture(autouse=True)
def clear_locks():
    """
    Clears the global lock dictionary before each test.

    Why it matters:
    chat_locks is a global state.
    Without clearing, one test could affect another
    (e.g., a lock might already be captured or created).
    """
    from friends_bot_service.handlers import chat_locks

    chat_locks.clear()


@pytest.mark.asyncio
async def test_start_game_already_run():
    """
    Verify scenario where the game has already been played today.

    Expected behavior:
    - bot does not start the game
    - notifies the user immediately
    - does not request the player list
    """

    message = AsyncMock()
    db = MagicMock(spec=DBHandler)

    # Simulate DB state:
    # winner already exists (returns user_id)
    db.is_already_runned.return_value = (12345,)

    await start_game(chat_id=1, game_type=GameType.LOSER, message=message, db=db)

    # Check that the bot correctly reported this
    message.answer.assert_called_with("Сегодня выбор уже сделан!")

    # Important: further logic should not execute
    db.get_players.assert_not_called()


@pytest.mark.asyncio
async def test_start_game_no_players():
    """
    Verify scenario where there are no registered players.

    Expected behavior:
    - game does not start
    - bot reports that there are no players
    """

    message = AsyncMock()
    db = MagicMock(spec=DBHandler)

    # Game hasn't run yet
    db.is_already_runned.return_value = None

    # But there are no players
    db.get_players.return_value = []

    await start_game(chat_id=1, game_type=GameType.LOSER, message=message, db=db)

    # Check correct response
    message.answer.assert_called_with("Никто не зарегистрировался!")


@pytest.mark.asyncio
async def test_start_loser_game_success_flow():
    """
    Verify full successful game scenario (loser).

    Scenario:
    - game hasn't run yet
    - at least one player exists
    - bot performs "animation" (sequence of messages)
    - then records the result

    Verify:
    - message count
    - final message content
    - result recorded in DB
    """

    message = AsyncMock()
    db = MagicMock(spec=DBHandler)

    db.is_already_runned.return_value = None

    # One player - guaranteed to be chosen
    db.get_players.return_value = [(999, "Test Name")]

    await start_game(chat_id=1, game_type=GameType.LOSER, message=message, db=db)

    # Check that the full sequence of messages was sent
    assert message.answer.call_count == 7

    # Collect sent messages
    sent_messages = [call.args[0] for call in message.answer.call_args_list]

    # Check final string
    assert "🎉 Сегодня ПИДОР 🌈 дня -  Test Name" in sent_messages[-1]

    # Check result recording
    db.set_winner.assert_called_once_with(1, 999, GameType.LOSER)


@pytest.mark.asyncio
async def test_start_winner_game_success_flow():
    """
    Verify full successful game scenario (winner).

    Difference from previous test:
    - different game type
    - different final message text

    Otherwise the scenario is identical:
    verifying the correctness of the entire chain of actions
    """

    message = AsyncMock()
    db = MagicMock(spec=DBHandler)

    db.is_already_runned.return_value = None

    # Two players (selection is random, but only text matters to us)
    db.get_players.return_value = [(999, "Test Name"), (999, "Test Name")]

    await start_game(chat_id=1, game_type=GameType.WINNER, message=message, db=db)

    # Check message count
    assert message.answer.call_count == 7

    # Collect sent messages
    sent_messages = [call.args[0] for call in message.answer.call_args_list]

    # Check final message
    assert "🎉 Сегодня красавчик дня -  Test Name" in sent_messages[-1]

    # Check result recording
    db.set_winner.assert_called_once_with(1, 999, GameType.WINNER)


@pytest.mark.asyncio
async def test_start_winner_game_calls_logic():
    """
    Verify that the handler correctly delegates execution to start_game.

    We aren't testing the game logic itself, but checking:
    - correct chat_id
    - correct GameType
    """

    message = AsyncMock()
    db = MagicMock(spec=DBHandler)

    # Mock start_game to avoid running real logic
    with patch(
        "friends_bot.handlers.start_game", new_callable=AsyncMock
    ) as mocked_logic:
        await start_winner_game(message, db)

        # Verify call correctness
        mocked_logic.assert_called_once_with(
            message.chat.id, GameType.WINNER, message, db
        )


@pytest.mark.asyncio
async def test_start_loser_game_calls_logic():
    """
    Similar test for the loser-game.

    Verify:
    handler must pass control to start_game
    with the correct game type (GameType.LOSER)
    """

    message = AsyncMock()
    db = MagicMock(spec=DBHandler)

    with patch(
        "friends_bot.handlers.start_game", new_callable=AsyncMock
    ) as mocked_logic:
        await start_loser_game(message, db)

        mocked_logic.assert_called_once_with(
            message.chat.id, GameType.LOSER, message, db
        )


@pytest.mark.asyncio
async def test_start_game_lock_prevents_race():
    """
    Verify that when running the game in parallel in one chat,
    the winner is recorded only once.

    Scenario:
    - Two start_game calls begin "simultaneously"
    - The first selects a winner and records them
    - The second should see that a winner already exists and not call set_winner

    Note:
    The Lock itself doesn't forbid the second call - it serializes the execution 
    sequence. Therefore, we additionally simulate DB behavior via 'state':
    the state changes after the first set_winner.
    """

    message1 = AsyncMock()
    message2 = AsyncMock()

    db = MagicMock(spec=DBHandler)

    # DB state imitation:
    # initially no winner, appears after recording
    state = {"has_winner": False}

    def is_already_runned(*args, **kwargs):
        # Return None while there's no winner,
        # and any value (as if user_id was found) if there is
        return (1,) if state["has_winner"] else None

    def set_winner(*args, **kwargs):
        # Record winner and "fix" state as a side effect
        state["has_winner"] = True

    db.is_already_runned.side_effect = is_already_runned
    db.get_players.return_value = [(1, "User")]
    db.set_winner.side_effect = set_winner

    # Run two calls in parallel
    await asyncio.gather(
        start_game(1, GameType.WINNER, message1, db),
        start_game(1, GameType.WINNER, message2, db),
    )

    # Winner should be recorded only once
    assert db.set_winner.call_count == 1


@pytest.mark.asyncio
async def test_start_game_lock_serializes_execution():
    """
    Verify that the Lock actually serializes the sequence of execution.

    Scenario:
    - First start_game call completes fully
    - Second call begins only after it
    - And already sees that the game has run

    Verify:
    the second call should not reach get_players
    """

    message1 = AsyncMock()
    message2 = AsyncMock()

    db = MagicMock(spec=DBHandler)

    # First call - game hasn't happened yet
    # Second call - game already happened (after the first)
    db.is_already_runned.side_effect = [None, (1,)]
    db.get_players.return_value = [(1, "User")]

    db.set_winner = MagicMock()

    # Run two calls in parallel
    await asyncio.gather(
        start_game(1, GameType.WINNER, message1, db),
        start_game(1, GameType.WINNER, message2, db),
    )

    # get_players should be called only once:
    # second call did not reach this stage
    assert db.get_players.call_count == 1


@pytest.mark.asyncio
async def test_lock_is_per_chat():
    """
    Verify that Lock is applied at the chat_id level, not globally.

    Scenario:
    - Run games simultaneously in two different chats
    - They should not block each other

    Verify:
    both calls should successfully record a winner
    """

    message1 = AsyncMock()
    message2 = AsyncMock()

    db = MagicMock(spec=DBHandler)

    db.is_already_runned.return_value = None
    db.get_players.return_value = [(1, "User")]

    db.set_winner = MagicMock()

    # Run two calls in different chats in parallel
    await asyncio.gather(
        start_game(1, GameType.WINNER, message1, db),
        start_game(2, GameType.WINNER, message2, db),
    )

    # Both calls should execute independently
    assert db.set_winner.call_count == 2
