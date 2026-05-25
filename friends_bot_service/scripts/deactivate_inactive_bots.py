import asyncio
import logging
from datetime import datetime, timedelta, timezone

from friends_bot_service.bootstrap.dependencies import unit_of_work

logger = logging.getLogger(__name__)

INACTIVITY_DAYS = 60


async def deactivate_inactive_bots() -> None:
    """Deactivates bots that have not been used for a configured period."""

    cutoff = datetime.now(timezone.utc) - timedelta(days=INACTIVITY_DAYS)

    async with unit_of_work() as uow:
        deactivated_bots = await uow.bots.deactivate_stale(cutoff)
        await uow.commit()

    if not deactivated_bots:
        logger.info("no stale bots to deactivate")
        return

    for bot_id, username in deactivated_bots:
        logger.info("deactivated bot_id=%s username=%s", bot_id, username)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    asyncio.run(deactivate_inactive_bots())


if __name__ == "__main__":
    main()
