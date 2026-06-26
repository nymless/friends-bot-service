from fastapi import FastAPI
from prometheus_client import start_http_server

from friends_bot_service.infra.observability.webhook_metrics import (
    webhook_metrics_middleware,
)


def start_metrics_server(host: str, port: int) -> None:
    """Exposes Prometheus metrics over HTTP on a dedicated port."""

    start_http_server(port=port, addr=host)


def setup_webhook_observability(app: FastAPI) -> None:
    """Registers webhook HTTP instrumentation on the FastAPI app."""

    app.middleware("http")(webhook_metrics_middleware)
