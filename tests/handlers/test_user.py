from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from friends_bot_service.domain import Player
from friends_bot_service.handlers.user import list_players, register, unregister
from friends_bot_service.texts.player_text import (
    PLAYER_ALREADY_NOT_IN_LIST,
    PLAYER_LIST_EMPTY,
    PLAYER_LIST_HEADER,
    PLAYER_REGISTERED,
    PLAYER_REGISTRATION_DISABLED,
    PLAYER_UNREGISTERED,
)
from friends_bot_service.usecases.user import (
    ListPlayersOutcome,
    ListPlayersResult,
    RegisterPlayerOutcome,
    RegisterPlayerResult,
    UnregisterPlayerOutcome,
    UnregisterPlayerResult,
)
from tests.helpers.uow import invoke_run_with_unit_of_work


def build_message(
    *,
    chat_id: int = 10,
    user_id: int | None = 20,
    username: str | None = "test_user",
    full_name: str = "Test User",
) -> AsyncMock:
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
    message = build_message(user_id=None)
    bot = SimpleNamespace(id=1)

    with patch(
        "friends_bot_service.handlers.user.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ):
        with patch("friends_bot_service.handlers.user.RegisterPlayer") as register_cls:
            register_cls.return_value.execute = AsyncMock(
                return_value=RegisterPlayerResult(
                    outcome=RegisterPlayerOutcome.USER_MISSING
                )
            )
            await register(message, bot, "upd-1")

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_register_rejects_when_registration_is_disabled():
    message = build_message(chat_id=10, user_id=20, username="test_user")
    bot = SimpleNamespace(id=1)

    with patch(
        "friends_bot_service.handlers.user.settings.REGISTRATION_ENABLED",
        False,
    ):
        with patch(
            "friends_bot_service.handlers.user.run_with_unit_of_work",
            new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
        ):
            with patch(
                "friends_bot_service.handlers.user.RegisterPlayer"
            ) as register_cls:
                register_cls.return_value.execute = AsyncMock(
                    return_value=RegisterPlayerResult(
                        outcome=RegisterPlayerOutcome.REGISTRATION_DISABLED
                    )
                )
                await register(message, bot, "upd-1")

    message.answer.assert_awaited_once_with(PLAYER_REGISTRATION_DISABLED)


@pytest.mark.asyncio
async def test_register_upserts_user_and_answers():
    message = build_message(chat_id=10, user_id=20, username="test_user")
    bot = SimpleNamespace(id=1)

    with patch(
        "friends_bot_service.handlers.user.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ) as run_uow:
        with patch("friends_bot_service.handlers.user.RegisterPlayer") as register_cls:
            register_cls.return_value.execute = AsyncMock(
                return_value=RegisterPlayerResult(outcome=RegisterPlayerOutcome.SUCCESS)
            )
            await register(message, bot, "upd-1")

    run_uow.assert_awaited_once()
    message.answer.assert_awaited_once_with(PLAYER_REGISTERED)


@pytest.mark.asyncio
async def test_unregister_returns_early_when_user_is_missing():
    message = build_message(user_id=None)
    bot = SimpleNamespace(id=1)

    with patch(
        "friends_bot_service.handlers.user.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ):
        with patch(
            "friends_bot_service.handlers.user.UnregisterPlayer"
        ) as unregister_cls:
            unregister_cls.return_value.execute = AsyncMock(
                return_value=UnregisterPlayerResult(
                    outcome=UnregisterPlayerOutcome.USER_MISSING
                )
            )
            await unregister(message, bot, "upd-1")

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_unregister_reports_missing_player():
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=1)

    with patch(
        "friends_bot_service.handlers.user.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ):
        with patch(
            "friends_bot_service.handlers.user._unregister_player.execute",
            new=AsyncMock(
                return_value=UnregisterPlayerResult(
                    outcome=UnregisterPlayerOutcome.NOT_FOUND
                )
            ),
        ):
            await unregister(message, bot, "upd-1")

    message.answer.assert_awaited_once_with(PLAYER_ALREADY_NOT_IN_LIST)


@pytest.mark.asyncio
async def test_unregister_reports_already_inactive_player():
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=1)

    with patch(
        "friends_bot_service.handlers.user.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ):
        with patch(
            "friends_bot_service.handlers.user._unregister_player.execute",
            new=AsyncMock(
                return_value=UnregisterPlayerResult(
                    outcome=UnregisterPlayerOutcome.ALREADY_INACTIVE
                )
            ),
        ):
            await unregister(message, bot, "upd-1")

    message.answer.assert_awaited_once_with(PLAYER_ALREADY_NOT_IN_LIST)


@pytest.mark.asyncio
async def test_unregister_deactivates_player_and_answers():
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=1)

    with patch(
        "friends_bot_service.handlers.user.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ):
        with patch(
            "friends_bot_service.handlers.user._unregister_player.execute",
            new=AsyncMock(
                return_value=UnregisterPlayerResult(
                    outcome=UnregisterPlayerOutcome.SUCCESS
                )
            ),
        ):
            await unregister(message, bot, "upd-1")

    message.answer.assert_awaited_once_with(PLAYER_UNREGISTERED)


@pytest.mark.asyncio
async def test_list_players_returns_early_when_user_is_missing():
    message = build_message(user_id=None)
    bot = SimpleNamespace(id=1)

    with patch(
        "friends_bot_service.handlers.user.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ):
        with patch(
            "friends_bot_service.handlers.user._list_players.execute",
            new=AsyncMock(
                return_value=ListPlayersResult(outcome=ListPlayersOutcome.USER_MISSING)
            ),
        ):
            await list_players(message, bot, "upd-1")

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_players_reports_empty_roster():
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=1)

    with patch(
        "friends_bot_service.handlers.user.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ):
        with patch(
            "friends_bot_service.handlers.user._list_players.execute",
            new=AsyncMock(
                return_value=ListPlayersResult(outcome=ListPlayersOutcome.EMPTY)
            ),
        ):
            await list_players(message, bot, "upd-1")

    message.answer.assert_awaited_once_with(PLAYER_LIST_EMPTY)


@pytest.mark.asyncio
async def test_list_players_formats_registered_users():
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=1)
    players = (
        Player(1, 10, 1, "alice_u", "Alice", True),
        Player(1, 10, 2, None, "Bob", True),
    )

    with patch(
        "friends_bot_service.handlers.user.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ):
        with patch(
            "friends_bot_service.handlers.user._list_players.execute",
            new=AsyncMock(
                return_value=ListPlayersResult(
                    outcome=ListPlayersOutcome.SUCCESS,
                    players=players,
                )
            ),
        ):
            await list_players(message, bot, "upd-1")

    message.answer.assert_awaited_once_with(
        PLAYER_LIST_HEADER + "1) Alice @alice_u\n2) Bob"
    )
