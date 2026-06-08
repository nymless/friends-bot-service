import logging

from aiogram import Bot, types

from friends_bot_service.draw import domain

from .common import run_show_stats

_logger = logging.getLogger(__name__)


async def show_loser_statistics(
    message: types.Message,
    bot: Bot,
    update_id: str | None = None,
):
    """Shows the loser statistics."""

    from_user = message.from_user
    if from_user is None:
        _logger.warning(
            "Update id=%s: loser stats declined; Cause: user not found.",
            update_id,
        )
        return

    _logger.info(
        "Update id=%s: loser stats requested.",
        update_id,
    )

    await run_show_stats(message, bot, domain.DrawType.LOSER)
