from aiogram import BaseMiddleware


class UpdateIdMiddleware(BaseMiddleware):
    """Injects Telegram update_id into handler context for log correlation."""

    async def __call__(self, handler, event, data):
        raw = getattr(event, "update_id", None)
        data["update_id"] = str(raw) if raw is not None else None
        return await handler(event, data)
