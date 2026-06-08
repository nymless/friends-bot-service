from abc import ABC, abstractmethod

from aiogram import Bot


class BotManager(ABC):
    """Base abstract class for bot managers."""

    @abstractmethod
    async def start_bot(self, token: str) -> Bot: ...

    @abstractmethod
    async def stop_bot(self, bot_id: int, *, token: str | None = None) -> None: ...

    @abstractmethod
    async def stop_all(self) -> None: ...
