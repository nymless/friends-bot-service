from friends_bot_service.bot_admin.domain import RegisteredBot
from friends_bot_service.draw_entrant.domain.draw_entrant import (
    DrawEntrant,
    DrawEntrantKey,
    RegisteredDrawEntrant,
)


def draw_entrant_key(
    *,
    bot_id: int = 1,
    chat_id: int = 10,
    user_id: int = 100,
) -> DrawEntrantKey:
    return DrawEntrantKey(bot_id=bot_id, chat_id=chat_id, user_id=user_id)


def draw_entrant(
    *,
    bot_id: int = 1,
    chat_id: int = 10,
    user_id: int = 100,
    username: str | None = "player",
    full_name: str = "Player Name",
) -> DrawEntrant:
    return DrawEntrant(
        bot_id=bot_id,
        chat_id=chat_id,
        user_id=user_id,
        username=username,
        full_name=full_name,
    )


def registered_draw_entrant(
    *,
    bot_id: int = 1,
    chat_id: int = 10,
    user_id: int = 100,
    username: str | None = "player",
    full_name: str = "Player Name",
    is_active: bool = True,
) -> RegisteredDrawEntrant:
    return RegisteredDrawEntrant(
        bot_id=bot_id,
        chat_id=chat_id,
        user_id=user_id,
        username=username,
        full_name=full_name,
        is_active=is_active,
    )


def registered_bot(
    *,
    bot_id: int = 1,
    username: str = "game_bot",
    encrypted_token: str = "enc-token",
    owner_id: int = 20,
    is_active: bool = True,
) -> RegisteredBot:
    return RegisteredBot(
        bot_id=bot_id,
        username=username,
        encrypted_token=encrypted_token,
        owner_id=owner_id,
        is_active=is_active,
    )
