import logging
from typing import TYPE_CHECKING

from telegram.ext import Application

from csm_bot.texts import NO_NEW_BLOCKS_ADMIN_ALERT


logger = logging.getLogger(__name__)
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)

if TYPE_CHECKING:
    from csm_bot.app.context import BotContext
    from csm_bot.rpc import Subscription

CHAIN_HEAD_POLL_INTERVAL_SECONDS = 5 * 60  # 5 minutes
BLOCK_LAG_THRESHOLD = 200  # ~40 minutes of blocks
ALERT_INTERVAL_MINUTES = 30


class JobContext:
    _alerted: bool = False

    def __init__(self, subscription: "Subscription") -> None:
        self._subscription = subscription
        self._chain_head: int = 0

    async def schedule(self, app: Application):
        interval_seconds = 60 * ALERT_INTERVAL_MINUTES
        app.job_queue.run_repeating(
            self.callback_block_processing_check,
            interval=interval_seconds,
            first=0,
        )
        app.job_queue.run_repeating(
            self._poll_chain_head,
            interval=CHAIN_HEAD_POLL_INTERVAL_SECONDS,
            first=0,
        )

    async def _poll_chain_head(self, _context: "BotContext"):
        try:
            self._chain_head = await self._subscription.get_block_number()
            logger.debug("Polled chain head: %s", self._chain_head)
        except Exception as exc:
            logger.warning("Failed to poll chain head: %s", exc)

    async def callback_block_processing_check(self, context: "BotContext"):
        if not self._chain_head:
            return
        persisted_block = context.bot_storage.block.value
        lag = self._chain_head - persisted_block
        if lag > BLOCK_LAG_THRESHOLD:
            logger.warning(
                "Block processing lag: chain head %s, persisted %s (lag %s)",
                self._chain_head,
                persisted_block,
                lag,
            )
            if self._alerted:
                return
            await self._notify_admins(context, persisted_block)
            self._alerted = True
            return
        self._alerted = False

    async def _notify_admins(self, context: "BotContext", current_block: int) -> None:
        admin_ids = context.runtime.config.admin_ids
        if not admin_ids:
            return
        message = NO_NEW_BLOCKS_ADMIN_ALERT.format(
            minutes=ALERT_INTERVAL_MINUTES,
            block=current_block,
        )
        for admin_id in admin_ids:
            try:
                await context.bot.send_message(chat_id=admin_id, text=message)
            except Exception as exc:  # pragma: no cover - depends on Telegram runtime
                logger.error("Failed to notify admin %s about stalled blocks: %s", admin_id, exc)
