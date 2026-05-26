from unittest.mock import AsyncMock

import pytest

from friends_bot_service.draw.domain import GameType
from friends_bot_service.draw_stats.domain import StatLine
from friends_bot_service.draw_stats.usecases.show_stats import (
    ShowStats,
    ShowStatsData,
    ShowStatsOutcome,
)
from friends_bot_service.infra.texts import stats_text


@pytest.mark.asyncio
async def test_show_stats_returns_user_missing_when_user_id_is_none():
    stats_repo = AsyncMock()
    use_case = ShowStats()

    result = await use_case.execute(
        ShowStatsData(
            bot_id=1,
            chat_id=10,
            user_id=None,
            game_type=GameType.WINNER,
        ),
        stats_repo,
    )

    assert result.outcome is ShowStatsOutcome.USER_MISSING
    stats_repo.top_for_chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_show_stats_returns_empty_message_when_no_rows():
    stats_repo = AsyncMock()
    stats_repo.top_for_chat = AsyncMock(return_value=[])
    use_case = ShowStats()

    result = await use_case.execute(
        ShowStatsData(
            bot_id=1,
            chat_id=10,
            user_id=100,
            game_type=GameType.LOSER,
        ),
        stats_repo,
    )

    assert result.outcome is ShowStatsOutcome.EMPTY
    assert result.message == stats_text.STATS_EMPTY_MESSAGE


@pytest.mark.asyncio
async def test_show_stats_returns_title_and_leaderboard_rows():
    stats_repo = AsyncMock()
    rows = (StatLine(full_name="Alice", count=5), StatLine(full_name="Bob", count=3))
    stats_repo.top_for_chat = AsyncMock(return_value=rows)
    use_case = ShowStats()

    result = await use_case.execute(
        ShowStatsData(
            bot_id=1,
            chat_id=10,
            user_id=100,
            game_type=GameType.WINNER,
        ),
        stats_repo,
    )

    assert result.outcome is ShowStatsOutcome.SUCCESS
    assert result.message == stats_text.STATS_MESSAGES[GameType.WINNER]
    assert result.lines == rows
    stats_repo.top_for_chat.assert_awaited_once_with(1, 10, GameType.WINNER)
