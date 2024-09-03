import asyncio
import logging
import os
from asyncio import CancelledError
from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, PicklePersistence, MessageHandler, filters,
    CallbackQueryHandler, ConversationHandler, Application, TypeHandler,
)
from web3 import AsyncWeb3, WebSocketProvider

from csm_bot.events import EventMessages
from csm_bot.models import Block, Event
from csm_bot.rpc import Subscription
from csm_bot.texts import (
    START_BUTTON_FOLLOW, START_BUTTON_UNFOLLOW, FOLLOW_NODE_OPERATOR_BACK, FOLLOW_NODE_OPERATOR_TEXT,
    UNFOLLOW_NODE_OPERATOR_BACK, UNFOLLOW_NODE_OPERATOR_TEXT, UNFOLLOW_NODE_OPERATOR_NOT_FOLLOWING,
    NODE_OPERATOR_FOLLOWED, NODE_OPERATOR_UNFOLLOWED, UNFOLLOW_NODE_OPERATOR_FOLLOWING, FOLLOW_NODE_OPERATOR_FOLLOWING,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


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

    def __init__(self, provider, application: Application):
        self.application = application
        super().__init__(provider)

    async def process_event_log(self, event: Event):
        await application.update_queue.put(event)

    async def handle_event_log(self, event: Event, context: ContextTypes.DEFAULT_TYPE):
        print("Event received: ", event.event, event.args)
        chats = []
        if "nodeOperatorId" in event.args:
            chats = context.bot_data["no_ids_to_chats"].get(str(event.args["nodeOperatorId"]), set())
        message = await eventMessages.get_event_message(event)

        for chat in chats:
            await context.bot.send_message(chat_id=chat,
                                           text=message,
                                           parse_mode=ParseMode.MARKDOWN_V2,
                                           link_preview_options=LinkPreviewOptions(is_disabled=True))

    async def process_new_block(self, block: Block):
        await application.update_queue.put(block)

    async def handle_new_block(self, block: Block, context):
        application.bot_data['block'] = block.number


async def chat_migration(update, context):
    message = update.message
    context.application.migrate_chat_data(message=message)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(START_BUTTON_FOLLOW, callback_data=Callback.FOLLOW_TO_NODE_OPERATOR),
            InlineKeyboardButton(START_BUTTON_UNFOLLOW, callback_data=Callback.UNFOLLOW_FROM_NODE_OPERATOR),
        ],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Hello!",
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
        text="Hello!",
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
        text = FOLLOW_NODE_OPERATOR_FOLLOWING.format(', '.join(node_operator_ids)) + text
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup([keyboard]))
    return States.FOLLOW_NODE_OPERATOR


async def follow_node_operator_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    # TODO validate node operator id
    node_operator_id = message.text
    node_operator_ids = context.chat_data.get('node_operators')
    if node_operator_ids:
        node_operator_ids.add(node_operator_id)
    else:
        node_operator_ids = {node_operator_id}
    context.bot_data["no_ids_to_chats"][node_operator_id].add(message.chat_id)
    context.chat_data['node_operators'] = node_operator_ids
    await message.reply_text(NODE_OPERATOR_FOLLOWED.format(node_operator_id))
    return States.WELCOME


async def unfollow_node_operator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    node_operator_ids = context.chat_data.get('node_operators', {})
    keyboard = [
        InlineKeyboardButton(UNFOLLOW_NODE_OPERATOR_BACK, callback_data=Callback.BACK)
    ]
    if node_operator_ids:
        text = UNFOLLOW_NODE_OPERATOR_FOLLOWING.format(', '.join(node_operator_ids))
        text += UNFOLLOW_NODE_OPERATOR_TEXT
    else:
        text = UNFOLLOW_NODE_OPERATOR_NOT_FOLLOWING
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup([keyboard]))
    return States.UNFOLLOW_NODE_OPERATOR


async def unfollow_node_operator_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    # TODO validate node operator id
    node_operator_id = message.text
    node_operator_ids = context.chat_data.get('node_operators')
    if node_operator_ids and node_operator_id in node_operator_ids:
        node_operator_ids.remove(node_operator_id)
        context.chat_data['node_operators'] = node_operator_ids
        context.bot_data["no_ids_to_chats"][node_operator_id].remove(message.chat_id)
    await message.reply_text(NODE_OPERATOR_UNFOLLOWED.format(node_operator_id))
    return States.WELCOME


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
    print("Bot started. Latest processed block number: ", application.bot_data.get('block'))
    await application.updater.start_polling()
    await subscription.subscribe()
    try:
        while True:
            await asyncio.sleep(1)
    except CancelledError:
        pass
    finally:

        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == '__main__':
    persistence = PicklePersistence(filepath='persistence.pkl')
    application = (
        ApplicationBuilder()
        .token(os.getenv("TOKEN"))
        .persistence(persistence)
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

    application.add_handler(conv_handler)
    application.add_handler(
        MessageHandler(filters.StatusUpdate.MIGRATE, chat_migration)
    )
    application.add_handler(TypeHandler(Block, subscription.handle_new_block))
    application.add_handler(TypeHandler(Event, subscription.handle_event_log))

    asyncio.run(main())