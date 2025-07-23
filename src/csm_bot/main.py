import asyncio
import logging
import os
from collections import defaultdict
from itertools import chain
from pathlib import Path

import httpx
import telegram.error
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions, Chat, ChatMemberUpdated,
    ChatMember,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, PicklePersistence, MessageHandler, filters,
    CallbackQueryHandler, ConversationHandler, Application, TypeHandler, AIORateLimiter, ChatMemberHandler,
)
from web3 import AsyncWeb3, WebSocketProvider

from csm_bot.events import EventMessages, EVENTS_TO_FOLLOW
from csm_bot.jobs import JobContext
from csm_bot.models import Block, Event
from csm_bot.rpc import Subscription
from csm_bot.texts import (
    START_BUTTON_FOLLOW, START_BUTTON_UNFOLLOW, FOLLOW_NODE_OPERATOR_TEXT,
    UNFOLLOW_NODE_OPERATOR_TEXT, UNFOLLOW_NODE_OPERATOR_NOT_FOLLOWING,
    NODE_OPERATOR_FOLLOWED, NODE_OPERATOR_UNFOLLOWED, UNFOLLOW_NODE_OPERATOR_FOLLOWING, FOLLOW_NODE_OPERATOR_FOLLOWING,
    WELCOME_TEXT, NODE_OPERATOR_CANT_UNFOLLOW, NODE_OPERATOR_CANT_FOLLOW, EVENT_MESSAGES, EVENT_DESCRIPTIONS,
    BUTTON_BACK, START_BUTTON_EVENTS, EVENT_LIST_TEXT,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger('httpx').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

logging.getLogger('web3.providers.WebSocketProvider').setLevel(logging.WARNING)


class States:
    WELCOME = "1"
    FOLLOW_NODE_OPERATOR = "2"
    UNFOLLOW_NODE_OPERATOR = "3"
    FOLLOWED_EVENTS = "4"


class Callback:
    FOLLOW_TO_NODE_OPERATOR = "1"
    UNFOLLOW_FROM_NODE_OPERATOR = "2"
    FOLLOWED_EVENTS = "3"
    BACK = "4"


class TelegramSubscription(Subscription):
    application: Application

    def __init__(self, w3, application: Application):
        self.application = application
        super().__init__(w3)

    async def process_event_log(self, event: Event):
        await application.update_queue.put(event)

    async def handle_event_log(self, event: Event, context: ContextTypes.DEFAULT_TYPE):
        logger.info("Handle event on the block %s: %s", event.block, event.readable())
        actual_chat_ids = (context.bot_data.get("user_ids", set())
                           .union(context.bot_data.get("group_ids", set()))
                           .union(context.bot_data.get("channel_ids", set())))
        if "nodeOperatorId" in event.args:
            chats = context.bot_data["no_ids_to_chats"].get(str(event.args["nodeOperatorId"]), set())
        else:
            # all chats that subscribed to any node operator
            chats = set(chain(*context.bot_data["no_ids_to_chats"].values()))
        chats = chats.intersection(actual_chat_ids)

        message = await event_messages.get_event_message(event)
        if message is None:
            logger.warning("No message found for event %s", event.readable())
            return

        sent_messages = 0
        for chat in chats:
            try:
                await context.bot.send_message(chat_id=chat,
                                               text=message,
                                               parse_mode=ParseMode.MARKDOWN_V2,
                                               link_preview_options=LinkPreviewOptions(is_disabled=True))
                sent_messages += 1
            except Exception as e:
                logger.error("Error sending message to chat %s: %s", chat, e)
        if sent_messages:
            logger.info("Messages sent: %s", sent_messages)

    async def process_new_block(self, block: Block):
        await application.update_queue.put(block)

    async def handle_new_block(self, block: Block, context):
        logger.debug("Handle block: %s", block.number)
        application.bot_data['block'] = block.number


async def chat_migration(update, context):
    message = update.message
    context.application.migrate_chat_data(message=message)


async def add_user_if_required(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type != Chat.PRIVATE or chat.id in context.bot_data.get("user_ids", set()):
        return

    logger.info("%s started a private chat with the bot", update.effective_user.full_name)
    context.bot_data.setdefault("user_ids", set()).add(chat.id)


def extract_status_change(chat_member_update: ChatMemberUpdated):
    """Takes a ChatMemberUpdated instance and extracts whether the 'old_chat_member' was a member
    of the chat and whether the 'new_chat_member' is a member of the chat. Returns None, if
    the status didn't change.
    """
    status_change = chat_member_update.difference().get("status")
    old_is_member, new_is_member = chat_member_update.difference().get("is_member", (None, None))

    if status_change is None:
        return

    old_status, new_status = status_change
    was_member = old_status in [
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ] or (old_status == ChatMember.RESTRICTED and old_is_member is True)
    is_member = new_status in [
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ] or (new_status == ChatMember.RESTRICTED and new_is_member is True)

    return was_member, is_member


async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tracks the chats the bot is in."""
    result = extract_status_change(update.my_chat_member)
    if result is None:
        return
    was_member, is_member = result

    # Let's check who is responsible for the change
    cause_name = update.effective_user.full_name

    # Handle chat types differently:
    chat = update.effective_chat
    if chat.type == Chat.PRIVATE:
        if not was_member and is_member:
            logger.info("%s unblocked the bot", cause_name)
            context.bot_data.setdefault("user_ids", set()).add(chat.id)
        elif was_member and not is_member:
            logger.info("%s blocked the bot", cause_name)
            context.bot_data.setdefault("user_ids", set()).discard(chat.id)
    elif chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
        if not was_member and is_member:
            logger.info("%s added the bot to the group %s", cause_name, chat.title)
            context.bot_data.setdefault("group_ids", set()).add(chat.id)
        elif was_member and not is_member:
            logger.info("%s removed the bot from the group %s", cause_name, chat.title)
            context.bot_data.setdefault("group_ids", set()).discard(chat.id)
    elif not was_member and is_member:
        logger.info("%s added the bot to the channel %s", cause_name, chat.title)
        context.bot_data.setdefault("channel_ids", set()).add(chat.id)
    elif was_member and not is_member:
        logger.info("%s removed the bot from the channel %s", cause_name, chat.title)
        context.bot_data.setdefault("channel_ids", set()).discard(chat.id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_user_if_required(update, context)
    keyboard = [
        [
            InlineKeyboardButton(START_BUTTON_FOLLOW, callback_data=Callback.FOLLOW_TO_NODE_OPERATOR),
            InlineKeyboardButton(START_BUTTON_UNFOLLOW, callback_data=Callback.UNFOLLOW_FROM_NODE_OPERATOR),
            InlineKeyboardButton(START_BUTTON_EVENTS, callback_data=Callback.FOLLOWED_EVENTS),
        ],
    ]

    text = WELCOME_TEXT
    node_operator_ids = sorted(context.chat_data.get('node_operators', {}))
    if node_operator_ids:
        text += FOLLOW_NODE_OPERATOR_FOLLOWING.format(', '.join(map(lambda x: f"#{x}", node_operator_ids)))

    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
    )
    return States.WELCOME


async def start_over(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(START_BUTTON_FOLLOW, callback_data=Callback.FOLLOW_TO_NODE_OPERATOR),
            InlineKeyboardButton(START_BUTTON_UNFOLLOW, callback_data=Callback.UNFOLLOW_FROM_NODE_OPERATOR),
            InlineKeyboardButton(START_BUTTON_EVENTS, callback_data=Callback.FOLLOWED_EVENTS),
        ],
    ]

    text = WELCOME_TEXT
    node_operator_ids = sorted(context.chat_data.get('node_operators', {}))
    if node_operator_ids:
        text += FOLLOW_NODE_OPERATOR_FOLLOWING.format(', '.join(map(lambda x: f"#{x}", node_operator_ids)))

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        text=text,
        reply_markup=reply_markup
    )
    return States.WELCOME


async def follow_node_operator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    node_operator_ids = sorted(context.chat_data.get('node_operators', {}))
    keyboard = [
        InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK)
    ]
    text = FOLLOW_NODE_OPERATOR_TEXT
    if node_operator_ids:
        text = FOLLOW_NODE_OPERATOR_FOLLOWING.format(', '.join(map(lambda x: f"#{x}", node_operator_ids))) + text
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup([keyboard]))
    return States.FOLLOW_NODE_OPERATOR


async def follow_node_operator_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK)
    ]
    message = update.message
    node_operator_id = message.text
    if node_operator_id.startswith("#"):
        node_operator_id = message.text[1:]
    # TODO provider should be a separate instance
    async with event_messages.connectProvider:
        node_operators_count = await event_messages.csm.functions.getNodeOperatorsCount().call()
    if node_operator_id.isdigit() and int(node_operator_id) < node_operators_count:
        context.bot_data["no_ids_to_chats"][node_operator_id].add(message.chat_id)
        context.chat_data.setdefault("node_operators", set()).add(node_operator_id)
        await message.reply_text(NODE_OPERATOR_FOLLOWED.format(node_operator_id),
                                 reply_markup=InlineKeyboardMarkup([keyboard]))
        return States.FOLLOW_NODE_OPERATOR
    else:
        await message.reply_text(NODE_OPERATOR_CANT_FOLLOW, reply_markup=InlineKeyboardMarkup([keyboard]))
        return States.FOLLOW_NODE_OPERATOR


async def unfollow_node_operator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    node_operator_ids = sorted(context.chat_data.get('node_operators', {}))
    keyboard = [
        InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK)
    ]
    if node_operator_ids:
        text = UNFOLLOW_NODE_OPERATOR_FOLLOWING.format(', '.join(map(lambda x: f"#{x}", node_operator_ids)))
        text += UNFOLLOW_NODE_OPERATOR_TEXT
    else:
        text = UNFOLLOW_NODE_OPERATOR_NOT_FOLLOWING
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup([keyboard]))
    return States.UNFOLLOW_NODE_OPERATOR


async def unfollow_node_operator_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK)
    ]

    message = update.message
    node_operator_id = message.text
    if node_operator_id.startswith("#"):
        node_operator_id = message.text[1:]
    node_operator_ids = context.chat_data.get('node_operators')
    if node_operator_ids and node_operator_id in node_operator_ids:
        node_operator_ids.remove(node_operator_id)
        context.chat_data['node_operators'] = node_operator_ids
        context.bot_data["no_ids_to_chats"][node_operator_id].remove(message.chat_id)
        await message.reply_text(NODE_OPERATOR_UNFOLLOWED.format(node_operator_id),
                                 reply_markup=InlineKeyboardMarkup([keyboard]))
        return States.UNFOLLOW_NODE_OPERATOR
    else:
        await message.reply_text(NODE_OPERATOR_CANT_UNFOLLOW, reply_markup=InlineKeyboardMarkup([keyboard]))
        return States.UNFOLLOW_NODE_OPERATOR


async def followed_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK)
    ]
    await query.edit_message_text(
        text=EVENT_LIST_TEXT,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([keyboard])
    )
    return States.FOLLOWED_EVENTS


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update is None:
        logger.error("A %s occurred: %s", context.error.__class__.__name__, context.error)
    else:
        logger.error("Update %s caused error %s", update, context.error)


def error_callback(error: Exception) -> None:
    """
    Suppress error tracebacks that are possibly not affecting the user experience.
    """
    if isinstance(error, (telegram.error.Conflict, httpx.ReadError)):
        application.create_task(application.process_error(update=None, error=error))


application: Application
subscription: TelegramSubscription
event_messages: EventMessages
job_context: JobContext

async def main():
    await application.initialize()
    await application.start()
    application.add_error_handler(error_handler)
    if "no_ids_to_chats" not in application.bot_data:
        application.bot_data["no_ids_to_chats"] = defaultdict(set)
    if "block" not in application.bot_data:
        application.bot_data["block"] = 0
    block_from = int(os.getenv("BLOCK_FROM", application.bot_data.get('block')))
    await job_context.schedule(application)

    logger.info("Bot started. Latest processed block number: %s", block_from)

    try:
        await application.updater.start_polling(error_callback=error_callback)

        subscription.setup_signal_handlers(asyncio.get_running_loop())
        if block_from:
            await subscription.process_blocks_from(block_from)
        await subscription.subscribe()

    except asyncio.CancelledError:
        pass
    finally:
        await subscription.shutdown()
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == '__main__':
    events, messages, descriptions = set(EVENTS_TO_FOLLOW.keys()), set(EVENT_MESSAGES.keys()), set(
        EVENT_DESCRIPTIONS.keys())
    assert events == messages, "Missed events: " + str(events.symmetric_difference(messages))
    assert events == descriptions, "Missed events: " + str(events.symmetric_difference(descriptions))

    storage_path = Path(os.getenv("FILESTORAGE_PATH", ".storage"))
    if not storage_path.exists():
        storage_path.mkdir(parents=True)
    persistence = PicklePersistence(filepath=storage_path / "persistence.pkl")
    application = (
        ApplicationBuilder()
        .token(os.getenv("TOKEN"))
        .persistence(persistence)
        .rate_limiter(AIORateLimiter(max_retries=5))
        .build()
    )
    persistent_provider = AsyncWeb3(WebSocketProvider(os.getenv("WEB3_SOCKET_PROVIDER"), max_connection_retries=-1))
    rpc_provider = AsyncWeb3(WebSocketProvider(os.getenv("WEB3_SOCKET_PROVIDER"), max_connection_retries=-1))
    subscription = TelegramSubscription(persistent_provider, application)
    event_messages = EventMessages(rpc_provider)
    job_context = JobContext()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            States.WELCOME: [
                CallbackQueryHandler(follow_node_operator, pattern="^" + Callback.FOLLOW_TO_NODE_OPERATOR + "$"),
                CallbackQueryHandler(unfollow_node_operator, pattern="^" + Callback.UNFOLLOW_FROM_NODE_OPERATOR + "$"),
                CallbackQueryHandler(followed_events, pattern="^" + Callback.FOLLOWED_EVENTS + "$"),
            ],
            States.FOLLOW_NODE_OPERATOR: [
                CallbackQueryHandler(start_over, pattern="^" + Callback.BACK + "$"),
                MessageHandler(filters.TEXT, follow_node_operator_message),
            ],
            States.UNFOLLOW_NODE_OPERATOR: [
                CallbackQueryHandler(start_over, pattern="^" + Callback.BACK + "$"),
                MessageHandler(filters.TEXT, unfollow_node_operator_message),
            ],
            States.FOLLOWED_EVENTS: [
                CallbackQueryHandler(start_over, pattern="^" + Callback.BACK + "$"),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))
    application.add_handler(conv_handler)
    application.add_handler(
        MessageHandler(filters.StatusUpdate.MIGRATE, chat_migration)
    )
    application.add_handler(TypeHandler(Block, subscription.handle_new_block))
    application.add_handler(TypeHandler(Event, subscription.handle_event_log, block=False))

    asyncio.run(main())
