from aiogram import Bot, types

from friends_bot_service.draw import domain
from friends_bot_service.draw_stats import usecases
from friends_bot_service.infra.bootstrap import db
from friends_bot_service.infra.repositories.unit_of_work import SqlAlchemyUnitOfWork
from friends_bot_service.infra.texts import system_text

_show_stats = usecases.ShowStats()


async def answer_stats(
    message: types.Message, result: usecases.ShowStatsResult
) -> None:
    if result.outcome is usecases.ShowStatsOutcome.EMPTY:
        await message.answer(result.message or "")
        return

    lines = [
        f"{i}) {row.full_name} — {row.count} раз(а)"
        for i, row in enumerate(result.lines, 1)
    ]
    await message.answer((result.message or "") + "\n".join(lines))


async def run_show_stats(
    message: types.Message,
    bot: Bot,
    draw_type: domain.DrawType,
) -> None:
    from_user = message.from_user
    assert from_user is not None

    async def run(uow: SqlAlchemyUnitOfWork) -> usecases.ShowStatsResult:
        data = usecases.ShowStatsData(
            bot_id=bot.id,
            chat_id=message.chat.id,
            user_id=from_user.id,
            draw_type=draw_type,
        )
        return await _show_stats.execute(data, uow.draw_stats)

    try:
        result = await db.run_with_unit_of_work(run)
    except db.DatabaseUnavailableError:
        await message.answer(system_text.DB_UNAVAILABLE_MESSAGE)
        return

    if result.outcome is usecases.ShowStatsOutcome.USER_MISSING:
        return

    await answer_stats(message, result)
