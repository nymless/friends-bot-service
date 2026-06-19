import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Dispatcher

from friends_bot_service.infra.observability.command_name import (
    command_name_from_message_text,
)
from friends_bot_service.infra.observability.metrics import (
    HANDLER_DURATION_SECONDS,
    HANDLER_INVOCATIONS_TOTAL,
)

Handler = Callable[[Any, dict[str, Any]], Awaitable[Any]]


class HandlerMetricsMiddleware(BaseMiddleware):
    """Times aiogram handlers and records command-level counters."""

    def __init__(self, bot_mode: str) -> None:
        self._bot_mode = bot_mode

    async def __call__(self, handler: Handler, event: Any, data: dict[str, Any]) -> Any:
        message = getattr(event, "message", None)
        command = command_name_from_message_text(
            message.text if message is not None else None,
        )

        started = time.perf_counter()
        try:
            result = await handler(event, data)
        except Exception:
            HANDLER_INVOCATIONS_TOTAL.labels(
                command=command,
                bot_mode=self._bot_mode,
                outcome="error",
            ).inc()
            raise
        else:
            HANDLER_INVOCATIONS_TOTAL.labels(
                command=command,
                bot_mode=self._bot_mode,
                outcome="ok",
            ).inc()
            return result
        finally:
            elapsed = time.perf_counter() - started
            HANDLER_DURATION_SECONDS.labels(
                command=command,
                bot_mode=self._bot_mode,
            ).observe(elapsed)


def register_handler_metrics_middleware(dp: Dispatcher, bot_mode: str) -> None:
    dp.update.middleware(HandlerMetricsMiddleware(bot_mode))
