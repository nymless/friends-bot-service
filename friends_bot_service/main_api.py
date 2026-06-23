"""
This entry point is intended for running the FastAPI app directly.

It can be useful when the webhook app needs to be started by an ASGI server
or another deployment-specific process.
"""

import uvicorn

from friends_bot_service.infra.bootstrap.runtime import (
    create_webhook_app,
    setup_logging,
)
from friends_bot_service.infra.core.config import settings

setup_logging()
app = create_webhook_app()

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.WEBHOOK_BIND_HOST,
        port=settings.WEBHOOK_BIND_PORT,
    )
