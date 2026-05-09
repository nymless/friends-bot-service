import asyncio
import logging
import sys

import uvicorn

from friends_bot_service.bootstrap.runtime import (
    create_webhook_app,
    run_polling,
    setup_logging,
)
from friends_bot_service.core.config import settings
from friends_bot_service.enums.enums import BotMode

logger = logging.getLogger(__name__)


def run() -> None:
    """Runs the service using the mode from settings."""

    setup_logging()

    if settings.BOT_MODE == BotMode.POLLING:
        asyncio.run(run_polling())
        return

    if settings.BOT_MODE == BotMode.WEBHOOK:
        uvicorn.run(create_webhook_app(), host="0.0.0.0", port=8000)
        return

    logger.critical("unsupported mode %s", settings.BOT_MODE)
    sys.exit(1)


if __name__ == "__main__":
    run()
