from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from friends_bot_service.handlers.error import get_error_router


def get_error_handler():
    """Extracts the registered aiogram error callback from the router."""

    router = get_error_router()
    return router.observers["error"].handlers[0].callback


@pytest.mark.asyncio
async def test_global_error_handler_notifies_user_when_message_exists():
    """
    Verify that the global error handler notifies the chat when a message is present.

    Scenario:
    - an error event contains update data with a message object

    Expected behavior:
    - the handler attempts to send the generic failure notification
    """

    # Build a minimal error event with bot and message data.
    message = AsyncMock()
    update = SimpleNamespace(
        update_id=123,
        bot=SimpleNamespace(id=456),
        message=message,
    )
    event = SimpleNamespace(update=update, exception=RuntimeError("boom"))

    # Execute the registered error handler callback.
    handler = get_error_handler()
    await handler(event)

    # The handler must notify the user with the generic error text.
    message.answer.assert_awaited_once_with(
        "❌ Произошла непредвиденная ошибка. Мы уже работаем над этим!"
    )


@pytest.mark.asyncio
async def test_global_error_handler_swallows_notification_failures():
    """
    Verify that notification failures inside the global error handler are swallowed.

    Scenario:
    - an error event contains update data with a message object
    - replying to that message raises an exception

    Expected behavior:
    - the handler does not re-raise the notification failure
    - fallback logging is performed
    """

    # Build a minimal error event whose reply attempt fails.
    message = AsyncMock()
    message.answer.side_effect = RuntimeError("cannot answer")
    update = SimpleNamespace(
        update_id=123,
        bot=SimpleNamespace(id=456),
        message=message,
    )
    event = SimpleNamespace(update=update, exception=RuntimeError("boom"))

    # Execute the registered error handler callback and capture fallback logging.
    handler = get_error_handler()
    with patch("friends_bot_service.handlers.error.logger.error") as logger_error:
        await handler(event)

    # The handler must log the notification failure instead of crashing.
    assert any(
        call.args == ("Failed to notify user about error [bot_id=456]",)
        for call in logger_error.call_args_list
    )
