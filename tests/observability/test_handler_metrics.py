from unittest.mock import AsyncMock

import pytest

from friends_bot_service.infra.observability.handler_metrics import (
    HandlerMetricsMiddleware,
)
from friends_bot_service.infra.observability.metrics import (
    DRAW_HANDLER_DURATION_SECONDS,
    HANDLER_DURATION_SECONDS,
)


@pytest.mark.parametrize(
    ("command_text", "expected_histogram"),
    [
        ("/run", DRAW_HANDLER_DURATION_SECONDS),
        ("/loser", DRAW_HANDLER_DURATION_SECONDS),
        ("/stats", HANDLER_DURATION_SECONDS),
    ],
)
async def test_handler_metrics_routes_duration_histogram(
    command_text: str,
    expected_histogram,
) -> None:
    middleware = HandlerMetricsMiddleware("draw")
    handler = AsyncMock(return_value=None)
    event = type(
        "Event", (), {"message": type("Message", (), {"text": command_text})()}
    )()

    await middleware(handler, event, {})

    handler.assert_awaited_once()
    assert (
        expected_histogram.labels(command=command_text, bot_mode="draw")._sum.get() > 0
    )
