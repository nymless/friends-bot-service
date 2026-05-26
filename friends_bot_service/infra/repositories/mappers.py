from friends_bot_service.bot_admin.domain import RegisteredBot
from friends_bot_service.draw_entrant.domain import DrawEntrant, RegisteredDrawEntrant
from friends_bot_service.infra.models.bot_models import (
    RegisteredBot as RegisteredBotORM,
)
from friends_bot_service.infra.models.draw_models import DrawEntrantORM


def draw_entrant_orm_to_registered_draw_entrant(
    orm: DrawEntrantORM,
) -> RegisteredDrawEntrant:
    return RegisteredDrawEntrant(
        bot_id=orm.bot_id,
        chat_id=orm.chat_id,
        user_id=orm.user_id,
        username=orm.username,
        full_name=orm.full_name,
        is_active=orm.is_active,
    )


def draw_entrant_orm_to_draw_entrant(orm: DrawEntrantORM) -> DrawEntrant:
    return DrawEntrant(
        bot_id=orm.bot_id,
        chat_id=orm.chat_id,
        user_id=orm.user_id,
        username=orm.username,
        full_name=orm.full_name,
    )


def registered_bot_orm_to_registered_bot(orm: RegisteredBotORM) -> RegisteredBot:
    return RegisteredBot(
        bot_id=orm.bot_id,
        username=orm.username,
        encrypted_token=orm.encrypted_token,
        owner_id=orm.owner_id,
        is_active=orm.is_active,
    )
