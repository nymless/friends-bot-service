from collections.abc import Sequence
from datetime import date
from typing import Protocol

from friends_bot_service.domain import GameType, Player


class GameRepository(Protocol):
    async def has_draw_today(
        self,
        bot_id: int,
        chat_id: int,
        game_type: GameType,
        today: date,
    ) -> bool: ...

    async def list_eligible_players(
        self,
        bot_id: int,
        chat_id: int,
        today: date,
    ) -> Sequence[Player]: ...

    async def record_draw_result(
        self,
        bot_id: int,
        chat_id: int,
        winner_user_id: int,
        game_type: GameType,
        today: date,
    ) -> None: ...
