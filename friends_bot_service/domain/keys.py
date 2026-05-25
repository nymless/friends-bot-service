from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlayerKey:
    bot_id: int
    chat_id: int
    user_id: int


@dataclass(frozen=True, slots=True)
class BotChatKey:
    bot_id: int
    chat_id: int
