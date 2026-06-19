from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from friends_bot_service.infra.observability.webhook_metrics import (
    webhook_metrics_middleware,
)


def setup_webhook_observability(app: FastAPI) -> None:
    """Mounts Prometheus metrics and webhook HTTP instrumentation."""

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.middleware("http")(webhook_metrics_middleware)
