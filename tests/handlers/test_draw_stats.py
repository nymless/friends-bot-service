from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from friends_bot_service.draw import domain
from friends_bot_service.draw_stats import usecases
from friends_bot_service.draw_stats.domain import StatLine
from friends_bot_service.draw_stats.handlers.loser_stats import show_loser_statistics
from friends_bot_service.draw_stats.handlers.winner_stats import show_winner_statistics
from tests.helpers.uow import invoke_run_with_unit_of_work


def build_message(*, chat_id: int = 10, user_id: int | None = 20) -> AsyncMock:
    message = AsyncMock()
    message.chat.id = chat_id
    message.from_user = None if user_id is None else SimpleNamespace(id=user_id)
    return message


@pytest.mark.asyncio
async def test_show_statistics_reports_empty_leaderboard():
    message = build_message()

    with patch(
        "friends_bot_service.draw_stats.handlers.common.db.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ):
        with patch(
            "friends_bot_service.draw_stats.handlers.common._show_stats.execute"
        ) as show_stats:
            show_stats.return_value = usecases.ShowStatsResult(
                outcome=usecases.ShowStatsOutcome.EMPTY,
                message="Статистика пока пуста. Сначала сыграйте в игру!",
            )
            await show_winner_statistics(message, SimpleNamespace(id=1), "upd-1")

    show_stats.assert_awaited_once()
    message.answer.assert_awaited_once_with(
        "Статистика пока пуста. Сначала сыграйте в игру!"
    )


@pytest.mark.asyncio
async def test_show_statistics_formats_leaderboard_rows():
    message = build_message()
    lines = (StatLine("Alice", 5), StatLine("Bob", 3))

    with patch(
        "friends_bot_service.draw_stats.handlers.common.db.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ):
        with patch(
            "friends_bot_service.draw_stats.handlers.common._show_stats.execute"
        ) as show_stats:
            show_stats.return_value = usecases.ShowStatsResult(
                outcome=usecases.ShowStatsOutcome.SUCCESS,
                message="🎉 Результаты Красавчик Дня\n",
                lines=lines,
            )
            await show_winner_statistics(message, SimpleNamespace(id=1), "upd-1")

    message.answer.assert_awaited_once_with(
        "🎉 Результаты Красавчик Дня\n1) Alice — 5 раз(а)\n2) Bob — 3 раз(а)"
    )


@pytest.mark.asyncio
async def test_show_winner_statistics_returns_early_when_user_is_missing():
    message = build_message(user_id=None)
    bot = SimpleNamespace(id=1)

    with patch(
        "friends_bot_service.draw_stats.handlers.common.db.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ):
        with patch(
            "friends_bot_service.draw_stats.handlers.common._show_stats.execute"
        ) as show_stats:
            show_stats.return_value = usecases.ShowStatsResult(
                outcome=usecases.ShowStatsOutcome.USER_MISSING
            )
            await show_winner_statistics(message, bot, "upd-1")

    show_stats.assert_not_awaited()
    message.answer.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler", "game_type"),
    [
        (show_winner_statistics, domain.GameType.WINNER),
        (show_loser_statistics, domain.GameType.LOSER),
    ],
)
async def test_stats_commands_delegate_to_show_statistics(handler, game_type):
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=30)

    with patch(
        "friends_bot_service.draw_stats.handlers.common.db.run_with_unit_of_work",
        new=AsyncMock(side_effect=invoke_run_with_unit_of_work),
    ) as run_uow:
        with patch(
            "friends_bot_service.draw_stats.handlers.common._show_stats.execute"
        ) as show_stats:
            show_stats.return_value = usecases.ShowStatsResult(
                outcome=usecases.ShowStatsOutcome.EMPTY
            )
            await handler(message, bot, "upd-1")

    run_uow.assert_awaited_once()
    show_stats.assert_awaited_once()
    data = show_stats.await_args.args[0]
    assert data.bot_id == 30
    assert data.chat_id == 10
    assert data.game_type == game_type
