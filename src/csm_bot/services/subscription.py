import logging
from typing import TYPE_CHECKING

from telegram import LinkPreviewOptions
from telegram.constants import ParseMode
from telegram.ext import Application, TypeHandler

from csm_bot.models import Block, Event
from csm_bot.rpc import Subscription
from csm_bot.app.storage import BotStorage

logger = logging.getLogger(__name__)
logging.getLogger("web3.providers.WebSocketProvider").setLevel(logging.WARNING)

if TYPE_CHECKING:
    from csm_bot.app.context import BotContext


class TelegramSubscription(Subscription):
    """Bridge Web3 subscription events into the Telegram application update queue."""

    def __init__(self, w3, application: Application, event_messages) -> None:
        super().__init__(w3)
        self.application = application
        self.event_messages = event_messages

    async def process_event_log(self, event: Event):
        await self.application.update_queue.put(event)

    async def handle_event_log(self, event: Event, context: "BotContext"):
        logger.info("Handle event on the block %s: %s", event.block, event.readable())
        bot_storage = context.bot_storage
        actual_chat_ids = bot_storage.actual_chat_ids()
        node_operator_chats = bot_storage.node_operator_chats
        if "nodeOperatorId" in event.args:
            chats = node_operator_chats.chats_for(str(event.args["nodeOperatorId"]))
        else:
            chats = set()
            for node_operator_id in node_operator_chats.ids():
                try:
                    no_id_int = int(node_operator_id)
                except ValueError:  # pragma: no cover - defensive
                    logger.warning("Unexpected non-integer node operator id: %s", node_operator_id)
                    continue
                if await self.event_messages.should_notify_node_operator(event, no_id_int):
                    chats.update(node_operator_chats.chats_for(node_operator_id))
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

    async def handle_new_block(self, block: Block, context: "BotContext"):
        logger.debug("Handle block: %s", block.number)
        context.bot_storage.block.update(block.number)

    def register_handlers(self) -> None:
        """Attach type handlers for block and event updates to the application."""
        self.application.add_handler(TypeHandler(Block, self.handle_new_block))
        self.application.add_handler(TypeHandler(Event, self.handle_event_log, block=False))

    def ensure_state_containers(self) -> None:
        BotStorage(self.application.bot_data)
