from dataclasses import dataclass
from enum import StrEnum

from friends_bot_service.draw_entrant.domain.draw_entrant import RegisteredDrawEntrant
from friends_bot_service.draw_entrant.interfaces import DrawEntrantRepository


class ListDrawEntrantsOutcome(StrEnum):
    NO_ENTRANTS = "no_entrants"
    SUCCESS = "success"


@dataclass(frozen=True, slots=True)
class ListDrawEntrantsData:
    bot_id: int
    chat_id: int


@dataclass(frozen=True, slots=True)
class ListDrawEntrantsResult:
    outcome: ListDrawEntrantsOutcome
    draw_entrants: tuple[RegisteredDrawEntrant, ...] = ()


class ListDrawEntrants:
    async def execute(
        self,
        data: ListDrawEntrantsData,
        draw_entrant: DrawEntrantRepository,
    ) -> ListDrawEntrantsResult:

        players = await draw_entrant.list_active_for_chat(data.bot_id, data.chat_id)
        if not players:
            return ListDrawEntrantsResult(outcome=ListDrawEntrantsOutcome.NO_ENTRANTS)

        return ListDrawEntrantsResult(
            outcome=ListDrawEntrantsOutcome.SUCCESS,
            draw_entrants=tuple(players),
        )
