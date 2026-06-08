import random
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import StrEnum

from sqlalchemy.exc import IntegrityError

from friends_bot_service.bot_admin.interfaces import BotRepository
from friends_bot_service.draw.domain import DrawType
from friends_bot_service.draw.interfaces import DrawRepository
from friends_bot_service.draw_entrant.domain import DrawEntrantKey
from friends_bot_service.draw_entrant.interfaces import DrawEntrantRepository
from friends_bot_service.infra.texts.draw_text import DRAW_SUSPENSE_MESSAGES


class ClaimDrawOutcome(StrEnum):
    ALREADY_PLAYED = "already_played"
    NO_DRAW_ENTRANTS = "no_draw_entrants"
    READY = "ready"
    NOT_REGISTERED = "not_registered"


@dataclass(frozen=True, slots=True)
class ClaimDrawData:
    bot_id: int
    chat_id: int
    user_id: int
    draw_type: DrawType


@dataclass(frozen=True, slots=True)
class ClaimDrawResult:
    outcome: ClaimDrawOutcome
    suspense_messages: tuple[str, ...] = ()
    final_message: str | None = None
    winner_user_id: int | None = None
    today_utc: date | None = None


class DrawAlreadyClaimedError(Exception):
    """Raised when another process already claimed today's draw."""


class ClaimDraw:
    async def execute(
        self,
        data: ClaimDrawData,
        draw_entrant: DrawEntrantRepository,
        draw: DrawRepository,
    ) -> ClaimDrawResult:
        key = DrawEntrantKey(
            bot_id=data.bot_id,
            chat_id=data.chat_id,
            user_id=data.user_id,
        )
        participant = await draw_entrant.get(key)
        if participant is None or not participant.is_active:
            return ClaimDrawResult(outcome=ClaimDrawOutcome.NOT_REGISTERED)

        today_utc = datetime.now(timezone.utc).date()

        if await draw.has_claim_today(
            data.bot_id,
            data.chat_id,
            data.draw_type,
            today_utc,
        ):
            return ClaimDrawResult(outcome=ClaimDrawOutcome.ALREADY_PLAYED)

        eligible = await draw.list_eligible_draw_entrants(
            data.bot_id,
            data.chat_id,
            today_utc,
        )
        if not eligible:
            return ClaimDrawResult(outcome=ClaimDrawOutcome.NO_DRAW_ENTRANTS)

        winner = random.choice(list(eligible))
        try:
            await draw.claim_draw(
                data.bot_id,
                data.chat_id,
                winner.user_id,
                data.draw_type,
                today_utc,
            )
        except IntegrityError as exc:
            raise DrawAlreadyClaimedError from exc

        steps = DRAW_SUSPENSE_MESSAGES[data.draw_type][:-1]
        final_step = DRAW_SUSPENSE_MESSAGES[data.draw_type][-1] + winner.full_name

        return ClaimDrawResult(
            outcome=ClaimDrawOutcome.READY,
            suspense_messages=tuple(steps),
            final_message=final_step,
            winner_user_id=winner.user_id,
            today_utc=today_utc,
        )


class TouchBotDrawAttempt:
    async def execute(self, bot_id: int, bot: BotRepository) -> None:
        await bot.touch_last_draw_attempt(bot_id)
