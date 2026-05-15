from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from friends_bot_service.handlers.user import list_players, register, unregister


def build_message(
    *,
    chat_id: int = 10,
    user_id: int | None = 20,
    username: str | None = "test_user",
    full_name: str = "Test User",
) -> AsyncMock:
    """Builds a minimal aiogram message mock for user handler tests."""

    message = AsyncMock()
    message.chat.id = chat_id

    if user_id is None:
        message.from_user = None
    else:
        message.from_user = SimpleNamespace(
            id=user_id,
            username=username,
            full_name=full_name,
        )

    return message


@pytest.mark.asyncio
async def test_register_returns_early_when_user_is_missing():
    """
    Verify the register handler early-exit branch when from_user is missing.

    Scenario:
    - the /reg handler is called
    - the incoming message has no from_user

    Expected behavior:
    - repository upsert is not called
    - commit does not happen
    - no response message is sent
    """

    # Prepare a message without Telegram user data.
    message = build_message(user_id=None)
    bot = SimpleNamespace(id=1)
    session = AsyncMock()

    # Guard against any unintended repository usage.
    with patch(
        "friends_bot_service.handlers.user.user_repo.upsert_db_user",
        new=AsyncMock(),
    ) as upsert_db_user:
        await register(message, bot, session, "upd-1")

    # The handler must stop without touching the database or replying.
    upsert_db_user.assert_not_awaited()
    session.commit.assert_not_awaited()
    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_register_rejects_when_registration_is_disabled():
    """
    Verify the register handler when new registrations are disabled.

    Scenario:
    - the /reg handler is called with a valid Telegram user
    - global registration is turned off in settings

    Expected behavior:
    - repository upsert is not called
    - commit does not happen
    - the chat receives a temporary closure message
    """

    # Prepare a normal registration request.
    message = build_message(chat_id=10, user_id=20, username="test_user")
    bot = SimpleNamespace(id=1)
    session = AsyncMock()

    # Freeze the feature flag in the disabled state.
    with (
        patch(
            "friends_bot_service.handlers.user.settings.REGISTRATION_ENABLED",
            False,
        ),
        patch(
            "friends_bot_service.handlers.user.user_repo.upsert_db_user",
            new=AsyncMock(),
        ) as upsert_db_user,
    ):
        await register(message, bot, session, "upd-1")

    # The handler must report the closure without touching the database.
    upsert_db_user.assert_not_awaited()
    session.commit.assert_not_awaited()
    message.answer.assert_awaited_once_with("Регистрация игроков временно закрыта.")


@pytest.mark.asyncio
async def test_register_upserts_user_and_answers():
    """
    Verify the successful register handler flow.

    Scenario:
    - the /reg handler is called with a valid Telegram user

    Expected behavior:
    - repository upsert is called with the user data
    - the session is committed
    - success message is sent back to the chat
    """

    # Prepare a normal registration request.
    message = build_message(chat_id=10, user_id=20, username="test_user")
    bot = SimpleNamespace(id=1)
    session = AsyncMock()

    # Intercept the repository call to verify the payload.
    with patch(
        "friends_bot_service.handlers.user.user_repo.upsert_db_user",
        new=AsyncMock(),
    ) as upsert_db_user:
        await register(message, bot, session, "upd-1")

    # The handler must upsert, commit and answer with the success text.
    upsert_db_user.assert_awaited_once_with(
        session, 1, 10, 20, "test_user", "Test User"
    )
    session.commit.assert_awaited_once()
    message.answer.assert_awaited_once_with("Ты в игре!")


@pytest.mark.asyncio
async def test_unregister_returns_early_when_user_is_missing():
    """
    Verify the unregister handler early-exit branch when from_user is missing.

    Scenario:
    - the /delete handler is called
    - the incoming message has no from_user

    Expected behavior:
    - repository lookup is not called
    - commit does not happen
    - no response message is sent
    """

    # Prepare a message without Telegram user data.
    message = build_message(user_id=None)
    bot = SimpleNamespace(id=1)
    session = AsyncMock()

    # Guard against any unintended repository usage.
    with patch(
        "friends_bot_service.handlers.user.user_repo.get_db_user",
        new=AsyncMock(),
    ) as get_db_user:
        await unregister(message, session, bot, "upd-1")

    # The handler must stop without touching the database or replying.
    get_db_user.assert_not_awaited()
    session.commit.assert_not_awaited()
    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_unregister_reports_missing_player():
    """
    Verify unregister behavior when the player record does not exist.

    Scenario:
    - the /delete handler is called by a valid user
    - repository lookup returns no player row

    Expected behavior:
    - the handler reports that the player is already absent
    - commit does not happen
    """

    # Prepare a normal unregister request.
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=1)
    session = AsyncMock()

    # Simulate missing player row in the repository.
    with patch(
        "friends_bot_service.handlers.user.user_repo.get_db_user",
        new=AsyncMock(return_value=None),
    ):
        await unregister(message, session, bot, "upd-1")

    # The handler must only answer with the "already absent" message.
    session.commit.assert_not_awaited()
    message.answer.assert_awaited_once_with("Тебя и так нет в списках игроков.")


@pytest.mark.asyncio
async def test_unregister_reports_already_inactive_player():
    """
    Verify unregister behavior when the player is already inactive.

    Scenario:
    - the /delete handler is called by a valid user
    - repository lookup returns an inactive player row

    Expected behavior:
    - the handler reports that the player is already absent
    - commit does not happen
    """

    # Prepare a normal unregister request.
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=1)
    session = AsyncMock()
    db_user = SimpleNamespace(is_active=False)

    # Simulate an already inactive player row.
    with patch(
        "friends_bot_service.handlers.user.user_repo.get_db_user",
        new=AsyncMock(return_value=db_user),
    ):
        await unregister(message, session, bot, "upd-1")

    # The handler must only answer with the "already absent" message.
    session.commit.assert_not_awaited()
    message.answer.assert_awaited_once_with("Тебя и так нет в списках игроков.")


@pytest.mark.asyncio
async def test_unregister_deactivates_player_and_answers():
    """
    Verify the successful unregister handler flow.

    Scenario:
    - the /delete handler is called by a valid user
    - repository lookup returns an active player row

    Expected behavior:
    - the player row becomes inactive
    - the session is committed
    - the farewell message is sent
    """

    # Prepare a normal unregister request and an active player row.
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=1)
    session = AsyncMock()
    db_user = SimpleNamespace(is_active=True)

    # Simulate successful player lookup.
    with patch(
        "friends_bot_service.handlers.user.user_repo.get_db_user",
        new=AsyncMock(return_value=db_user),
    ):
        await unregister(message, session, bot, "upd-1")

    # The handler must deactivate the row, commit and answer with the final text.
    assert db_user.is_active is False
    session.commit.assert_awaited_once()
    message.answer.assert_awaited_once_with("Ты вышел из игры. Но мы всё помним... 😉")


@pytest.mark.asyncio
async def test_list_players_returns_early_when_user_is_missing():
    """When from_user is missing, /list must not query or reply."""

    message = build_message(user_id=None)
    bot = SimpleNamespace(id=1)
    session = AsyncMock()

    with patch(
        "friends_bot_service.handlers.user.user_repo.list_active_players_for_chat",
        new=AsyncMock(),
    ) as list_active_players_for_chat:
        await list_players(message, bot, session, "upd-1")

    list_active_players_for_chat.assert_not_awaited()
    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_players_reports_empty_roster():
    """When no active players exist for the chat, /list answers with a short note."""

    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=1)
    session = AsyncMock()

    with patch(
        "friends_bot_service.handlers.user.user_repo.list_active_players_for_chat",
        new=AsyncMock(return_value=[]),
    ) as list_active_players_for_chat:
        await list_players(message, bot, session, "upd-1")

    list_active_players_for_chat.assert_awaited_once_with(session, 1, 10)
    message.answer.assert_awaited_once_with("Никто не зарегистрировался в игре.")


@pytest.mark.asyncio
async def test_list_players_formats_registered_users():
    """When players exist, /list renders one line per row from the repository."""

    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=1)
    session = AsyncMock()
    alice = SimpleNamespace(full_name="Alice", username="alice_u")
    bob = SimpleNamespace(full_name="Bob", username=None)

    with patch(
        "friends_bot_service.handlers.user.user_repo.list_active_players_for_chat",
        new=AsyncMock(return_value=[alice, bob]),
    ):
        await list_players(message, bot, session, "upd-1")

    message.answer.assert_awaited_once_with(
        "Участники игры в этом чате:\n"
        "1) Alice @alice_u\n"
        "2) Bob"
    )
