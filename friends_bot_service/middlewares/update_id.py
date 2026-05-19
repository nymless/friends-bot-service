from aiogram import BaseMiddleware


class UpdateIdMiddleware(BaseMiddleware):
    """Injects Telegram update_id into handler context for log correlation."""

    async def __call__(self, handler, event, data):
        data["update_id"] = getattr(event, "update_id", None)
        return await handler(event, data)
