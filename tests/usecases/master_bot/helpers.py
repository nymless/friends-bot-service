from types import SimpleNamespace
from unittest.mock import AsyncMock


class FakeTempBot:
    """Minimal async context manager used to fake Bot(token) in master tests."""

    def __init__(
        self,
        *,
        bot_info: SimpleNamespace | None = None,
        get_me_exception: Exception | None = None,
        set_my_commands_exception: Exception | None = None,
    ) -> None:
        self._bot_info = bot_info
        self._get_me_exception = get_me_exception
        self._set_my_commands_exception = set_my_commands_exception
        self.set_my_commands = AsyncMock(side_effect=self._set_my_commands)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get_me(self):
        if self._get_me_exception is not None:
            raise self._get_me_exception
        return self._bot_info

    async def _set_my_commands(self, *args, **kwargs):
        if self._set_my_commands_exception is not None:
            raise self._set_my_commands_exception
