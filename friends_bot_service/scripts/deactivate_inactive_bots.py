import asyncio
import logging
from datetime import datetime, timedelta, timezone

from friends_bot_service.core.database import session_factory
from friends_bot_service.repositories import bot_repo

logger = logging.getLogger(__name__)

INACTIVITY_DAYS = 60


async def main() -> None:
    """Deactivates bots that were not used within the inactivity window."""

    cutoff = datetime.now(timezone.utc) - timedelta(days=INACTIVITY_DAYS)

    async with session_factory() as session:
        deactivated_bots = await bot_repo.deactivate_stale_bots(session, cutoff)
        await session.commit()

    if not deactivated_bots:
        logger.info("no stale bots found cutoff=%s", cutoff.isoformat())
        return

    bot_labels = ", ".join(
        f"@{username}({bot_id})" for bot_id, username in deactivated_bots
    )
    logger.info(
        "deactivated stale bots count=%s cutoff=%s bots=%s",
        len(deactivated_bots),
        cutoff.isoformat(),
        bot_labels,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    asyncio.run(main())
