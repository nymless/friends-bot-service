import asyncio
import logging
from asyncio import Task, create_task
from collections.abc import Callable
from contextlib import suppress

from aiogram import Bot, Dispatcher

from friends_bot_service.infra.bot_manager.base import BotManager

_logger = logging.getLogger(__name__)


class PollingBotManager(BotManager):
    """Bot manager implementation for polling mode."""

    def __init__(self, dispatcher_factory: Callable[[], Dispatcher]):
        super().__init__()
        self._dispatcher_factory = dispatcher_factory
        self._dispatchers: dict[int, Dispatcher] = {}
        self._tasks: dict[int, Task] = {}

    def _handle_task_done(self, bot_id: int, bot: Bot, task: Task) -> None:
        """Handles the completion of a polling task."""

        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            _logger.exception("polling task crashed [bot_id=%s]", bot_id)
        finally:
            self._tasks.pop(bot_id, None)
            self._dispatchers.pop(bot_id, None)
            active_bot = self._active_bots.get(bot_id)
            if active_bot is bot:
                self._active_bots.pop(bot_id, None)
                create_task(bot.session.close())

    async def start_bot(self, token: str) -> Bot:
        """Starts a bot with polling."""

        bot = Bot(token=token)
        bot_user = await bot.get_me()

        if bot_user.id in self._tasks:
            existing_bot = self.get_bot(bot_user.id)
            await bot.session.close()
            if existing_bot is None:
                raise RuntimeError(f"bot {bot_user.id} task exists without active bot")
            return existing_bot

        dp = self._dispatcher_factory()
        task = create_task(dp.start_polling(bot, handle_signals=False))

        def done_callback(finished_task: Task) -> None:
            self._handle_task_done(bot_user.id, bot, finished_task)

        task.add_done_callback(done_callback)
        self._dispatchers[bot_user.id] = dp
        self._tasks[bot_user.id] = task
        self._active_bots[bot_user.id] = bot
        return bot

    async def stop_bot(self, bot_id: int):
        """Stops a bot with polling."""

        task = self._tasks.get(bot_id)
        if task:
            dp = self._dispatchers.get(bot_id)
            if dp is not None:
                with suppress(RuntimeError):
                    await dp.stop_polling()
            with suppress(asyncio.CancelledError):
                await task
            return

        bot = self._active_bots.pop(bot_id, None)
        if bot:
            await bot.session.close()
