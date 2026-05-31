import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from friends_bot_service.draw import domain
from friends_bot_service.draw.handlers.loser_draw import start_loser_draw
from friends_bot_service.draw.handlers.winner_draw import start_winner_draw
from friends_bot_service.draw.usecases.run_draw import (
    PrepareDrawOutcome,
    PrepareDrawResult,
)
from friends_bot_service.infra.texts.draw_entrant_text import (
    DRAW_ALREADY_PLAYED,
    DRAW_ENTRANT_NOT_IN_LIST,
    DRAW_NO_PLAYERS,
)
from friends_bot_service.infra.texts.game_text import WINNER_MESSAGES
from tests.helpers.uow import invoke_run_with_unit_of_work

_real_asyncio_sleep = asyncio.sleep


class DummyTypingContext:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return None


def build_message(chat_id: int = 10, user_id: int = 20) -> AsyncMock:
    message = AsyncMock()
    message.chat.id = chat_id
    message.from_user = SimpleNamespace(id=user_id)
    message.message_thread_id = None
    return message


@pytest.mark.asyncio
async def test_start_game_reports_if_already_run():
    message = build_message()
    bot = SimpleNamespace(id=1)

    with (
        patch(
            "friends_bot_service.draw.handlers.common.db.run_with_unit_of_work",
            new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
        ) as run_uow,
        patch(
            "friends_bot_service.draw.handlers.common._touch_bot_game_attempt.execute",
            new=AsyncMock(),
        ) as touch_execute,
        patch(
            "friends_bot_service.draw.handlers.common._prepare_draw.execute",
            new=AsyncMock(
                return_value=PrepareDrawResult(
                    outcome=PrepareDrawOutcome.ALREADY_PLAYED
                )
            ),
        ) as prepare_execute,
        patch(
            "friends_bot_service.draw.handlers.common._record_draw.execute",
            new=AsyncMock(),
        ) as record_execute,
    ):
        await start_winner_draw(message, bot, "upd-1")

    run_uow.assert_awaited_once()
    touch_execute.assert_awaited_once()
    prepare_execute.assert_awaited_once()
    record_execute.assert_not_awaited()
    message.answer.assert_awaited_once_with(DRAW_ALREADY_PLAYED)


@pytest.mark.asyncio
async def test_start_game_reports_if_no_players():
    message = build_message()
    bot = SimpleNamespace(id=1)

    with (
        patch(
            "friends_bot_service.draw.handlers.common.db.run_with_unit_of_work",
            new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
        ),
        patch(
            "friends_bot_service.draw.handlers.common._touch_bot_game_attempt.execute",
            new=AsyncMock(),
        ),
        patch(
            "friends_bot_service.draw.handlers.common._prepare_draw.execute",
            new=AsyncMock(
                return_value=PrepareDrawResult(outcome=PrepareDrawOutcome.NO_PLAYERS)
            ),
        ) as prepare_execute,
        patch(
            "friends_bot_service.draw.handlers.common._record_draw.execute",
            new=AsyncMock(),
        ) as record_execute,
    ):
        await start_winner_draw(message, bot, "upd-1")

    prepare_execute.assert_awaited_once()
    record_execute.assert_not_awaited()
    message.answer.assert_awaited_once_with(DRAW_NO_PLAYERS)


@pytest.mark.asyncio
@pytest.mark.parametrize("game_type", [domain.GameType.WINNER, domain.GameType.LOSER])
async def test_start_game_success_flow(game_type: domain.GameType):
    message = build_message()
    bot = SimpleNamespace(id=1)
    today = date.today()
    steps = WINNER_MESSAGES[game_type][:-1]
    final_step = WINNER_MESSAGES[game_type][-1] + "Test Name"

    prepare_result = PrepareDrawResult(
        outcome=PrepareDrawOutcome.READY,
        suspense_messages=tuple(steps),
        final_message=final_step,
        winner_user_id=777,
        today_utc=today,
    )

    with (
        patch(
            "friends_bot_service.draw.handlers.common.db.run_with_unit_of_work",
            new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
        ) as run_uow,
        patch(
            "friends_bot_service.draw.handlers.common._touch_bot_game_attempt.execute",
            new=AsyncMock(),
        ),
        patch(
            "friends_bot_service.draw.handlers.common._prepare_draw.execute",
            new=AsyncMock(return_value=prepare_result),
        ),
        patch(
            "friends_bot_service.draw.handlers.common._record_draw.execute",
            new=AsyncMock(),
        ) as record_execute,
        patch(
            "friends_bot_service.draw.handlers.common.ChatActionSender.typing",
            return_value=DummyTypingContext(),
        ) as typing_mock,
        patch(
            "friends_bot_service.draw.handlers.common.asyncio.sleep",
            new=AsyncMock(),
        ) as sleep_mock,
    ):
        handler = (
            start_winner_draw
            if game_type == domain.GameType.WINNER
            else start_loser_draw
        )
        await handler(message, bot, "upd-1")

    assert run_uow.await_count == 2
    typing_mock.assert_called_once_with(chat_id=10, bot=bot, message_thread_id=None)
    record_execute.assert_awaited_once()
    assert sleep_mock.await_count == len(steps) + 1

    sent_messages = [call.args[0] for call in message.answer.await_args_list]
    assert sent_messages == [*steps, final_step]


@pytest.mark.asyncio
async def test_start_winner_game_rejects_unregistered_user():
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=30)

    with (
        patch(
            "friends_bot_service.draw.handlers.common.db.run_with_unit_of_work",
            new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
        ),
        patch(
            "friends_bot_service.draw.handlers.common._touch_bot_game_attempt.execute",
            new=AsyncMock(),
        ) as touch_execute,
        patch(
            "friends_bot_service.draw.handlers.common._prepare_draw.execute",
            new=AsyncMock(
                return_value=PrepareDrawResult(
                    outcome=PrepareDrawOutcome.NOT_REGISTERED
                )
            ),
        ) as prepare_execute,
        patch(
            "friends_bot_service.draw.handlers.common._record_draw.execute",
            new=AsyncMock(),
        ) as record_execute,
    ):
        await start_winner_draw(message, bot, "upd-1")

    touch_execute.assert_awaited_once()
    prepare_execute.assert_awaited_once()
    record_execute.assert_not_awaited()
    message.answer.assert_awaited_once_with(DRAW_ENTRANT_NOT_IN_LIST)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler", "game_type"),
    [
        (start_winner_draw, domain.GameType.WINNER),
        (start_loser_draw, domain.GameType.LOSER),
    ],
)
async def test_game_command_starts_game_for_registered_user(handler, game_type):
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=30)
    today = date.today()
    steps = WINNER_MESSAGES[game_type][:-1]
    final_step = WINNER_MESSAGES[game_type][-1] + "Winner"

    prepare_result = PrepareDrawResult(
        outcome=PrepareDrawOutcome.READY,
        suspense_messages=tuple(steps),
        final_message=final_step,
        winner_user_id=777,
        today_utc=today,
    )

    with (
        patch(
            "friends_bot_service.draw.handlers.common.db.run_with_unit_of_work",
            new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
        ) as run_uow,
        patch(
            "friends_bot_service.draw.handlers.common._touch_bot_game_attempt.execute",
            new=AsyncMock(),
        ) as touch_execute,
        patch(
            "friends_bot_service.draw.handlers.common._prepare_draw.execute",
            new=AsyncMock(return_value=prepare_result),
        ) as prepare_execute,
        patch(
            "friends_bot_service.draw.handlers.common._record_draw.execute",
            new=AsyncMock(),
        ) as record_execute,
        patch(
            "friends_bot_service.draw.handlers.common.ChatActionSender.typing",
            return_value=DummyTypingContext(),
        ),
        patch(
            "friends_bot_service.draw.handlers.common.asyncio.sleep",
            new=AsyncMock(),
        ),
    ):
        await handler(message, bot, "upd-1")

    assert run_uow.await_count == 2
    touch_execute.assert_awaited_once()
    prepare_execute.assert_awaited_once()
    record_execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_draw_handlers_do_not_overlap_in_same_chat():
    """Only one draw handler may run per bot/chat at a time (handler-level mutex)."""
    message_one = build_message(chat_id=10, user_id=20)
    message_two = build_message(chat_id=10, user_id=21)
    bot = SimpleNamespace(id=1)
    today = date.today()
    steps = WINNER_MESSAGES[domain.GameType.WINNER][:-1]
    final_step = WINNER_MESSAGES[domain.GameType.WINNER][-1] + "Winner"
    prepare_result = PrepareDrawResult(
        outcome=PrepareDrawOutcome.READY,
        suspense_messages=tuple(steps),
        final_message=final_step,
        winner_user_id=777,
        today_utc=today,
    )
    inside_suspense = 0
    peak_concurrent_handlers = 0

    async def sleep_that_yields(_seconds: float) -> None:
        nonlocal inside_suspense, peak_concurrent_handlers
        inside_suspense += 1
        peak_concurrent_handlers = max(peak_concurrent_handlers, inside_suspense)
        await _real_asyncio_sleep(0)
        inside_suspense -= 1

    with (
        patch(
            "friends_bot_service.draw.handlers.common.db.run_with_unit_of_work",
            new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
        ),
        patch(
            "friends_bot_service.draw.handlers.common._touch_bot_game_attempt.execute",
            new=AsyncMock(),
        ),
        patch(
            "friends_bot_service.draw.handlers.common._prepare_draw.execute",
            new=AsyncMock(return_value=prepare_result),
        ),
        patch(
            "friends_bot_service.draw.handlers.common._record_draw.execute",
            new=AsyncMock(),
        ),
        patch(
            "friends_bot_service.draw.handlers.common.ChatActionSender.typing",
            return_value=DummyTypingContext(),
        ),
        patch(
            "friends_bot_service.draw.handlers.common.asyncio.sleep",
            new=AsyncMock(side_effect=sleep_that_yields),
        ),
    ):
        await asyncio.gather(
            start_winner_draw(message_one, bot, "upd-1"),
            start_winner_draw(message_two, bot, "upd-2"),
        )

    assert peak_concurrent_handlers == 1
