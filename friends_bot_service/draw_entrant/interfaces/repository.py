from collections.abc import Sequence
from typing import Protocol

from friends_bot_service.draw_entrant.domain import (
    DrawEntrant,
    DrawEntrantKey,
    RegisteredDrawEntrant,
)


class DrawEntrantRepository(Protocol):
    async def get(self, key: DrawEntrantKey) -> RegisteredDrawEntrant | None: ...

    async def list_active_for_chat(
        self, bot_id: int, chat_id: int
    ) -> Sequence[RegisteredDrawEntrant]: ...

    async def upsert_active(
        self, draw_entrant: DrawEntrant
    ) -> RegisteredDrawEntrant: ...

    async def save(self, draw_entrant: RegisteredDrawEntrant) -> None: ...
