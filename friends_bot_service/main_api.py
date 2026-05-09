"""
This entry point is intended for running the FastAPI app directly.

It can be useful when the webhook app needs to be started by an ASGI server
or another deployment-specific process.
"""

import uvicorn

from friends_bot_service.bootstrap.runtime import create_webhook_app, setup_logging

setup_logging()
app = create_webhook_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
