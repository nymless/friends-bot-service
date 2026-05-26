import random
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import StrEnum

from friends_bot_service.bot_admin.interfaces import BotRepository
from friends_bot_service.draw.domain import GameType
from friends_bot_service.draw.interfaces import DrawRepository
from friends_bot_service.draw_entrant.domain import DrawEntrantKey
from friends_bot_service.draw_entrant.interfaces import DrawEntrantRepository
from friends_bot_service.infra.core.lock import get_bot_chat_lock
from friends_bot_service.infra.texts.game_text import WINNER_MESSAGES


class PrepareDrawOutcome(StrEnum):
    ALREADY_PLAYED = "already_played"
    NO_PLAYERS = "no_players"
    READY = "ready"
    NOT_REGISTERED = "not_registered"


@dataclass(frozen=True, slots=True)
class PrepareDrawData:
    bot_id: int
    chat_id: int
    user_id: int
    game_type: GameType


@dataclass(frozen=True, slots=True)
class PrepareDrawResult:
    outcome: PrepareDrawOutcome
    suspense_messages: tuple[str, ...] = ()
    final_message: str | None = None
    winner_user_id: int | None = None
    today_utc: date | None = None


class PrepareDraw:
    async def execute(
        self,
        data: PrepareDrawData,
        draw_entrant: DrawEntrantRepository,
        draw: DrawRepository,
    ) -> PrepareDrawResult:
        key = DrawEntrantKey(
            bot_id=data.bot_id,
            chat_id=data.chat_id,
            user_id=data.user_id,
        )
        participant = await draw_entrant.get(key)
        if participant is None or not participant.is_active:
            return PrepareDrawResult(outcome=PrepareDrawOutcome.NOT_REGISTERED)

        lock = get_bot_chat_lock((data.bot_id, data.chat_id))
        async with lock:
            today_utc = datetime.now(timezone.utc).date()

            if await draw.has_draw_today(
                data.bot_id,
                data.chat_id,
                data.game_type,
                today_utc,
            ):
                return PrepareDrawResult(outcome=PrepareDrawOutcome.ALREADY_PLAYED)

            eligible = await draw.list_eligible_players(
                data.bot_id,
                data.chat_id,
                today_utc,
            )
            if not eligible:
                return PrepareDrawResult(outcome=PrepareDrawOutcome.NO_PLAYERS)

            winner = random.choice(list(eligible))
            steps = WINNER_MESSAGES[data.game_type][:-1]
            final_step = WINNER_MESSAGES[data.game_type][-1] + winner.full_name

            return PrepareDrawResult(
                outcome=PrepareDrawOutcome.READY,
                suspense_messages=tuple(steps),
                final_message=final_step,
                winner_user_id=winner.user_id,
                today_utc=today_utc,
            )


@dataclass(frozen=True, slots=True)
class RecordDrawData:
    bot_id: int
    chat_id: int
    winner_user_id: int
    game_type: GameType
    today_utc: date


class RecordDraw:
    async def execute(
        self,
        data: RecordDrawData,
        draw: DrawRepository,
    ) -> None:
        await draw.record_draw_result(
            data.bot_id,
            data.chat_id,
            data.winner_user_id,
            data.game_type,
            data.today_utc,
        )


class TouchBotGameAttempt:
    async def execute(self, bot_id: int, bot: BotRepository) -> None:
        await bot.touch_last_game_attempt(bot_id)
