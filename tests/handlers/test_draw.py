from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from friends_bot_service.draw import domain
from friends_bot_service.draw.handlers.loser_draw import start_loser_draw
from friends_bot_service.draw.handlers.winner_draw import start_winner_draw
from friends_bot_service.draw.usecases.run_draw import (
    ClaimDrawOutcome,
    ClaimDrawResult,
)
from friends_bot_service.infra.texts.draw_entrant_text import (
    DRAW_ALREADY_PLAYED,
    DRAW_ENTRANT_NOT_IN_LIST,
    DRAW_NO_DRAW_ENTRANTS,
)
from friends_bot_service.infra.texts.draw_text import DRAW_SUSPENSE_MESSAGES
from tests.helpers.uow import invoke_run_with_unit_of_work


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
async def test_start_draw_reports_if_already_run():
    message = build_message()
    bot = SimpleNamespace(id=1)

    with (
        patch(
            "friends_bot_service.draw.handlers.common.db.run_with_unit_of_work",
            new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
        ) as run_uow,
        patch(
            "friends_bot_service.draw.handlers.common._touch_bot_draw_attempt.execute",
            new=AsyncMock(),
        ) as touch_execute,
        patch(
            "friends_bot_service.draw.handlers.common._claim_draw.execute",
            new=AsyncMock(
                return_value=ClaimDrawResult(outcome=ClaimDrawOutcome.ALREADY_PLAYED)
            ),
        ) as claim_execute,
    ):
        await start_winner_draw(message, bot, "upd-1")

    assert run_uow.await_count == 2
    touch_execute.assert_awaited_once()
    claim_execute.assert_awaited_once()
    message.answer.assert_awaited_once_with(DRAW_ALREADY_PLAYED)


@pytest.mark.asyncio
async def test_start_draw_reports_if_no_draw_entrants():
    message = build_message()
    bot = SimpleNamespace(id=1)

    with (
        patch(
            "friends_bot_service.draw.handlers.common.db.run_with_unit_of_work",
            new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
        ),
        patch(
            "friends_bot_service.draw.handlers.common._touch_bot_draw_attempt.execute",
            new=AsyncMock(),
        ),
        patch(
            "friends_bot_service.draw.handlers.common._claim_draw.execute",
            new=AsyncMock(
                return_value=ClaimDrawResult(outcome=ClaimDrawOutcome.NO_DRAW_ENTRANTS)
            ),
        ) as claim_execute,
    ):
        await start_winner_draw(message, bot, "upd-1")

    claim_execute.assert_awaited_once()
    message.answer.assert_awaited_once_with(DRAW_NO_DRAW_ENTRANTS)


@pytest.mark.asyncio
@pytest.mark.parametrize("draw_type", [domain.DrawType.WINNER, domain.DrawType.LOSER])
async def test_start_draw_success_flow(draw_type: domain.DrawType):
    message = build_message()
    bot = SimpleNamespace(id=1)
    today = date.today()
    steps = DRAW_SUSPENSE_MESSAGES[draw_type][:-1]
    final_step = DRAW_SUSPENSE_MESSAGES[draw_type][-1] + "Test Name"

    claim_result = ClaimDrawResult(
        outcome=ClaimDrawOutcome.READY,
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
            "friends_bot_service.draw.handlers.common._touch_bot_draw_attempt.execute",
            new=AsyncMock(),
        ),
        patch(
            "friends_bot_service.draw.handlers.common._claim_draw.execute",
            new=AsyncMock(return_value=claim_result),
        ),
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
            if draw_type == domain.DrawType.WINNER
            else start_loser_draw
        )
        await handler(message, bot, "upd-1")

    assert run_uow.await_count == 2
    typing_mock.assert_called_once_with(chat_id=10, bot=bot, message_thread_id=None)
    assert sleep_mock.await_count == len(steps) + 1

    sent_messages = [call.args[0] for call in message.answer.await_args_list]
    assert sent_messages == [*steps, final_step]


@pytest.mark.asyncio
async def test_start_winner_draw_rejects_unregistered_user():
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=30)

    with (
        patch(
            "friends_bot_service.draw.handlers.common.db.run_with_unit_of_work",
            new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
        ),
        patch(
            "friends_bot_service.draw.handlers.common._touch_bot_draw_attempt.execute",
            new=AsyncMock(),
        ) as touch_execute,
        patch(
            "friends_bot_service.draw.handlers.common._claim_draw.execute",
            new=AsyncMock(
                return_value=ClaimDrawResult(outcome=ClaimDrawOutcome.NOT_REGISTERED)
            ),
        ) as claim_execute,
    ):
        await start_winner_draw(message, bot, "upd-1")

    touch_execute.assert_awaited_once()
    claim_execute.assert_awaited_once()
    message.answer.assert_awaited_once_with(DRAW_ENTRANT_NOT_IN_LIST)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler", "draw_type"),
    [
        (start_winner_draw, domain.DrawType.WINNER),
        (start_loser_draw, domain.DrawType.LOSER),
    ],
)
async def test_draw_command_starts_draw_for_registered_user(handler, draw_type):
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=30)
    today = date.today()
    steps = DRAW_SUSPENSE_MESSAGES[draw_type][:-1]
    final_step = DRAW_SUSPENSE_MESSAGES[draw_type][-1] + "Winner"

    claim_result = ClaimDrawResult(
        outcome=ClaimDrawOutcome.READY,
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
            "friends_bot_service.draw.handlers.common._touch_bot_draw_attempt.execute",
            new=AsyncMock(),
        ) as touch_execute,
        patch(
            "friends_bot_service.draw.handlers.common._claim_draw.execute",
            new=AsyncMock(return_value=claim_result),
        ) as claim_execute,
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
    claim_execute.assert_awaited_once()
