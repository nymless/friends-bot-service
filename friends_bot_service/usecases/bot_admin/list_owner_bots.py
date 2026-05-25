from collections.abc import Sequence
from dataclasses import dataclass

from friends_bot_service.domain import RegisteredBot
from friends_bot_service.usecases.ports import BotRepository


@dataclass(frozen=True, slots=True)
class ListOwnerBotsCommand:
    owner_id: int


@dataclass(frozen=True, slots=True)
class ListOwnerBotsResult:
    bots: Sequence[RegisteredBot]


class ListOwnerBots:
    async def execute(
        self,
        command: ListOwnerBotsCommand,
        bots: BotRepository,
    ) -> ListOwnerBotsResult:
        registered_bots = await bots.list_active_for_owner(command.owner_id)
        return ListOwnerBotsResult(bots=tuple(registered_bots))
