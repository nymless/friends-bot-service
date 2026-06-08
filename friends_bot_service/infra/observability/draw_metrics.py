from friends_bot_service.draw.domain import DrawType
from friends_bot_service.infra.observability.metrics import (
    DRAW_COMPLETED_TOTAL,
    DRAW_REJECTED_TOTAL,
)


def draw_type_label(draw_type: DrawType) -> str:
    return draw_type.value


def record_draw_completed(draw_type: DrawType) -> None:
    DRAW_COMPLETED_TOTAL.labels(draw_type=draw_type_label(draw_type)).inc()


def record_draw_rejected(draw_type: DrawType, reason: str) -> None:
    DRAW_REJECTED_TOTAL.labels(
        draw_type=draw_type_label(draw_type),
        reason=reason,
    ).inc()
