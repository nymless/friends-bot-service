from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from friends_bot_service.infra.handlers.error import router
from friends_bot_service.infra.texts import system_text


def get_error_handler():
    """Extracts the registered aiogram error callback from the router."""

    return router.observers["error"].handlers[0].callback


@pytest.mark.asyncio
async def test_global_error_handler_notifies_user_when_message_exists():
    message = AsyncMock()
    update = SimpleNamespace(
        update_id=123,
        bot=SimpleNamespace(id=456),
        message=message,
    )
    event = SimpleNamespace(update=update, exception=RuntimeError("boom"))

    handler = get_error_handler()
    await handler(event)

    message.answer.assert_awaited_once_with(system_text.UNEXPECTED_ERROR_MESSAGE)


@pytest.mark.asyncio
async def test_global_error_handler_swallows_notification_failures():
    message = AsyncMock()
    message.answer.side_effect = RuntimeError("cannot answer")
    update = SimpleNamespace(
        update_id=123,
        bot=SimpleNamespace(id=456),
        message=message,
    )
    event = SimpleNamespace(update=update, exception=RuntimeError("boom"))

    handler = get_error_handler()
    with patch(
        "friends_bot_service.infra.handlers.error._logger.error"
    ) as logger_error:
        await handler(event)

    assert any(
        call.args == ("Failed to notify user about error [bot_id=%s]", 456)
        for call in logger_error.call_args_list
    )
