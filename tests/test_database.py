import pytest

from friends_bot_service.database import DBHandler
from friends_bot_service.enums import GameType


@pytest.fixture
def db():
    """
    Creates an isolated SQLite database in memory for each test.

    Why it matters:
    - tests do not affect each other
    - state is always clean
    - behavior is as close to a real DB as possible
    """
    handler = DBHandler(":memory:")
    yield handler
    handler.close()


def test_register_and_update_user(db):
    """
    Verify the idempotency of user registration behavior.

    Scenario:
    - user registers for the first time
    - then registers again with new data

    Expected behavior:
    - record is not duplicated (PRIMARY KEY + ON CONFLICT works)
    - data is updated
    """
    # First registration
    db.register_user(chat_id=1, user_id=10, username="usertest", full_name="Name Test")
    players = db.get_players(chat_id=1)

    assert len(players) == 1
    assert players[0][1] == "Name Test"

    # Re-registration with a name change
    db.register_user(chat_id=1, user_id=10, username="testuser", full_name="Test Name")
    players = db.get_players(chat_id=1)

    # Row is not duplicated
    assert len(players) == 1

    # Data has been updated
    assert players[0][1] == "Test Name"


def test_unregister_and_re_register(db):
    """
    Verify the "soft delete" of a user.

    Scenario:
    - user registers
    - then "deleted" (is_active = 0)
    - then registers again

    Expected behavior:
    - deleted user does not participate in the game
    - becomes active again upon re-registration
    """

    db.register_user(1, 10, "testuser", "Test Name")

    # Deactivate user
    db.unregister_user(1, 10)

    players = db.get_players(chat_id=1)

    # User does not participate in the game
    assert len(players) == 0

    # Re-registration (should reactivate them)
    db.register_user(1, 10, "testuser", "Test Name")

    players = db.get_players(chat_id=1)

    # Active again
    assert len(players) == 1


def test_exclude_today_winner(db):
    """
    Verify business rule:
    a user who already participated today (win/lose)
    should not be included in the selection for a new game.

    Scenario:
    - two users are registered
    - assign a win (WINNER) to one of them
    - request the list of players

    Expected behavior:
    - the user with a result for today is excluded
    """

    db.register_user(1, 10, "testuser1", "Test Name1")
    db.register_user(1, 20, "testuser2", "Test Name2")

    # Assign a winner
    db.set_winner(chat_id=1, user_id=20, game_type=GameType.WINNER)

    # Get the list of available players
    players = db.get_players(chat_id=1)

    # Only one should remain
    assert len(players) == 1

    # And it's not the one who already won
    assert players[0][0] == 10


def test_chat_isolation(db):
    """
    Verify data isolation by chat_id.

    Scenario:
    - the same user is in two different chats
    - a game is played in only one chat

    Expected behavior:
    - state of one chat does not affect the other
    - statistics and player selection are independent
    """

    user_id = 777
    chat_one = 1
    chat_two = 2

    # Register the user in two chats
    db.register_user(chat_one, user_id, "testuser", "Test Name")
    db.register_user(chat_two, user_id, "testuser", "Test Name")

    # Play the game only in the first chat
    db.set_winner(chat_one, user_id, GameType.LOSER)

    # In the first chat, the game has already run
    assert db.is_already_runned(chat_one, GameType.LOSER) is not None

    # In the second chat, it hasn't
    assert db.is_already_runned(chat_two, GameType.LOSER) is None

    # Check the player lists

    # In the first chat, the user has already participated - excluded
    players_one = db.get_players(chat_one)
    assert len(players_one) == 0

    # In the second chat, they are available
    players_two = db.get_players(chat_two)
    assert len(players_two) == 1
    assert players_two[0][0] == user_id


def test_unique_index_prevents_two_winners_same_day(db):
    """
    Verify UNIQUE INDEX constraint:
    there cannot be two winners in the same chat on the same day.

    Scenario:
    - two users
    - attempt to record a win for both on the same day

    Expected behavior:
    - the second INSERT fails with IntegrityError
    """

    db.register_user(1, 10, "user1", "User 1")
    db.register_user(1, 20, "user2", "User 2")

    # First winner - ok
    assert db.set_winner(1, 10, GameType.WINNER) is True

    # Second one should violate UNIQUE INDEX
    assert db.set_winner(1, 20, GameType.WINNER) is False
