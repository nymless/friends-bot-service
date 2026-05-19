import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from friends_bot_service.middlewares.inbound_command_log import (
    InboundCommandLogMiddleware,
    redact_command_text_for_log,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/add_bot", "/add_bot"),
        ("/add_bot 123:SECRET", "/add_bot"),
        ("/add_bot@mybot 1:2", "/add_bot"),
        ("/remove_bot x:y", "/remove_bot"),
        ("/stats", "/stats"),
        ("/reg@evergreen16_bot", "/reg@evergreen16_bot"),
    ],
)
def test_redact_command_text_for_log(text: str, expected: str) -> None:
    assert redact_command_text_for_log(text) == expected


@pytest.mark.asyncio
async def test_inbound_command_log_logs_slash_commands_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    middleware = InboundCommandLogMiddleware()
    handler = AsyncMock(return_value="ok")
    bot = SimpleNamespace(id=1)
    user = SimpleNamespace(id=2)
    chat = SimpleNamespace(id=3)
    event = SimpleNamespace(
        update_id=42,
        message=SimpleNamespace(text="/reg@bot"),
        event_type="message",
    )
    data = {"bot": bot, "event_from_user": user, "event_chat": chat}

    with caplog.at_level(logging.INFO):
        result = await middleware(handler, event, data)

    assert result == "ok"
    handler.assert_awaited_once()
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert "Inbound" in record.message
    assert "42" in record.message
    assert "/reg@bot" in record.message
    assert "full" not in record.message.lower()


@pytest.mark.asyncio
async def test_inbound_command_log_skips_non_commands(
    caplog: pytest.LogCaptureFixture,
) -> None:
    middleware = InboundCommandLogMiddleware()
    handler = AsyncMock(return_value="ok")
    event = SimpleNamespace(
        update_id=42,
        message=SimpleNamespace(text="hello"),
        event_type="message",
    )
    data = {"bot": SimpleNamespace(id=1)}

    with caplog.at_level(logging.INFO):
        await middleware(handler, event, data)

    assert caplog.records == []


@pytest.mark.asyncio
async def test_inbound_command_log_skips_messages_without_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    middleware = InboundCommandLogMiddleware()
    handler = AsyncMock(return_value="ok")
    event = SimpleNamespace(
        update_id=42,
        message=SimpleNamespace(text=None),
        event_type="message",
    )
    data = {"bot": SimpleNamespace(id=1)}

    with caplog.at_level(logging.INFO):
        await middleware(handler, event, data)

    assert caplog.records == []
