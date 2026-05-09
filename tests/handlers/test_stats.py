from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from friends_bot_service.enums.enums import GameType
from friends_bot_service.handlers.stats import (
    show_loser_statistics,
    show_statistics,
    show_winner_statistics,
)


def build_message(*, chat_id: int = 10, user_id: int | None = 20) -> AsyncMock:
    """Builds a minimal aiogram message mock for stats handler tests."""

    message = AsyncMock()
    message.chat.id = chat_id
    message.from_user = None if user_id is None else SimpleNamespace(id=user_id)
    return message


@pytest.mark.asyncio
async def test_show_statistics_reports_empty_leaderboard():
    """
    Verify show_statistics behavior when the leaderboard is empty.

    Scenario:
    - repository returns no leaderboard rows for the selected game type

    Expected behavior:
    - the handler answers with the empty-statistics message
    """

    # Prepare a plain statistics request.
    message = build_message()
    session = AsyncMock()

    # Simulate an empty leaderboard in the repository.
    with patch(
        "friends_bot_service.handlers.stats.stats_repo.get_top_stats",
        new=AsyncMock(return_value=[]),
    ) as get_top_stats:
        await show_statistics(message, session, 1, 10, GameType.WINNER)

    # The handler must query once and answer with the fallback text.
    get_top_stats.assert_awaited_once_with(session, 1, 10, GameType.WINNER)
    message.answer.assert_awaited_once_with(
        "Статистика пока пуста. Сначала сыграйте в игру!"
    )


@pytest.mark.asyncio
async def test_show_statistics_formats_leaderboard_rows():
    """
    Verify show_statistics formatting for a non-empty leaderboard.

    Scenario:
    - repository returns multiple leaderboard rows

    Expected behavior:
    - the handler formats them as a numbered list
    - the title for the requested game type is prepended
    """

    # Prepare a plain statistics request.
    message = build_message()
    session = AsyncMock()
    leaderboard = [("Alice", 5), ("Bob", 3)]

    # Simulate a filled leaderboard in the repository.
    with patch(
        "friends_bot_service.handlers.stats.stats_repo.get_top_stats",
        new=AsyncMock(return_value=leaderboard),
    ):
        await show_statistics(message, session, 1, 10, GameType.WINNER)

    # The handler must answer with the numbered leaderboard text.
    message.answer.assert_awaited_once_with(
        "🎉 Результаты Красавчик Дня\n1) Alice — 5 раз(а)\n2) Bob — 3 раз(а)"
    )


@pytest.mark.asyncio
async def test_show_winner_statistics_returns_early_when_user_is_missing():
    """
    Verify winner statistics early-exit branch when from_user is missing.

    Scenario:
    - the /stats handler is called
    - the incoming message has no from_user

    Expected behavior:
    - nested statistics rendering is not called
    - no response message is sent
    """

    # Prepare a message without Telegram user data.
    message = build_message(user_id=None)
    bot = SimpleNamespace(id=1)
    session = AsyncMock()

    # Guard against any unintended nested rendering.
    with patch(
        "friends_bot_service.handlers.stats.show_statistics",
        new=AsyncMock(),
    ) as show_statistics_mock:
        await show_winner_statistics(message, bot, session, "upd-1")

    # The handler must stop without delegating further.
    show_statistics_mock.assert_not_awaited()
    message.answer.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler", "game_type"),
    [
        (show_winner_statistics, GameType.WINNER),
        (show_loser_statistics, GameType.LOSER),
    ],
)
async def test_stats_commands_delegate_to_show_statistics(handler, game_type):
    """
    Verify command handlers delegate to show_statistics with the correct game type.

    Scenario:
    - a valid user calls either /stats or /loserstats

    Expected behavior:
    - show_statistics is called once with correct bot, chat and game type
    """

    # Prepare a valid statistics request.
    message = build_message(chat_id=10, user_id=20)
    bot = SimpleNamespace(id=30)
    session = AsyncMock()

    # Intercept the nested rendering function.
    with patch(
        "friends_bot_service.handlers.stats.show_statistics",
        new=AsyncMock(),
    ) as show_statistics_mock:
        await handler(message, bot, session, "upd-1")

    # The wrapper handler must pass control to show_statistics with correct arguments.
    show_statistics_mock.assert_awaited_once_with(message, session, 30, 10, game_type)
