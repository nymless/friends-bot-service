import asyncio
import logging
import sys

import uvicorn

from friends_bot_service.infra.bootstrap.runtime import (
    log_worker_cpu_budget,
    run_polling,
    setup_logging,
)
from friends_bot_service.infra.core.config import settings
from friends_bot_service.infra.enums.enums import BotMode

logger = logging.getLogger(__name__)


def run() -> None:
    """Runs the service using the mode from settings."""

    setup_logging()

    if settings.BOT_MODE == BotMode.POLLING:
        asyncio.run(run_polling())
        return

    if settings.BOT_MODE == BotMode.WEBHOOK:
        from friends_bot_service.infra.observability.multiproc import (
            prepare_for_webhook_workers,
        )

        log_worker_cpu_budget(logger)
        prepare_for_webhook_workers(settings.WORKER_COUNT)
        uvicorn.run(
            "friends_bot_service.main_api:app",
            host=settings.WEBHOOK_BIND_HOST,
            port=settings.WEBHOOK_BIND_PORT,
            workers=settings.WORKER_COUNT,
        )
        return

    logger.critical("unsupported mode %s", settings.BOT_MODE)
    sys.exit(1)


if __name__ == "__main__":
    run()
