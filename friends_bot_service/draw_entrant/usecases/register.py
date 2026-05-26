from dataclasses import dataclass
from enum import StrEnum

from friends_bot_service.draw_entrant.domain.draw_entrant import DrawEntrant
from friends_bot_service.draw_entrant.interfaces import DrawEntrantRepository


class RegisterDrawEntrantOutcome(StrEnum):
    SUCCESS = "success"


RegisterDrawEntrantData = DrawEntrant


@dataclass(frozen=True, slots=True)
class RegisterDrawEntrantResult:
    outcome: RegisterDrawEntrantOutcome


class RegisterDrawEntrant:
    async def execute(
        self,
        data: RegisterDrawEntrantData,
        draw_entrant: DrawEntrantRepository,
    ) -> RegisterDrawEntrantResult:
        await draw_entrant.upsert_active(draw_entrant=data)
        return RegisterDrawEntrantResult(outcome=RegisterDrawEntrantOutcome.SUCCESS)
