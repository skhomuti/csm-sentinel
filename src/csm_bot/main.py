import asyncio
import logging
import os
from collections import defaultdict
from itertools import chain
from pathlib import Path

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

from csm_bot.events import EventMessages
from csm_bot.models import Block, Event
from csm_bot.rpc import Subscription
from csm_bot.texts import (
    START_BUTTON_FOLLOW, START_BUTTON_UNFOLLOW, FOLLOW_NODE_OPERATOR_BACK, FOLLOW_NODE_OPERATOR_TEXT,
    UNFOLLOW_NODE_OPERATOR_BACK, UNFOLLOW_NODE_OPERATOR_TEXT, UNFOLLOW_NODE_OPERATOR_NOT_FOLLOWING,
    NODE_OPERATOR_FOLLOWED, NODE_OPERATOR_UNFOLLOWED, UNFOLLOW_NODE_OPERATOR_FOLLOWING, FOLLOW_NODE_OPERATOR_FOLLOWING,
    WELCOME_TEXT, NODE_OPERATOR_CANT_UNFOLLOW, NODE_OPERATOR_CANT_FOLLOW,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger('httpx').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class States:
    WELCOME = "1"
    FOLLOW_NODE_OPERATOR = "2"
    UNFOLLOW_NODE_OPERATOR = "3"


class Callback:
    FOLLOW_TO_NODE_OPERATOR = "1"
    UNFOLLOW_FROM_NODE_OPERATOR = "2"
    BACK = "3"


class TelegramSubscription(Subscription):
    application: Application

    def __init__(self, w3, application: Application):
        self.application = application
        super().__init__(w3)

    async def process_event_log(self, event: Event):
        await application.update_queue.put(event)

    async def handle_event_log(self, event: Event, context: ContextTypes.DEFAULT_TYPE):
        logger.info("Handle event on the block %s: %s %s", event.block, event.event, event.args)
        if "nodeOperatorId" in event.args:
            chats = context.bot_data["no_ids_to_chats"].get(str(event.args["nodeOperatorId"]), set())
        else:
            # all chats that subscribed to any node operator
            chats = set(chain(*context.bot_data["no_ids_to_chats"].values()))

        message = await eventMessages.get_event_message(event)

        for chat in chats:
            await context.bot.send_message(chat_id=chat,
                                           text=message,
                                           parse_mode=ParseMode.MARKDOWN_V2,
                                           link_preview_options=LinkPreviewOptions(is_disabled=True))

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
        ],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=WELCOME_TEXT,
        reply_markup=reply_markup
    )
    return States.WELCOME


async def start_over(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(START_BUTTON_FOLLOW, callback_data=Callback.FOLLOW_TO_NODE_OPERATOR),
            InlineKeyboardButton(START_BUTTON_UNFOLLOW, callback_data=Callback.UNFOLLOW_FROM_NODE_OPERATOR),
        ],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        text=WELCOME_TEXT,
        reply_markup=reply_markup
    )
    return States.WELCOME


async def follow_node_operator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    node_operator_ids = context.chat_data.get('node_operators', {})
    keyboard = [
        InlineKeyboardButton(FOLLOW_NODE_OPERATOR_BACK, callback_data=Callback.BACK)
    ]
    text = FOLLOW_NODE_OPERATOR_TEXT
    if node_operator_ids:
        text = FOLLOW_NODE_OPERATOR_FOLLOWING.format(', '.join(map(lambda x: f"#{x}", node_operator_ids))) + text
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup([keyboard]))
    return States.FOLLOW_NODE_OPERATOR


async def follow_node_operator_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        InlineKeyboardButton(UNFOLLOW_NODE_OPERATOR_BACK, callback_data=Callback.BACK)
    ]
    message = update.message
    node_operator_id = message.text
    if node_operator_id.startswith("#"):
        node_operator_id = message.text[1:]
    # TODO provider should be a separate instance
    if node_operator_id.isdigit() and await eventMessages.csm.functions.getNodeOperatorsCount().call() >= int(node_operator_id):
        context.bot_data["no_ids_to_chats"][node_operator_id].add(message.chat_id)
        context.chat_data.setdefault("node_operators", set()).add(node_operator_id)
        await message.reply_text(NODE_OPERATOR_FOLLOWED.format(node_operator_id), reply_markup=InlineKeyboardMarkup([keyboard]))
        return States.FOLLOW_NODE_OPERATOR
    else:
        await message.reply_text(NODE_OPERATOR_CANT_FOLLOW, reply_markup=InlineKeyboardMarkup([keyboard]))
        return States.FOLLOW_NODE_OPERATOR


async def unfollow_node_operator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    node_operator_ids = context.chat_data.get('node_operators', {})
    keyboard = [
        InlineKeyboardButton(UNFOLLOW_NODE_OPERATOR_BACK, callback_data=Callback.BACK)
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
        InlineKeyboardButton(UNFOLLOW_NODE_OPERATOR_BACK, callback_data=Callback.BACK)
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
        await message.reply_text(NODE_OPERATOR_UNFOLLOWED.format(node_operator_id), reply_markup=InlineKeyboardMarkup([keyboard]))
        return States.UNFOLLOW_NODE_OPERATOR
    else:
        await message.reply_text(NODE_OPERATOR_CANT_UNFOLLOW, reply_markup=InlineKeyboardMarkup([keyboard]))
        return States.UNFOLLOW_NODE_OPERATOR


application: Application
subscription: TelegramSubscription
eventMessages: EventMessages


async def main():
    await application.initialize()
    await application.start()
    if "no_ids_to_chats" not in application.bot_data:
        application.bot_data["no_ids_to_chats"] = defaultdict(set)
    if "block" not in application.bot_data:
        application.bot_data["block"] = 0
    logger.info("Bot started. Latest processed block number: %s", application.bot_data.get('block'))

    try:
        await application.updater.start_polling()

        subscription.setup_signal_handlers(asyncio.get_running_loop())
        if application.bot_data.get('block') != 0:
            await subscription.process_blocks_from(application.bot_data.get('block'))
        await subscription.subscribe()

    except asyncio.CancelledError:
        pass
    finally:
        await subscription.shutdown()
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == '__main__':
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
    provider = AsyncWeb3(WebSocketProvider(os.getenv("WEB3_SOCKET_PROVIDER"), max_connection_retries=-1))
    subscription = TelegramSubscription(provider, application)
    eventMessages = EventMessages(provider)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            States.WELCOME: [
                CallbackQueryHandler(follow_node_operator, pattern="^" + Callback.FOLLOW_TO_NODE_OPERATOR + "$"),
                CallbackQueryHandler(unfollow_node_operator, pattern="^" + Callback.UNFOLLOW_FROM_NODE_OPERATOR + "$"),
            ],
            States.FOLLOW_NODE_OPERATOR: [
                CallbackQueryHandler(start_over, pattern="^" + Callback.BACK + "$"),
                MessageHandler(filters.TEXT, follow_node_operator_message),
            ],
            States.UNFOLLOW_NODE_OPERATOR: [
                CallbackQueryHandler(start_over, pattern="^" + Callback.BACK + "$"),
                MessageHandler(filters.TEXT, unfollow_node_operator_message),
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
