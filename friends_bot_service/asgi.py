"""ASGI application export for uvicorn multi-worker webhook mode.

``main.py`` starts metrics and uvicorn with an import string
(``friends_bot_service.asgi:app``) so each worker process loads the same
FastAPI app. Use ``python -m friends_bot_service.main`` to run the service.
"""

from friends_bot_service.infra.bootstrap.runtime import (
    create_webhook_app,
    setup_logging,
)

setup_logging()
app = create_webhook_app()
