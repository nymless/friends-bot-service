import random
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import StrEnum

from friends_bot_service.core.lock import get_bot_chat_lock
from friends_bot_service.domain import GameType, PlayerKey
from friends_bot_service.texts.game_text import WINNER_MESSAGES
from friends_bot_service.usecases.ports import (
    BotRepository,
    GameRepository,
    UserRepository,
)


class PrepareDrawOutcome(StrEnum):
    ALREADY_PLAYED = "already_played"
    NO_PLAYERS = "no_players"
    READY = "ready"
    NOT_REGISTERED = "not_registered"


@dataclass(frozen=True, slots=True)
class PrepareDrawCommand:
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


@dataclass(frozen=True, slots=True)
class RecordDrawCommand:
    bot_id: int
    chat_id: int
    winner_user_id: int
    game_type: GameType
    today_utc: date


class PrepareDraw:
    async def execute(
        self,
        command: PrepareDrawCommand,
        users: UserRepository,
        games: GameRepository,
    ) -> PrepareDrawResult:
        key = PlayerKey(
            bot_id=command.bot_id,
            chat_id=command.chat_id,
            user_id=command.user_id,
        )
        player = await users.get(key)
        if player is None:
            return PrepareDrawResult(outcome=PrepareDrawOutcome.NOT_REGISTERED)

        lock = get_bot_chat_lock((command.bot_id, command.chat_id))
        async with lock:
            today_utc = datetime.now(timezone.utc).date()

            if await games.has_draw_today(
                command.bot_id,
                command.chat_id,
                command.game_type,
                today_utc,
            ):
                return PrepareDrawResult(outcome=PrepareDrawOutcome.ALREADY_PLAYED)

            players = await games.list_eligible_players(
                command.bot_id,
                command.chat_id,
                today_utc,
            )
            if not players:
                return PrepareDrawResult(outcome=PrepareDrawOutcome.NO_PLAYERS)

            winner = random.choice(list(players))
            steps = WINNER_MESSAGES[command.game_type][:-1]
            final_step = WINNER_MESSAGES[command.game_type][-1] + winner.full_name

            return PrepareDrawResult(
                outcome=PrepareDrawOutcome.READY,
                suspense_messages=tuple(steps),
                final_message=final_step,
                winner_user_id=winner.user_id,
                today_utc=today_utc,
            )


class RecordDraw:
    async def execute(
        self,
        command: RecordDrawCommand,
        games: GameRepository,
    ) -> None:
        await games.record_draw_result(
            command.bot_id,
            command.chat_id,
            command.winner_user_id,
            command.game_type,
            command.today_utc,
        )


class TouchBotGameAttempt:
    async def execute(self, bot_id: int, bots: BotRepository) -> None:
        await bots.touch_last_game_attempt(bot_id)
