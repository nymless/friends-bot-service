from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from fastapi import Request

from friends_bot_service.bot_admin.interfaces import BotRuntimePort


@dataclass(slots=True)
class WebhookAppState:
    """Runtime dependencies stored on the FastAPI application during lifespan."""

    dp: Dispatcher
    manager: BotRuntimePort
    webhook_secret_token: str
    master_dp: Dispatcher
    master_bot: Bot


def get_webhook_app_state(request: Request) -> WebhookAppState:
    state = request.app.state
    if not isinstance(state, WebhookAppState):
        msg = "webhook application state is not initialized"
        raise RuntimeError(msg)
    return state
