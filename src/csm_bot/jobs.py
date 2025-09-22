import logging
from typing import TYPE_CHECKING

from telegram.ext import Application

from csm_bot.texts import NO_NEW_BLOCKS_ADMIN_ALERT


logger = logging.getLogger(__name__)
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)

if TYPE_CHECKING:
    from csm_bot.app.context import BotContext


class JobContext:
    latest_block: int = 0
    alerted_for_block: int | None = None
    alert_interval_minutes: int = 30

    async def schedule(self, app: Application):
        interval_seconds = 60 * self.alert_interval_minutes
        app.job_queue.run_repeating(
            self.callback_block_processing_check,
            interval=interval_seconds,
            first=0,
        )

    async def callback_block_processing_check(self, context: "BotContext"):
        current_block = context.bot_storage.block.value
        if not self.latest_block:
            self.latest_block = current_block
            return
        if self.latest_block == current_block:
            logger.warning(
                "No new blocks processed in the last %s minutes. Latest block: %s",
                self.alert_interval_minutes,
                self.latest_block,
            )
            if self.alerted_for_block == current_block:
                return
            await self._notify_admins(context, current_block)
            self.alerted_for_block = current_block
            return
        self.latest_block = current_block
        self.alerted_for_block = None

    async def _notify_admins(self, context: "BotContext", current_block: int) -> None:
        admin_ids = context.runtime.config.admin_ids
        if not admin_ids:
            return
        message = NO_NEW_BLOCKS_ADMIN_ALERT.format(
            minutes=self.alert_interval_minutes,
            block=current_block,
        )
        for admin_id in admin_ids:
            try:
                await context.bot.send_message(chat_id=admin_id, text=message)
            except Exception as exc:  # pragma: no cover - depends on Telegram runtime
                logger.error("Failed to notify admin %s about stalled blocks: %s", admin_id, exc)
