import logging
import secrets

from aiogram import Bot
from aiogram.types import Update
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from friends_bot_service.bot_admin.domain import RegisteredBot
from friends_bot_service.infra.api.app_state import (
    WebhookAppState,
    get_webhook_app_state,
)
from friends_bot_service.infra.bootstrap.db import unit_of_work
from friends_bot_service.infra.security import default_token_cipher

_logger = logging.getLogger(__name__)
router = APIRouter()
WEBHOOK_SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"
_token_cipher = default_token_cipher()


async def _load_active_draw_bot(bot_id: int) -> RegisteredBot | None:
    async with unit_of_work() as uow:
        return await uow.bots.get_active_by_id(bot_id)


async def _feed_master_update(
    state: WebhookAppState,
    update: Update,
) -> None:
    try:
        await state.master_dp.feed_update(
            state.master_bot,
            update,
            manager=state.manager,
        )
    except Exception:
        _logger.exception(
            "webhook feed_update failed bot_id=%s update_id=%s",
            state.master_bot.id,
            update.update_id,
        )


async def _feed_draw_bot_update(
    state: WebhookAppState,
    registered_bot: RegisteredBot,
    update: Update,
) -> None:
    bot = Bot(token=_token_cipher.decrypt(registered_bot.encrypted_token))
    try:
        await state.dp.feed_update(bot, update)
    except Exception:
        _logger.exception(
            "webhook feed_update failed bot_id=%s update_id=%s",
            registered_bot.bot_id,
            update.update_id,
        )
    finally:
        await bot.session.close()


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

    data = await request.json()
    update = Update.model_validate(data)

    if bot_id == state.master_bot.id:
        background_tasks.add_task(_feed_master_update, state, update)
        return {"status": "ok"}

    registered_bot = await _load_active_draw_bot(bot_id)
    if registered_bot is None:
        return {"status": "ignored"}

    background_tasks.add_task(_feed_draw_bot_update, state, registered_bot, update)

    return {"status": "ok"}
