from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode

from csm_bot.handlers.state import Callback, States
from csm_bot.handlers.tracking import add_user_if_required
from csm_bot.handlers.utils import is_admin, reply_with_markup
from csm_bot.texts import (
    BUTTON_BACK,
    FOLLOW_NODE_OPERATOR_FOLLOWING,
    FOLLOW_NODE_OPERATOR_TEXT,
    NODE_OPERATOR_CANT_FOLLOW,
    NODE_OPERATOR_CANT_UNFOLLOW,
    NODE_OPERATOR_FOLLOWED,
    NODE_OPERATOR_UNFOLLOWED,
    START_BUTTON_ADMIN,
    START_BUTTON_EVENTS,
    START_BUTTON_FOLLOW,
    START_BUTTON_UNFOLLOW,
    UNFOLLOW_NODE_OPERATOR_FOLLOWING,
    UNFOLLOW_NODE_OPERATOR_NOT_FOLLOWING,
    UNFOLLOW_NODE_OPERATOR_TEXT,
    WELCOME_TEXT,
)

if TYPE_CHECKING:
    from csm_bot.app.context import BotContext


async def start(update: Update, context: "BotContext") -> States:
    await add_user_if_required(update, context)
    chat_storage = context.chat_storage()
    keyboard = [
        [
            InlineKeyboardButton(START_BUTTON_FOLLOW, callback_data=Callback.FOLLOW_TO_NODE_OPERATOR.value),
            InlineKeyboardButton(START_BUTTON_UNFOLLOW, callback_data=Callback.UNFOLLOW_FROM_NODE_OPERATOR.value),
            InlineKeyboardButton(START_BUTTON_EVENTS, callback_data=Callback.FOLLOWED_EVENTS.value),
        ],
    ]
    if is_admin(update.effective_user.id, context):
        keyboard.append([InlineKeyboardButton(START_BUTTON_ADMIN, callback_data=Callback.ADMIN.value)])

    text = WELCOME_TEXT
    node_operator_ids = sorted(chat_storage.node_operators.ids())
    if node_operator_ids:
        text += FOLLOW_NODE_OPERATOR_FOLLOWING.format(", ".join(f"#{x}" for x in node_operator_ids)
        )

    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
    )
    return States.WELCOME


async def start_over(update: Update, context: "BotContext") -> States:
    keyboard = [
        [
            InlineKeyboardButton(START_BUTTON_FOLLOW, callback_data=Callback.FOLLOW_TO_NODE_OPERATOR.value),
            InlineKeyboardButton(START_BUTTON_UNFOLLOW, callback_data=Callback.UNFOLLOW_FROM_NODE_OPERATOR.value),
            InlineKeyboardButton(START_BUTTON_EVENTS, callback_data=Callback.FOLLOWED_EVENTS.value),
        ],
    ]
    if is_admin(update.effective_user.id, context):
        keyboard.append([InlineKeyboardButton(START_BUTTON_ADMIN, callback_data=Callback.ADMIN.value)])

    text = WELCOME_TEXT
    chat_storage = context.chat_storage()
    node_operator_ids = sorted(chat_storage.node_operators.ids())
    if node_operator_ids:
        text += FOLLOW_NODE_OPERATOR_FOLLOWING.format(", ".join(f"#{x}" for x in node_operator_ids)
        )

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
    )
    return States.WELCOME


async def follow_node_operator(update: Update, context: "BotContext") -> States:
    query = update.callback_query
    await query.answer()

    chat_storage = context.chat_storage()
    node_operator_ids = sorted(chat_storage.node_operators.ids())
    keyboard = [InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK.value)]
    text = FOLLOW_NODE_OPERATOR_TEXT
    if node_operator_ids:
        text = (
            FOLLOW_NODE_OPERATOR_FOLLOWING.format(", ".join(f"#{x}" for x in node_operator_ids))
            + text
        )
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup([keyboard]))
    return States.FOLLOW_NODE_OPERATOR


async def follow_node_operator_message(update: Update, context: "BotContext") -> States:
    keyboard = [InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK.value)]
    message = update.message
    if message is None or not message.text:
        await reply_with_markup(
            update,
            context,
            NODE_OPERATOR_CANT_FOLLOW,
            InlineKeyboardMarkup([keyboard]),
        )
        return States.FOLLOW_NODE_OPERATOR

    node_operator_id = message.text
    if node_operator_id.startswith("#"):
        node_operator_id = node_operator_id[1:]

    runtime = context.runtime
    async with runtime.event_messages.connectProvider:
        node_operators_count = await runtime.event_messages.module.functions.getNodeOperatorsCount().call()

    if node_operator_id.isdigit() and int(node_operator_id) < node_operators_count:
        chat_storage = context.chat_storage()
        context.bot_storage.node_operator_chats.subscribe(node_operator_id, message.chat_id)
        chat_storage.node_operators.follow(node_operator_id)
        await reply_with_markup(
            update,
            context,
            NODE_OPERATOR_FOLLOWED.format(node_operator_id),
            InlineKeyboardMarkup([keyboard]),
        )
        return States.FOLLOW_NODE_OPERATOR

    await reply_with_markup(
        update,
        context,
        NODE_OPERATOR_CANT_FOLLOW,
        InlineKeyboardMarkup([keyboard]),
    )
    return States.FOLLOW_NODE_OPERATOR


async def unfollow_node_operator(update: Update, context: "BotContext") -> States:
    query = update.callback_query
    await query.answer()

    chat_storage = context.chat_storage()
    node_operator_ids = sorted(chat_storage.node_operators.ids())
    keyboard = [InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK.value)]
    if node_operator_ids:
        text = UNFOLLOW_NODE_OPERATOR_FOLLOWING.format(", ".join(f"#{x}" for x in node_operator_ids))
        text += UNFOLLOW_NODE_OPERATOR_TEXT
    else:
        text = UNFOLLOW_NODE_OPERATOR_NOT_FOLLOWING
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup([keyboard]))
    return States.UNFOLLOW_NODE_OPERATOR


async def unfollow_node_operator_message(update: Update, context: "BotContext") -> States:
    keyboard = [InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK.value)]
    message = update.message
    if message is None or not message.text:
        await reply_with_markup(
            update,
            context,
            NODE_OPERATOR_CANT_UNFOLLOW,
            InlineKeyboardMarkup([keyboard]),
        )
        return States.UNFOLLOW_NODE_OPERATOR

    node_operator_id = message.text
    if node_operator_id.startswith("#"):
        node_operator_id = node_operator_id[1:]
    chat_storage = context.chat_storage()
    if chat_storage.node_operators.unfollow(node_operator_id):
        context.bot_storage.node_operator_chats.unsubscribe(node_operator_id, message.chat_id)
        await reply_with_markup(
            update,
            context,
            NODE_OPERATOR_UNFOLLOWED.format(node_operator_id),
            InlineKeyboardMarkup([keyboard]),
        )
        return States.UNFOLLOW_NODE_OPERATOR

    await reply_with_markup(
        update,
        context,
        NODE_OPERATOR_CANT_UNFOLLOW,
        InlineKeyboardMarkup([keyboard]),
    )
    return States.UNFOLLOW_NODE_OPERATOR


async def followed_events(update: Update, context: "BotContext") -> States:
    query = update.callback_query
    await query.answer()

    keyboard = [InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK.value)]
    await query.edit_message_text(
        text=context.runtime.module_adapter.build_event_list_text(),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([keyboard]),
    )
    return States.FOLLOWED_EVENTS
