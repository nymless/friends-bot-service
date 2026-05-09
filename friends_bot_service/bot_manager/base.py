from abc import ABC, abstractmethod

from aiogram import Bot


class BotManager(ABC):
    """Base abstract class for bot managers."""

    def __init__(self):
        self._active_bots: dict[int, Bot] = {}

    @abstractmethod
    async def start_bot(self, token: str) -> Bot: ...

    @abstractmethod
    async def stop_bot(self, bot_id: int) -> None: ...

    def get_bot(self, bot_id: int) -> Bot | None:
        """Returns a bot by its ID."""

        return self._active_bots.get(bot_id)

    async def stop_all(self):
        """Stops all bots."""

        for bot_id in list(self._active_bots.keys()):
            await self.stop_bot(bot_id)
