import logging
from typing import TYPE_CHECKING

from telegram.ext import Application


logger = logging.getLogger(__name__)
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)

if TYPE_CHECKING:
    from csm_bot.app.context import BotContext


class JobContext:
    latest_block: int = 0

    async def schedule(self, app: Application):
        app.job_queue.run_repeating(self.callback_block_processing_check, interval=60 * 30, first=0)

    async def callback_block_processing_check(self, context: "BotContext"):
        current_block = context.bot_storage.block.value
        if not self.latest_block:
            self.latest_block = current_block
            return
        if self.latest_block == current_block:
            logger.warning("No new blocks processed in the last 30 minutes. Latest block: %s", self.latest_block)
        else:
            self.latest_block = current_block
