from load.seed_bots import entrant_user_id


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
