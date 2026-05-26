import logging
import secrets

from aiogram.types import Update
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from friends_bot_service.infra.api.app_state import (
    WebhookAppState,
    get_webhook_app_state,
)

_logger = logging.getLogger(__name__)

router = APIRouter()
WEBHOOK_SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"


async def _feed_update(state: WebhookAppState, bot, update: Update) -> None:
    try:
        await state.dp.feed_update(bot, update)
    except Exception:
        _logger.exception(
            "webhook feed_update failed bot_id=%s update_id=%s",
            bot.id,
            update.update_id,
        )


@router.post("/webhook/{bot_id}")
async def handle_telegram_update(
    bot_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    state: WebhookAppState = Depends(get_webhook_app_state),  # noqa: B008
):
    """Handles a Telegram update."""

    received_secret = request.headers.get(WEBHOOK_SECRET_HEADER)

    if received_secret is None or not secrets.compare_digest(
        received_secret,
        state.webhook_secret_token,
    ):
        _logger.warning("webhook secret token mismatch bot_id=%s", bot_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="forbidden",
        )

    bot = state.manager.get_bot(bot_id)

    if bot is None:
        return {"status": "ignored"}

    data = await request.json()
    update = Update.model_validate(data)

    background_tasks.add_task(_feed_update, state, bot, update)

    return {"status": "ok"}
