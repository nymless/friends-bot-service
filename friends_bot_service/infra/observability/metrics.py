from prometheus_client import Counter, Histogram

WEBHOOK_REQUEST_DURATION_SECONDS = Histogram(
    "friends_bot_webhook_request_duration_seconds",
    "Webhook HTTP request duration until response is sent",
    labelnames=("status",),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

WEBHOOK_REQUESTS_TOTAL = Counter(
    "friends_bot_webhook_requests_total",
    "Webhook HTTP requests",
    labelnames=("status",),
)

HANDLER_DURATION_SECONDS = Histogram(
    "friends_bot_handler_duration_seconds",
    "Aiogram handler execution duration",
    labelnames=("command", "bot_mode"),
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

HANDLER_INVOCATIONS_TOTAL = Counter(
    "friends_bot_handler_invocations_total",
    "Aiogram handler invocations",
    labelnames=("command", "bot_mode", "outcome"),
)

DRAW_COMPLETED_TOTAL = Counter(
    "friends_bot_draw_completed_total",
    "Draws completed and persisted",
    labelnames=("draw_type",),
)

DRAW_REJECTED_TOTAL = Counter(
    "friends_bot_draw_rejected_total",
    "Draw attempts rejected before completion",
    labelnames=("draw_type", "reason"),
)

DB_ERRORS_TOTAL = Counter(
    "friends_bot_db_errors_total",
    "Database unavailable errors surfaced to handlers",
    labelnames=("operation",),
)
