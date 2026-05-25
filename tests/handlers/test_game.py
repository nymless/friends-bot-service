import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from friends_bot_service.domain import GameType
from friends_bot_service.handlers.game import start_loser_game, start_winner_game
from friends_bot_service.texts.game_text import WINNER_MESSAGES
from friends_bot_service.usecases.game.run_draw import (
    PrepareDrawOutcome,
    PrepareDrawResult,
)
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
async def test_start_game_reports_if_already_run():
    message = build_message()
    bot = SimpleNamespace(id=1)

    with (
        patch(
            "friends_bot_service.handlers.game.run_with_unit_of_work",
            new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
        ) as run_uow,
        patch(
            "friends_bot_service.handlers.game._touch_bot_game_attempt.execute",
            new=AsyncMock(),
        ) as touch_execute,
        patch(
            "friends_bot_service.handlers.game._prepare_draw.execute",
            new=AsyncMock(
                return_value=PrepareDrawResult(
                    outcome=PrepareDrawOutcome.ALREADY_PLAYED
                )
            ),
        ) as prepare_execute,
        patch(
            "friends_bot_service.handlers.game._record_draw.execute",
            new=AsyncMock(),
        ) as record_execute,
    ):
        await start_winner_game(message, bot, "upd-1")

    run_uow.assert_awaited_once()
    touch_execute.assert_awaited_once()
    prepare_execute.assert_awaited_once()
    record_execute.assert_not_awaited()
    message.answer.assert_awaited_once_with("Сегодня выбор уже сделан!")


@pytest.mark.asyncio
async def test_start_game_reports_if_no_players():
    message = build_message()
    bot = SimpleNamespace(id=1)

    with (
        patch(
            "friends_bot_service.handlers.game.run_with_unit_of_work",
            new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
        ),
        patch(
            "friends_bot_service.handlers.game._touch_bot_game_attempt.execute",
            new=AsyncMock(),
        ),
        patch(
            "friends_bot_service.handlers.game._prepare_draw.execute",
            new=AsyncMock(
                return_value=PrepareDrawResult(outcome=PrepareDrawOutcome.NO_PLAYERS)
            ),
        ) as prepare_execute,
        patch(
            "friends_bot_service.handlers.game._record_draw.execute",
            new=AsyncMock(),
        ) as record_execute,
    ):
        await start_winner_game(message, bot, "upd-1")

    prepare_execute.assert_awaited_once()
    record_execute.assert_not_awaited()
    message.answer.assert_awaited_once_with("Никто не зарегистрировался!")


@pytest.mark.asyncio
@pytest.mark.parametrize("game_type", [GameType.WINNER, GameType.LOSER])
async def test_start_game_success_flow(game_type: GameType):
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
            "friends_bot_service.handlers.game.run_with_unit_of_work",
            new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
        ) as run_uow,
        patch(
            "friends_bot_service.handlers.game._touch_bot_game_attempt.execute",
            new=AsyncMock(),
        ),
        patch(
            "friends_bot_service.handlers.game._prepare_draw.execute",
            new=AsyncMock(return_value=prepare_result),
        ),
        patch(
            "friends_bot_service.handlers.game._record_draw.execute",
            new=AsyncMock(),
        ) as record_execute,
        patch(
            "friends_bot_service.handlers.game.ChatActionSender.typing",
            return_value=DummyTypingContext(),
        ) as typing_mock,
        patch(
            "friends_bot_service.handlers.game.asyncio.sleep",
            new=AsyncMock(),
        ) as sleep_mock,
    ):
        handler = (
            start_winner_game if game_type == GameType.WINNER else start_loser_game
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
            "friends_bot_service.handlers.game.run_with_unit_of_work",
            new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
        ),
        patch(
            "friends_bot_service.handlers.game._touch_bot_game_attempt.execute",
            new=AsyncMock(),
        ) as touch_execute,
        patch(
            "friends_bot_service.handlers.game._prepare_draw.execute",
            new=AsyncMock(
                return_value=PrepareDrawResult(
                    outcome=PrepareDrawOutcome.NOT_REGISTERED
                )
            ),
        ) as prepare_execute,
        patch(
            "friends_bot_service.handlers.game._record_draw.execute",
            new=AsyncMock(),
        ) as record_execute,
    ):
        await start_winner_game(message, bot, "upd-1")

    touch_execute.assert_awaited_once()
    prepare_execute.assert_awaited_once()
    record_execute.assert_not_awaited()
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
            "friends_bot_service.handlers.game.run_with_unit_of_work",
            new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
        ) as run_uow,
        patch(
            "friends_bot_service.handlers.game._touch_bot_game_attempt.execute",
            new=AsyncMock(),
        ) as touch_execute,
        patch(
            "friends_bot_service.handlers.game._prepare_draw.execute",
            new=AsyncMock(return_value=prepare_result),
        ) as prepare_execute,
        patch(
            "friends_bot_service.handlers.game._record_draw.execute",
            new=AsyncMock(),
        ) as record_execute,
        patch(
            "friends_bot_service.handlers.game.ChatActionSender.typing",
            return_value=DummyTypingContext(),
        ),
        patch(
            "friends_bot_service.handlers.game.asyncio.sleep",
            new=AsyncMock(),
        ),
    ):
        await handler(message, bot, "upd-1")

    assert run_uow.await_count == 2
    touch_execute.assert_awaited_once()
    prepare_execute.assert_awaited_once()
    record_execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_game_serializes_parallel_calls_for_same_bot_and_chat():
    message_one = build_message(chat_id=10, user_id=20)
    message_two = build_message(chat_id=10, user_id=21)
    bot = SimpleNamespace(id=1)
    today = date.today()
    state = {"has_played": False}

    async def fake_prepare(*args, **kwargs):
        if state["has_played"]:
            return PrepareDrawResult(outcome=PrepareDrawOutcome.ALREADY_PLAYED)

        state["has_played"] = True
        return PrepareDrawResult(
            outcome=PrepareDrawOutcome.READY,
            suspense_messages=tuple(WINNER_MESSAGES[GameType.WINNER][:-1]),
            final_message=WINNER_MESSAGES[GameType.WINNER][-1] + "Winner",
            winner_user_id=777,
            today_utc=today,
        )

    with (
        patch(
            "friends_bot_service.handlers.game.run_with_unit_of_work",
            new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
        ) as run_uow,
        patch(
            "friends_bot_service.handlers.game._touch_bot_game_attempt.execute",
            new=AsyncMock(),
        ),
        patch(
            "friends_bot_service.handlers.game._prepare_draw.execute",
            new=AsyncMock(side_effect=fake_prepare),
        ) as prepare_execute,
        patch(
            "friends_bot_service.handlers.game._record_draw.execute",
            new=AsyncMock(),
        ) as record_execute,
        patch(
            "friends_bot_service.handlers.game.ChatActionSender.typing",
            return_value=DummyTypingContext(),
        ),
        patch(
            "friends_bot_service.handlers.game.asyncio.sleep",
            new=AsyncMock(),
        ),
    ):
        await asyncio.gather(
            start_winner_game(message_one, bot, "upd-1"),
            start_winner_game(message_two, bot, "upd-2"),
        )

    assert prepare_execute.await_count == 2
    assert record_execute.await_count == 1
    assert run_uow.await_count == 3

    answers = [
        call.args[0]
        for call in message_one.answer.await_args_list
        + message_two.answer.await_args_list
    ]
    assert answers.count("Сегодня выбор уже сделан!") == 1
