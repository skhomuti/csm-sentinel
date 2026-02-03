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

    def __init__(self, w3, application: Application, event_messages, allowed_events: set[str]) -> None:
        super().__init__(w3, allowed_events)
        self.application = application
        self.event_messages = event_messages

    async def process_event_log(self, event: Event):
        await self.application.update_queue.put(event)

    async def handle_event_log(self, event: Event, context: "BotContext"):
        logger.info("Handle event on the block %s: %s", event.block, event.readable())
        bot_storage = context.bot_storage
        actual_chat_ids = bot_storage.actual_chat_ids()
        node_operator_chats = bot_storage.node_operator_chats
        plan = await self.event_messages.get_notification_plan(event)
        if plan is None:
            return

        sent_messages = 0
        targeted_chats: set[int] = set()

        for node_operator_id, message in plan.per_node_operator.items():
            chats = node_operator_chats.chats_for(node_operator_id)
            chats = chats.intersection(actual_chat_ids)
            if not chats:
                continue
            for chat in chats:
                try:
                    await context.bot.send_message(
                        chat_id=chat,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN_V2,
                        link_preview_options=LinkPreviewOptions(is_disabled=True),
                    )
                    targeted_chats.add(chat)
                    sent_messages += 1
                except Exception as exc:  # pragma: no cover - depends on Telegram runtime
                    logger.error("Error sending message to chat %s: %s", chat, exc)

        if plan.broadcast:
            targeted_ids = set(plan.per_node_operator.keys())
            if plan.broadcast_node_operator_ids is not None:
                candidate_ids = plan.broadcast_node_operator_ids
            else:
                candidate_ids = node_operator_chats.ids()

            candidate_ids -= targeted_ids

            broadcast_chats: set[int] = set()
            for node_operator_id in candidate_ids:
                broadcast_chats.update(node_operator_chats.chats_for(node_operator_id))

            broadcast_chats = broadcast_chats.intersection(actual_chat_ids)
            broadcast_chats -= targeted_chats

            for chat in broadcast_chats:
                try:
                    await context.bot.send_message(
                        chat_id=chat,
                        text=plan.broadcast,
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
