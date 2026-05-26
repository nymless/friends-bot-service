from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from friends_bot_service.draw.domain import GameType
from friends_bot_service.draw.usecases.run_draw import (
    PrepareDraw,
    PrepareDrawData,
    PrepareDrawOutcome,
    RecordDraw,
    RecordDrawData,
    TouchBotGameAttempt,
)
from friends_bot_service.infra.texts.game_text import WINNER_MESSAGES
from tests.usecases.factories import draw_entrant, registered_draw_entrant


@pytest.mark.asyncio
async def test_prepare_draw_returns_not_registered_when_entrant_is_missing():
    draw_entrant_repo = AsyncMock()
    draw_entrant_repo.get = AsyncMock(return_value=None)
    draw_repo = AsyncMock()
    use_case = PrepareDraw()

    result = await use_case.execute(
        PrepareDrawData(
            bot_id=1,
            chat_id=10,
            user_id=100,
            game_type=GameType.WINNER,
        ),
        draw_entrant_repo,
        draw_repo,
    )

    assert result.outcome is PrepareDrawOutcome.NOT_REGISTERED
    draw_repo.has_draw_today.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_draw_returns_not_registered_when_entrant_is_inactive():
    draw_entrant_repo = AsyncMock()
    draw_entrant_repo.get = AsyncMock(
        return_value=registered_draw_entrant(user_id=100, is_active=False)
    )
    draw_repo = AsyncMock()
    use_case = PrepareDraw()

    result = await use_case.execute(
        PrepareDrawData(
            bot_id=1,
            chat_id=10,
            user_id=100,
            game_type=GameType.WINNER,
        ),
        draw_entrant_repo,
        draw_repo,
    )

    assert result.outcome is PrepareDrawOutcome.NOT_REGISTERED


@pytest.mark.asyncio
async def test_prepare_draw_returns_already_played_when_draw_exists_today():
    draw_entrant_repo = AsyncMock()
    draw_entrant_repo.get = AsyncMock(
        return_value=registered_draw_entrant(user_id=100, is_active=True)
    )
    draw_repo = AsyncMock()
    draw_repo.has_draw_today = AsyncMock(return_value=True)
    use_case = PrepareDraw()

    result = await use_case.execute(
        PrepareDrawData(
            bot_id=1,
            chat_id=10,
            user_id=100,
            game_type=GameType.WINNER,
        ),
        draw_entrant_repo,
        draw_repo,
    )

    assert result.outcome is PrepareDrawOutcome.ALREADY_PLAYED
    draw_repo.list_eligible_players.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_draw_returns_no_players_when_eligible_list_is_empty():
    draw_entrant_repo = AsyncMock()
    draw_entrant_repo.get = AsyncMock(
        return_value=registered_draw_entrant(user_id=100, is_active=True)
    )
    draw_repo = AsyncMock()
    draw_repo.has_draw_today = AsyncMock(return_value=False)
    draw_repo.list_eligible_players = AsyncMock(return_value=[])
    use_case = PrepareDraw()

    result = await use_case.execute(
        PrepareDrawData(
            bot_id=1,
            chat_id=10,
            user_id=100,
            game_type=GameType.LOSER,
        ),
        draw_entrant_repo,
        draw_repo,
    )

    assert result.outcome is PrepareDrawOutcome.NO_PLAYERS


@pytest.mark.asyncio
async def test_prepare_draw_returns_ready_with_winner_messages():
    draw_entrant_repo = AsyncMock()
    draw_entrant_repo.get = AsyncMock(
        return_value=registered_draw_entrant(user_id=100, is_active=True)
    )
    draw_repo = AsyncMock()
    draw_repo.has_draw_today = AsyncMock(return_value=False)
    winner = draw_entrant(user_id=777, full_name="Winner Name")
    draw_repo.list_eligible_players = AsyncMock(return_value=[winner])
    use_case = PrepareDraw()
    fixed_today = date(2026, 5, 27)

    with (
        patch(
            "friends_bot_service.draw.usecases.run_draw.random.choice",
            return_value=winner,
        ),
        patch(
            "friends_bot_service.draw.usecases.run_draw.datetime",
        ) as datetime_mock,
    ):
        datetime_mock.now.return_value.date.return_value = fixed_today

        result = await use_case.execute(
            PrepareDrawData(
                bot_id=1,
                chat_id=10,
                user_id=100,
                game_type=GameType.WINNER,
            ),
            draw_entrant_repo,
            draw_repo,
        )

    steps = WINNER_MESSAGES[GameType.WINNER][:-1]
    final_step = WINNER_MESSAGES[GameType.WINNER][-1] + "Winner Name"

    assert result.outcome is PrepareDrawOutcome.READY
    assert result.suspense_messages == tuple(steps)
    assert result.final_message == final_step
    assert result.winner_user_id == 777
    assert result.today_utc == fixed_today


@pytest.mark.asyncio
async def test_record_draw_persists_result():
    draw_repo = AsyncMock()
    use_case = RecordDraw()
    today = date(2026, 5, 27)
    data = RecordDrawData(
        bot_id=1,
        chat_id=10,
        winner_user_id=777,
        game_type=GameType.LOSER,
        today_utc=today,
    )

    await use_case.execute(data, draw_repo)

    draw_repo.record_draw_result.assert_awaited_once_with(
        1,
        10,
        777,
        GameType.LOSER,
        today,
    )


@pytest.mark.asyncio
async def test_touch_bot_game_attempt_updates_bot_timestamp():
    bot_repo = AsyncMock()
    use_case = TouchBotGameAttempt()

    await use_case.execute(99, bot_repo)

    bot_repo.touch_last_game_attempt.assert_awaited_once_with(99)
