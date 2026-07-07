from load.seed_bots import chat_id_for_bot, entrant_user_id


def test_chat_id_for_bot_legacy_layout() -> None:
    assert (
        chat_id_for_bot(
            chat_id_base=10_000_000,
            bot_offset=3,
            chats_per_bot=1,
            chat_slot=0,
        )
        == 10_000_003
    )


def test_chat_id_for_bot_multiple_chats() -> None:
    assert (
        chat_id_for_bot(
            chat_id_base=10_000_000,
            bot_offset=2,
            chats_per_bot=10,
            chat_slot=7,
        )
        == 10_000_027
    )


def test_entrant_user_id_offsets_by_bot_and_player_index() -> None:
    assert (
        entrant_user_id(
            user_id_base=100_000,
            bot_offset=0,
            player_index=0,
            players_per_chat=2,
        )
        == 100_000
    )
    assert (
        entrant_user_id(
            user_id_base=100_000,
            bot_offset=0,
            player_index=1,
            players_per_chat=2,
        )
        == 100_001
    )
    assert (
        entrant_user_id(
            user_id_base=100_000,
            bot_offset=3,
            player_index=1,
            players_per_chat=2,
        )
        == 100_007
    )
