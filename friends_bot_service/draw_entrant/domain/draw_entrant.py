from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DrawEntrantKey:
    bot_id: int
    chat_id: int
    user_id: int


@dataclass(frozen=True, slots=True)
class DrawEntrant:
    bot_id: int
    chat_id: int
    user_id: int
    username: str | None
    full_name: str


@dataclass(slots=True)
class RegisteredDrawEntrant:
    bot_id: int
    chat_id: int
    user_id: int
    username: str | None
    full_name: str
    is_active: bool
