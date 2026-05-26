from dataclasses import dataclass
from enum import StrEnum

from friends_bot_service.draw_entrant.domain.draw_entrant import DrawEntrantKey
from friends_bot_service.draw_entrant.interfaces import DrawEntrantRepository


class UnregisterDrawEntrantOutcome(StrEnum):
    NOT_FOUND = "not_found"
    ALREADY_INACTIVE = "already_inactive"
    SUCCESS = "success"


UnregisterDrawEntrantData = DrawEntrantKey


@dataclass(frozen=True, slots=True)
class UnregisterDrawEntrantResult:
    outcome: UnregisterDrawEntrantOutcome


class UnregisterDrawEntrant:
    async def execute(
        self,
        data: UnregisterDrawEntrantData,
        draw_entrant: DrawEntrantRepository,
    ) -> UnregisterDrawEntrantResult:

        registered = await draw_entrant.get(data)

        if registered is None:
            return UnregisterDrawEntrantResult(
                outcome=UnregisterDrawEntrantOutcome.NOT_FOUND
            )

        if not registered.is_active:
            return UnregisterDrawEntrantResult(
                outcome=UnregisterDrawEntrantOutcome.ALREADY_INACTIVE
            )

        registered.is_active = False
        await draw_entrant.save(registered)
        return UnregisterDrawEntrantResult(outcome=UnregisterDrawEntrantOutcome.SUCCESS)
