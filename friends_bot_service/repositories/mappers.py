from friends_bot_service.domain import Player, RegisteredBot
from friends_bot_service.models.bot_models import RegisteredBot as RegisteredBotORM
from friends_bot_service.models.game_models import Player as PlayerORM


def player_to_domain(orm: PlayerORM) -> Player:
    return Player(
        bot_id=orm.bot_id,
        chat_id=orm.chat_id,
        user_id=orm.user_id,
        username=orm.username,
        full_name=orm.full_name,
        is_active=orm.is_active,
    )


def registered_bot_to_domain(orm: RegisteredBotORM) -> RegisteredBot:
    return RegisteredBot(
        bot_id=orm.bot_id,
        username=orm.username,
        encrypted_token=orm.encrypted_token,
        owner_id=orm.owner_id,
        is_active=orm.is_active,
    )
