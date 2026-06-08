from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from friends_bot_service.draw.domain import DrawType
from friends_bot_service.draw.usecases.run_draw import (
    ClaimDraw,
    ClaimDrawData,
    ClaimDrawOutcome,
    DrawAlreadyClaimedError,
    TouchBotDrawAttempt,
)
from friends_bot_service.infra.texts.draw_text import DRAW_SUSPENSE_MESSAGES
from tests.usecases.factories import draw_entrant, registered_draw_entrant


@pytest.mark.asyncio
async def test_claim_draw_returns_not_registered_when_entrant_is_missing():
    draw_entrant_repo = AsyncMock()
    draw_entrant_repo.get = AsyncMock(return_value=None)
    draw_repo = AsyncMock()
    use_case = ClaimDraw()

    result = await use_case.execute(
        ClaimDrawData(
            bot_id=1,
            chat_id=10,
            user_id=100,
            draw_type=DrawType.WINNER,
        ),
        draw_entrant_repo,
        draw_repo,
    )

    assert result.outcome is ClaimDrawOutcome.NOT_REGISTERED
    draw_repo.has_claim_today.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_draw_returns_not_registered_when_entrant_is_inactive():
    draw_entrant_repo = AsyncMock()
    draw_entrant_repo.get = AsyncMock(
        return_value=registered_draw_entrant(user_id=100, is_active=False)
    )
    draw_repo = AsyncMock()
    use_case = ClaimDraw()

    result = await use_case.execute(
        ClaimDrawData(
            bot_id=1,
            chat_id=10,
            user_id=100,
            draw_type=DrawType.WINNER,
        ),
        draw_entrant_repo,
        draw_repo,
    )

    assert result.outcome is ClaimDrawOutcome.NOT_REGISTERED


@pytest.mark.asyncio
async def test_claim_draw_returns_already_played_when_claim_exists_today():
    draw_entrant_repo = AsyncMock()
    draw_entrant_repo.get = AsyncMock(
        return_value=registered_draw_entrant(user_id=100, is_active=True)
    )
    draw_repo = AsyncMock()
    draw_repo.has_claim_today = AsyncMock(return_value=True)
    use_case = ClaimDraw()

    result = await use_case.execute(
        ClaimDrawData(
            bot_id=1,
            chat_id=10,
            user_id=100,
            draw_type=DrawType.WINNER,
        ),
        draw_entrant_repo,
        draw_repo,
    )

    assert result.outcome is ClaimDrawOutcome.ALREADY_PLAYED
    draw_repo.list_eligible_draw_entrants.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_draw_raises_when_claim_insert_races():
    draw_entrant_repo = AsyncMock()
    draw_entrant_repo.get = AsyncMock(
        return_value=registered_draw_entrant(user_id=100, is_active=True)
    )
    draw_repo = AsyncMock()
    draw_repo.has_claim_today = AsyncMock(return_value=False)
    draw_repo.list_eligible_draw_entrants = AsyncMock(
        return_value=[draw_entrant(user_id=777, full_name="Winner Name")]
    )
    draw_repo.claim_draw = AsyncMock(
        side_effect=IntegrityError("insert", {}, Exception("duplicate"))
    )
    use_case = ClaimDraw()

    with pytest.raises(DrawAlreadyClaimedError):
        await use_case.execute(
            ClaimDrawData(
                bot_id=1,
                chat_id=10,
                user_id=100,
                draw_type=DrawType.WINNER,
            ),
            draw_entrant_repo,
            draw_repo,
        )


@pytest.mark.asyncio
async def test_claim_draw_returns_no_draw_entrants_when_eligible_list_is_empty():
    draw_entrant_repo = AsyncMock()
    draw_entrant_repo.get = AsyncMock(
        return_value=registered_draw_entrant(user_id=100, is_active=True)
    )
    draw_repo = AsyncMock()
    draw_repo.has_claim_today = AsyncMock(return_value=False)
    draw_repo.list_eligible_draw_entrants = AsyncMock(return_value=[])
    use_case = ClaimDraw()

    result = await use_case.execute(
        ClaimDrawData(
            bot_id=1,
            chat_id=10,
            user_id=100,
            draw_type=DrawType.LOSER,
        ),
        draw_entrant_repo,
        draw_repo,
    )

    assert result.outcome is ClaimDrawOutcome.NO_DRAW_ENTRANTS


@pytest.mark.asyncio
async def test_claim_draw_returns_ready_after_persisting_result():
    draw_entrant_repo = AsyncMock()
    draw_entrant_repo.get = AsyncMock(
        return_value=registered_draw_entrant(user_id=100, is_active=True)
    )
    draw_repo = AsyncMock()
    draw_repo.has_claim_today = AsyncMock(return_value=False)
    winner = draw_entrant(user_id=777, full_name="Winner Name")
    draw_repo.list_eligible_draw_entrants = AsyncMock(return_value=[winner])
    draw_repo.claim_draw = AsyncMock()
    use_case = ClaimDraw()
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
            ClaimDrawData(
                bot_id=1,
                chat_id=10,
                user_id=100,
                draw_type=DrawType.WINNER,
            ),
            draw_entrant_repo,
            draw_repo,
        )

    steps = DRAW_SUSPENSE_MESSAGES[DrawType.WINNER][:-1]
    final_step = DRAW_SUSPENSE_MESSAGES[DrawType.WINNER][-1] + "Winner Name"

    assert result.outcome is ClaimDrawOutcome.READY
    assert result.suspense_messages == tuple(steps)
    assert result.final_message == final_step
    assert result.winner_user_id == 777
    assert result.today_utc == fixed_today
    draw_repo.claim_draw.assert_awaited_once_with(
        1,
        10,
        777,
        DrawType.WINNER,
        fixed_today,
    )


@pytest.mark.asyncio
async def test_touch_bot_draw_attempt_updates_bot_timestamp():
    bot_repo = AsyncMock()
    use_case = TouchBotDrawAttempt()

    await use_case.execute(99, bot_repo)

    bot_repo.touch_last_draw_attempt.assert_awaited_once_with(99)
