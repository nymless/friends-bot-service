from collections.abc import Sequence
from dataclasses import dataclass

from friends_bot_service.bot_admin.domain import RegisteredBot
from friends_bot_service.bot_admin.interfaces import BotRepository


@dataclass(frozen=True, slots=True)
class ListOwnerBotsData:
    owner_id: int


@dataclass(frozen=True, slots=True)
class ListOwnerBotsResult:
    bots: Sequence[RegisteredBot]


class ListOwnerBots:
    async def execute(
        self,
        data: ListOwnerBotsData,
        bots: BotRepository,
    ) -> ListOwnerBotsResult:
        registered_bots = await bots.list_active_for_owner(data.owner_id)
        return ListOwnerBotsResult(bots=tuple(registered_bots))
