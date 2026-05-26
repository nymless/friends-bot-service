from dataclasses import dataclass

from friends_bot_service.bot_admin import usecases as admin_usecases
from friends_bot_service.bot_admin.interfaces import BotRepository, BotRuntimePort


@dataclass(frozen=True, slots=True)
class RemoveBotData:
    bot_id: int
    owner_id: int


class RemoveBot:
    def __init__(self) -> None:
        self._remove_bot = admin_usecases.RemoveBot()

    async def deactivate(
        self,
        data: RemoveBotData,
        bots: BotRepository,
    ) -> admin_usecases.RemoveBotOutcome:
        result = await self._remove_bot.execute(
            admin_usecases.RemoveBotData(
                bot_id=data.bot_id,
                owner_id=data.owner_id,
            ),
            bots,
        )
        return result.outcome

    async def stop_runtime(self, bot_id: int, runtime: BotRuntimePort) -> None:
        await runtime.stop_bot(bot_id)
