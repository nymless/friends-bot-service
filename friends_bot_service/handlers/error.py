import logging

from aiogram import Router, types

logger = logging.getLogger(__name__)


def get_error_router() -> Router:
    """Returns a router for global error handling."""

    router = Router()

    @router.errors()
    async def global_error_handler(event: types.ErrorEvent):
        """Handles all errors globally."""

        update = event.update
        exception = event.exception
        bot_id = getattr(event.update.bot, "id", "N/A") if update else "N/A"

        logger.exception(
            f"GLOBAL_ERROR [upd={update.update_id}] [bot_id={bot_id}] "
            f"[type={type(exception).__name__}]"
        )

        if update and update.message:
            try:
                await update.message.answer(
                    "❌ Произошла непредвиденная ошибка. Мы уже работаем над этим!"
                )
            except Exception:
                logger.error(f"Failed to notify user about error [bot_id={bot_id}]")

    return router
