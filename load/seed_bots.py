"""Insert synthetic bots (and optional draw entrants) for load testing."""

import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from friends_bot_service.infra.core.config import settings
from friends_bot_service.infra.core.security import encrypt_token


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        print(f"error: {name} is required (set in .env.load)", file=sys.stderr)
        sys.exit(1)
    return value


def _require_env_int(name: str) -> int:
    raw = _require_env(name)
    try:
        return int(raw)
    except ValueError:
        print(f"error: {name} must be an integer, got: {raw!r}", file=sys.stderr)
        sys.exit(1)


def _require_env_bool(name: str) -> bool:
    raw = _require_env(name).lower()
    if raw == "true":
        return True
    if raw == "false":
        return False
    print(f"error: {name} must be 'true' or 'false', got: {raw!r}", file=sys.stderr)
    sys.exit(1)


def _build_token(bot_id: int) -> str:
    return f"{bot_id}:AAloadtestfake"


def entrant_user_id(
    *,
    user_id_base: int,
    bot_offset: int,
    player_index: int,
    players_per_chat: int,
) -> int:
    return user_id_base + bot_offset * players_per_chat + player_index


async def seed_bots(
    *,
    count: int,
    start_id: int,
    owner_id: int,
    with_draw_entrants: bool,
    players_per_chat: int,
    chat_id_base: int,
    user_id_base: int,
) -> None:
    engine = create_async_engine(settings.DB_URL)
    insert_bot = text(
        """
        INSERT INTO bots (bot_id, username, encrypted_token, owner_id, is_active)
        VALUES (:bot_id, :username, :encrypted_token, :owner_id, true)
        ON CONFLICT (bot_id) DO UPDATE SET
            username = EXCLUDED.username,
            encrypted_token = EXCLUDED.encrypted_token,
            owner_id = EXCLUDED.owner_id,
            is_active = true
        """
    )
    insert_player = text(
        """
        INSERT INTO players (
            bot_id, chat_id, user_id, username, full_name, is_active
        )
        VALUES (
            :bot_id, :chat_id, :user_id, :username, :full_name, true
        )
        ON CONFLICT (bot_id, chat_id, user_id) DO UPDATE SET
            username = EXCLUDED.username,
            full_name = EXCLUDED.full_name,
            is_active = true
        """
    )

    async with engine.begin() as conn:
        for offset in range(count):
            bot_id = start_id + offset
            token = _build_token(bot_id)
            await conn.execute(
                insert_bot,
                {
                    "bot_id": bot_id,
                    "username": f"load_bot_{bot_id}",
                    "encrypted_token": encrypt_token(token),
                    "owner_id": owner_id,
                },
            )
            if with_draw_entrants:
                chat_id = chat_id_base + offset
                for player_index in range(players_per_chat):
                    user_id = entrant_user_id(
                        user_id_base=user_id_base,
                        bot_offset=offset,
                        player_index=player_index,
                        players_per_chat=players_per_chat,
                    )
                    await conn.execute(
                        insert_player,
                        {
                            "bot_id": bot_id,
                            "chat_id": chat_id,
                            "user_id": user_id,
                            "username": f"player_{user_id}",
                            "full_name": f"Load Player {user_id}",
                        },
                    )

    await engine.dispose()
    players = players_per_chat if with_draw_entrants else 0
    print(
        f"seeded bots={count} start_id={start_id} "
        f"draw_entrants={with_draw_entrants} players_per_chat={players}"
    )


def main() -> None:
    count = _require_env_int("LOAD_BOT_COUNT")
    with_draw_entrants = _require_env_bool("LOAD_SEED_DRAW_ENTRANTS")

    start_id = _require_env_int("LOAD_BOT_ID_START")
    owner_id = _require_env_int("LOAD_BOT_OWNER_ID")
    chat_id_base = _require_env_int("LOAD_CHAT_ID_BASE")
    user_id_base = _require_env_int("LOAD_USER_ID_BASE")
    players_per_chat = (
        _require_env_int("LOAD_PLAYERS_PER_CHAT") if with_draw_entrants else 1
    )
    if with_draw_entrants and players_per_chat < 2:
        print(
            "error: LOAD_PLAYERS_PER_CHAT must be >= 2 when "
            "LOAD_SEED_DRAW_ENTRANTS=true",
            file=sys.stderr,
        )
        sys.exit(1)

    asyncio.run(
        seed_bots(
            count=count,
            start_id=start_id,
            owner_id=owner_id,
            with_draw_entrants=with_draw_entrants,
            players_per_chat=players_per_chat,
            chat_id_base=chat_id_base,
            user_id_base=user_id_base,
        )
    )


if __name__ == "__main__":
    main()
