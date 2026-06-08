from collections.abc import Sequence
from datetime import date
from typing import Protocol

from friends_bot_service.draw.domain import DrawType
from friends_bot_service.draw_entrant.domain import DrawEntrant


class DrawRepository(Protocol):
    async def has_draw_today(
        self,
        bot_id: int,
        chat_id: int,
        draw_type: DrawType,
        today: date,
    ) -> bool: ...

    async def has_claim_today(
        self,
        bot_id: int,
        chat_id: int,
        draw_type: DrawType,
        today: date,
    ) -> bool: ...

    async def list_eligible_draw_entrants(
        self,
        bot_id: int,
        chat_id: int,
        today: date,
    ) -> Sequence[DrawEntrant]: ...

    async def claim_draw(
        self,
        bot_id: int,
        chat_id: int,
        winner_user_id: int,
        draw_type: DrawType,
        today: date,
    ) -> None: ...

    async def record_draw_result(
        self,
        bot_id: int,
        chat_id: int,
        winner_user_id: int,
        draw_type: DrawType,
        today: date,
    ) -> None: ...
