import logging
import secrets

from aiogram import Dispatcher
from aiogram.types import Update
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status

from friends_bot_service.usecases.ports import BotRuntimePort

logger = logging.getLogger(__name__)

router = APIRouter()
WEBHOOK_SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"


async def _feed_update(dp: Dispatcher, bot, update: Update) -> None:
    """Feeds an update to the bot dispatcher."""

    try:
        await dp.feed_update(bot, update)
    except Exception:
        logger.exception(
            "webhook feed_update failed bot_id=%s update_id=%s",
            bot.id,
            update.update_id,
        )


@router.post("/webhook/{bot_id}")
async def handle_telegram_update(
    bot_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Handles a Telegram update."""

    dp: Dispatcher = request.app.state.dp
    manager: BotRuntimePort = request.app.state.manager
    expected_secret: str | None = request.app.state.webhook_secret_token
    received_secret = request.headers.get(WEBHOOK_SECRET_HEADER)

    if expected_secret is None:
        logger.critical("webhook secret token is not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="webhook secret token is not configured",
        )

    # Compare the received secret with the expected secret securely.
    if received_secret is None or not secrets.compare_digest(
        received_secret,
        expected_secret,
    ):
        logger.warning("webhook secret token mismatch bot_id=%s", bot_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="forbidden",
        )

    bot = manager.get_bot(bot_id)

    if bot is None:
        return {"status": "ignored"}

    data = await request.json()
    update = Update.model_validate(data)

    # Feed the update to the bot dispatcher in the background.
    background_tasks.add_task(_feed_update, dp, bot, update)

    # Return success status.
    return {"status": "ok"}
