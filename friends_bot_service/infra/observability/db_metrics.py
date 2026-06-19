from friends_bot_service.infra.observability.metrics import DB_ERRORS_TOTAL


def record_db_unavailable(operation: str = "unit_of_work") -> None:
    DB_ERRORS_TOTAL.labels(operation=operation).inc()
