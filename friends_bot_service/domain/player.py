from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlayerKey:
    bot_id: int
    chat_id: int
    user_id: int


@dataclass(slots=True)
class Player:
    bot_id: int
    chat_id: int
    user_id: int
    username: str | None
    full_name: str
    is_active: bool
