import logging
from collections import defaultdict

from telegram import LinkPreviewOptions
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes, TypeHandler

from csm_bot.handlers.utils import get_actual_chat_ids
from csm_bot.models import Block, Event
from csm_bot.rpc import Subscription

logger = logging.getLogger(__name__)
logging.getLogger("web3.providers.WebSocketProvider").setLevel(logging.WARNING)


class TelegramSubscription(Subscription):
    """Bridge Web3 subscription events into the Telegram application update queue."""

    def __init__(self, w3, application: Application, event_messages) -> None:
        super().__init__(w3)
        self.application = application
        self.event_messages = event_messages

    async def process_event_log(self, event: Event):
        await self.application.update_queue.put(event)

    async def handle_event_log(self, event: Event, context: ContextTypes.DEFAULT_TYPE):
        logger.info("Handle event on the block %s: %s", event.block, event.readable())
        actual_chat_ids = get_actual_chat_ids(context.bot_data)
        if "nodeOperatorId" in event.args:
            chats = context.bot_data["no_ids_to_chats"].get(str(event.args["nodeOperatorId"]), set())
        else:
            chats = set()
            for node_operator_id, subscribed_chats in context.bot_data["no_ids_to_chats"].items():
                if await self.event_messages.should_notify_node_operator(event, int(node_operator_id)):
                    chats.update(subscribed_chats)
        chats = chats.intersection(actual_chat_ids)

        message = await self.event_messages.get_event_message(event)
        if message is None:
            logger.warning("No message found for event %s", event.readable())
            return

        sent_messages = 0
        for chat in chats:
            try:
                await context.bot.send_message(
                    chat_id=chat,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
                sent_messages += 1
            except Exception as exc:  # pragma: no cover - depends on Telegram runtime
                logger.error("Error sending message to chat %s: %s", chat, exc)
        if sent_messages:
            logger.info("Messages sent: %s", sent_messages)

    async def process_new_block(self, block: Block):
        await self.application.update_queue.put(block)

    async def handle_new_block(self, block: Block, context):
        logger.debug("Handle block: %s", block.number)
        context.application.bot_data.setdefault("block", 0)
        context.application.bot_data["block"] = block.number

    def register_handlers(self) -> None:
        """Attach type handlers for block and event updates to the application."""
        self.application.add_handler(TypeHandler(Block, self.handle_new_block))
        self.application.add_handler(TypeHandler(Event, self.handle_event_log, block=False))

    def ensure_state_containers(self) -> None:
        bot_data = self.application.bot_data
        if "no_ids_to_chats" not in bot_data:
            bot_data["no_ids_to_chats"] = defaultdict(set)
        if "block" not in bot_data:
            bot_data["block"] = 0
