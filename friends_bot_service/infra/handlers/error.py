import logging

from aiogram import Router, types

from friends_bot_service.infra.texts import system_text

_logger = logging.getLogger(__name__)

router = Router()


@router.errors()
async def global_error_handler(event: types.ErrorEvent):
    """Handles all unhandled dispatcher errors."""

    update = event.update
    exception = event.exception
    bot_id = getattr(event.update.bot, "id", "N/A") if update else "N/A"

    _logger.exception(
        "GLOBAL_ERROR [upd=%s] [bot_id=%s] [type=%s]",
        update.update_id if update else "N/A",
        bot_id,
        type(exception).__name__,
    )

    if update and update.message:
        try:
            await update.message.answer(system_text.UNEXPECTED_ERROR_MESSAGE)
        except Exception:
            _logger.error("Failed to notify user about error [bot_id=%s]", bot_id)
