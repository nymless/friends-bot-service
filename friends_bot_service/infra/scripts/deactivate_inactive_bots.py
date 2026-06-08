import asyncio
import logging
from datetime import datetime, timedelta, timezone

from friends_bot_service.infra.bootstrap.db import unit_of_work

logger = logging.getLogger(__name__)

INACTIVITY_DAYS = 60


async def deactivate_inactive_bots() -> None:
    """Marks stale bots inactive in the database.

    The script only updates ``bots.is_active``. It does not stop the running
    service, remove Telegram webhooks, or stop polling tasks. After it runs,
    restart the service so runtime state matches the database (webhook
    registration on startup, polling workers, and stale delivery all realign).
    """

    cutoff = datetime.now(timezone.utc) - timedelta(days=INACTIVITY_DAYS)

    async with unit_of_work() as uow:
        deactivated_bots = await uow.bots.deactivate_stale(cutoff)
        await uow.commit()

    if not deactivated_bots:
        logger.info("no stale bots to deactivate")
        return

    for bot_id, username in deactivated_bots:
        logger.info("deactivated bot_id=%s username=%s", bot_id, username)

    logger.info(
        "deactivated %s bot(s); restart the service to apply runtime changes",
        len(deactivated_bots),
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    asyncio.run(deactivate_inactive_bots())


if __name__ == "__main__":
    main()
