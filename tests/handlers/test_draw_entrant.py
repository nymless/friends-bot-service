from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from friends_bot_service.draw_entrant.domain.draw_entrant import RegisteredDrawEntrant
from friends_bot_service.draw_entrant.handlers.list import list_draw_entrants
from friends_bot_service.draw_entrant.handlers.register import register
from friends_bot_service.draw_entrant.handlers.unregister import unregister
from friends_bot_service.draw_entrant.usecases import (
    ListDrawEntrantsOutcome,
    ListDrawEntrantsResult,
    UnregisterDrawEntrantOutcome,
    UnregisterDrawEntrantResult,
)
from friends_bot_service.infra.texts.draw_entrant_text import (
    DRAW_ENTRANT_ALREADY_NOT_IN_LIST,
    DRAW_ENTRANT_LIST_EMPTY,
    DRAW_ENTRANT_LIST_HEADER,
    DRAW_ENTRANT_REGISTERED,
    DRAW_ENTRANT_REGISTRATION_DISABLED,
    DRAW_ENTRANT_UNREGISTERED,
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
        "friends_bot_service.draw_entrant.handlers.register.db.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ):
        await register(message, bot, "upd-1")

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_register_rejects_when_registration_is_disabled():
    message = build_message(chat_id=10, user_id=20, username="test_user")
    bot = SimpleNamespace(id=1)

    with patch(
        "friends_bot_service.draw_entrant.handlers.register.settings.REGISTRATION_ENABLED",
        False,
    ):
        await register(message, bot, "upd-1")

    message.answer.assert_awaited_once_with(DRAW_ENTRANT_REGISTRATION_DISABLED)


@pytest.mark.asyncio
async def test_register_upserts_user_and_answers():
    message = build_message(chat_id=10, user_id=20, username="test_user")
    bot = SimpleNamespace(id=1)

    with patch(
        "friends_bot_service.draw_entrant.handlers.register.db.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ) as run_uow:
        with patch(
            "friends_bot_service.draw_entrant.handlers.register._register_draw_entrant.execute",
            new=AsyncMock(),
        ):
            await register(message, bot, "upd-1")

    run_uow.assert_awaited_once()
    message.answer.assert_awaited_once_with(DRAW_ENTRANT_REGISTERED)


@pytest.mark.asyncio
async def test_unregister_returns_early_when_user_is_missing():
    message = build_message(user_id=None)
    bot = SimpleNamespace(id=1)

    with patch(
        "friends_bot_service.draw_entrant.handlers.unregister.db.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ):
        await unregister(message, bot, "upd-1")

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_unregister_reports_missing_player():
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=1)

    with patch(
        "friends_bot_service.draw_entrant.handlers.unregister.db.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ):
        with patch(
            "friends_bot_service.draw_entrant.handlers.unregister._unregister.execute",
            new=AsyncMock(
                return_value=UnregisterDrawEntrantResult(
                    outcome=UnregisterDrawEntrantOutcome.NOT_FOUND
                )
            ),
        ):
            await unregister(message, bot, "upd-1")

    message.answer.assert_awaited_once_with(DRAW_ENTRANT_ALREADY_NOT_IN_LIST)


@pytest.mark.asyncio
async def test_unregister_reports_already_inactive_player():
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=1)

    with patch(
        "friends_bot_service.draw_entrant.handlers.unregister.db.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ):
        with patch(
            "friends_bot_service.draw_entrant.handlers.unregister._unregister.execute",
            new=AsyncMock(
                return_value=UnregisterDrawEntrantResult(
                    outcome=UnregisterDrawEntrantOutcome.ALREADY_INACTIVE
                )
            ),
        ):
            await unregister(message, bot, "upd-1")

    message.answer.assert_awaited_once_with(DRAW_ENTRANT_ALREADY_NOT_IN_LIST)


@pytest.mark.asyncio
async def test_unregister_deactivates_player_and_answers():
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=1)

    with patch(
        "friends_bot_service.draw_entrant.handlers.unregister.db.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ):
        with patch(
            "friends_bot_service.draw_entrant.handlers.unregister._unregister.execute",
            new=AsyncMock(
                return_value=UnregisterDrawEntrantResult(
                    outcome=UnregisterDrawEntrantOutcome.SUCCESS
                )
            ),
        ):
            await unregister(message, bot, "upd-1")

    message.answer.assert_awaited_once_with(DRAW_ENTRANT_UNREGISTERED)


@pytest.mark.asyncio
async def test_list_players_returns_early_when_user_is_missing():
    message = build_message(user_id=None)
    bot = SimpleNamespace(id=1)

    with patch(
        "friends_bot_service.draw_entrant.handlers.list.db.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ):
        await list_draw_entrants(message, bot, "upd-1")

    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_players_reports_empty_roster():
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=1)

    with patch(
        "friends_bot_service.draw_entrant.handlers.list.db.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ):
        with patch(
            "friends_bot_service.draw_entrant.handlers.list._list_draw_entrants.execute",
            new=AsyncMock(
                return_value=ListDrawEntrantsResult(
                    outcome=ListDrawEntrantsOutcome.NO_ENTRANTS
                )
            ),
        ):
            await list_draw_entrants(message, bot, "upd-1")

    message.answer.assert_awaited_once_with(DRAW_ENTRANT_LIST_EMPTY)


@pytest.mark.asyncio
async def test_list_players_formats_registered_users():
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=1)
    draw_entrants = (
        RegisteredDrawEntrant(1, 10, 1, "alice_u", "Alice", True),
        RegisteredDrawEntrant(1, 10, 2, None, "Bob", True),
    )

    with patch(
        "friends_bot_service.draw_entrant.handlers.list.db.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ):
        with patch(
            "friends_bot_service.draw_entrant.handlers.list._list_draw_entrants.execute",
            new=AsyncMock(
                return_value=ListDrawEntrantsResult(
                    outcome=ListDrawEntrantsOutcome.SUCCESS,
                    draw_entrants=draw_entrants,
                )
            ),
        ):
            await list_draw_entrants(message, bot, "upd-1")

    message.answer.assert_awaited_once_with(
        DRAW_ENTRANT_LIST_HEADER + "1) Alice @alice_u\n2) Bob"
    )
