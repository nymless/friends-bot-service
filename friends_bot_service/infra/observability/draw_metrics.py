from friends_bot_service.draw.domain import GameType
from friends_bot_service.infra.observability.metrics import (
    DRAW_COMPLETED_TOTAL,
    DRAW_REJECTED_TOTAL,
)


def draw_type_label(game_type: GameType) -> str:
    return game_type.value


def record_draw_completed(game_type: GameType) -> None:
    DRAW_COMPLETED_TOTAL.labels(draw_type=draw_type_label(game_type)).inc()


def record_draw_rejected(game_type: GameType, reason: str) -> None:
    DRAW_REJECTED_TOTAL.labels(
        draw_type=draw_type_label(game_type),
        reason=reason,
    ).inc()
