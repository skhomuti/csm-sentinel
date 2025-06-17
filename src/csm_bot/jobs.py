import logging

from telegram.ext import ContextTypes, Application


logger = logging.getLogger(__name__)
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)


class JobContext:
    latest_block: str = 0

    async def schedule(self, app: Application):
        app.job_queue.run_repeating(self.callback_block_processing_check, interval=60 * 30, first=0)

    async def callback_block_processing_check(self, context: ContextTypes.DEFAULT_TYPE):
        current_block = context.bot_data['block']
        if not self.latest_block:
            self.latest_block = current_block
            return
        if self.latest_block == current_block:
            logging.warning("No new blocks processed in the last 30 minutes. Latest block: %s", self.latest_block)
        else:
            self.latest_block = current_block
