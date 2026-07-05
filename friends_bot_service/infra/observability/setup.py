import logging

from fastapi import FastAPI
from prometheus_client import CollectorRegistry, start_http_server
from prometheus_client import multiprocess as prom_multiprocess

from friends_bot_service.infra.observability.multiproc import is_multiprocess_mode
from friends_bot_service.infra.observability.webhook_metrics import (
    webhook_metrics_middleware,
)

_logger = logging.getLogger(__name__)
_metrics_server_started = False


def start_metrics_server(host: str, port: int) -> None:
    """Exposes Prometheus metrics on a dedicated port (ADR 0005).

    When ``WORKER_COUNT > 1``, aggregates all uvicorn worker processes via
    ``prometheus_client`` multiprocess mode. Call once from ``main.py`` (webhook)
    or ``run_polling()`` (polling), not from FastAPI lifespan.
    """

    global _metrics_server_started
    if _metrics_server_started:
        _logger.debug(
            "metrics server already started host=%s port=%s",
            host,
            port,
        )
        return

    if is_multiprocess_mode():
        registry = CollectorRegistry()
        prom_multiprocess.MultiProcessCollector(registry)
        start_http_server(port=port, addr=host, registry=registry)
    else:
        start_http_server(port=port, addr=host)

    _metrics_server_started = True
    _logger.info("metrics server started host=%s port=%s", host, port)


def setup_webhook_observability(app: FastAPI) -> None:
    """Registers webhook HTTP instrumentation on the FastAPI app."""

    app.middleware("http")(webhook_metrics_middleware)
