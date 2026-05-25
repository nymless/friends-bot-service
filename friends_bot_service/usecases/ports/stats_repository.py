from collections.abc import Sequence
from typing import Protocol

from friends_bot_service.domain import GameType, StatLine


class StatsRepository(Protocol):
    async def top_for_chat(
        self,
        bot_id: int,
        chat_id: int,
        game_type: GameType,
    ) -> Sequence[StatLine]: ...
