from collections.abc import Sequence
from typing import Protocol

from friends_bot_service.domain import Player, PlayerKey


class UserRepository(Protocol):
    async def get(self, key: PlayerKey) -> Player | None: ...

    async def list_active_for_chat(
        self, bot_id: int, chat_id: int
    ) -> Sequence[Player]: ...

    async def upsert_active(
        self,
        bot_id: int,
        chat_id: int,
        user_id: int,
        username: str | None,
        full_name: str,
    ) -> Player: ...

    async def save(self, player: Player) -> None: ...
