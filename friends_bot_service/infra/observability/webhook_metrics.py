import time
from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

from friends_bot_service.infra.observability.metrics import (
    WEBHOOK_REQUEST_DURATION_SECONDS,
    WEBHOOK_REQUESTS_TOTAL,
)

HttpHandler = Callable[[Request], Awaitable[Response]]


async def webhook_metrics_middleware(
    request: Request,
    call_next: HttpHandler,
) -> Response:
    if not request.url.path.startswith("/webhook/"):
        return await call_next(request)

    started = time.perf_counter()
    response = await call_next(request)
    status = str(response.status_code)
    elapsed = time.perf_counter() - started

    WEBHOOK_REQUEST_DURATION_SECONDS.labels(status=status).observe(elapsed)
    WEBHOOK_REQUESTS_TOTAL.labels(status=status).inc()
    return response
