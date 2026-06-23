from fastapi import FastAPI, Response

from friends_bot_service.infra.observability.multiproc import render_metrics
from friends_bot_service.infra.observability.webhook_metrics import (
    webhook_metrics_middleware,
)


def setup_webhook_observability(app: FastAPI) -> None:
    """Mounts Prometheus metrics and webhook HTTP instrumentation."""

    @app.get("/metrics")
    async def metrics() -> Response:
        body, content_type = render_metrics()
        return Response(body, media_type=content_type)

    app.middleware("http")(webhook_metrics_middleware)
