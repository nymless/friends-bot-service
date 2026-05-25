from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from friends_bot_service.domain import RegisteredBot


class BotRepository(Protocol):
    async def upsert(
        self,
        bot_id: int,
        username: str,
        encrypted_token: str,
        owner_id: int,
    ) -> RegisteredBot: ...

    async def deactivate_for_owner(self, bot_id: int, owner_id: int) -> bool: ...

    async def touch_last_game_attempt(self, bot_id: int) -> None: ...

    async def deactivate_stale(self, cutoff: datetime) -> Sequence[tuple[int, str]]: ...

    async def list_all_active(self) -> Sequence[RegisteredBot]: ...

    async def list_active_for_owner(self, owner_id: int) -> Sequence[RegisteredBot]: ...

    async def get_active_for_owner(
        self,
        owner_id: int,
        bot_id: int,
    ) -> RegisteredBot | None: ...
