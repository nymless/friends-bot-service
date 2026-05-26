import logging

from aiogram import Bot, types

from friends_bot_service.draw import domain

from .common import _run_draw

_logger = logging.getLogger(__name__)


async def start_loser_draw(
    message: types.Message,
    bot: Bot,
    update_id: str | None = None,
):
    """Starts a loser draw."""

    user = message.from_user
    if user is None:
        _logger.warning(
            "Update id=%s: draw preparation declined; Cause: user not found.",
            update_id,
        )
        return

    _logger.info(
        "Update id=%s: start %s draw.",
        update_id,
        domain.GameType.LOSER,
    )

    await _run_draw(
        message,
        bot,
        domain.GameType.LOSER,
    )
