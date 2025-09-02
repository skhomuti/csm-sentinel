import asyncio
import logging
import os
from collections import defaultdict
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
    BUTTON_BACK, START_BUTTON_EVENTS, EVENT_LIST_TEXT, START_BUTTON_ADMIN, ADMIN_BUTTON_SUBSCRIPTIONS, ADMIN_MENU_TEXT,
    ADMIN_BUTTON_BROADCAST, ADMIN_BROADCAST_MENU_TEXT, ADMIN_BROADCAST_ALL, ADMIN_BROADCAST_BY_NO,
    ADMIN_BROADCAST_ENTER_MESSAGE_ALL, ADMIN_BROADCAST_ENTER_NO_IDS, ADMIN_BROADCAST_NO_IDS_INVALID,
)
from csm_bot.utils import chunk_text

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
    ADMIN = "5"
    ADMIN_BROADCAST = "6"
    ADMIN_BROADCAST_MESSAGE_ALL = "7"
    ADMIN_BROADCAST_SELECT_NO = "8"
    ADMIN_BROADCAST_MESSAGE_SELECTED = "9"


class Callback:
    FOLLOW_TO_NODE_OPERATOR = "1"
    UNFOLLOW_FROM_NODE_OPERATOR = "2"
    FOLLOWED_EVENTS = "3"
    BACK = "4"
    ADMIN = "5"
    ADMIN_SUBSCRIPTIONS = "6"
    ADMIN_BROADCAST = "7"
    ADMIN_BROADCAST_ALL = "8"
    ADMIN_BROADCAST_BY_NO = "9"


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
            # For events without a specific node operator, check all subscribed node operators
            # and apply any registered filters
            chats = set()
            for node_operator_id, subscribed_chats in context.bot_data["no_ids_to_chats"].items():
                if await event_messages.should_notify_node_operator(event, int(node_operator_id)):
                    chats.update(subscribed_chats)
        chats = chats.intersection(actual_chat_ids)

        message = await event_messages.get_event_message(event)

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
    if is_admin(update.effective_user.id, context):
        keyboard.append([InlineKeyboardButton(START_BUTTON_ADMIN, callback_data=Callback.ADMIN)])

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
    if is_admin(update.effective_user.id, context):
        keyboard.append([InlineKeyboardButton(START_BUTTON_ADMIN, callback_data=Callback.ADMIN)])

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


async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id, context):
        await query.edit_message_text(text="Not authorized.")
        return States.WELCOME
    keyboard = [
        [InlineKeyboardButton(ADMIN_BUTTON_SUBSCRIPTIONS, callback_data=Callback.ADMIN_SUBSCRIPTIONS)],
        [InlineKeyboardButton(ADMIN_BUTTON_BROADCAST, callback_data=Callback.ADMIN_BROADCAST)],
        [InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK)],
    ]
    await query.edit_message_text(text=ADMIN_MENU_TEXT, reply_markup=InlineKeyboardMarkup(keyboard))
    return States.ADMIN


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


def get_admin_ids_from_env() -> set[int]:
    """Parse ADMIN_IDS env var to a set of ints. Accepts comma/space-separated values."""
    raw = os.getenv("ADMIN_IDS", "")
    ids: set[int] = set()
    for token in raw.replace(" ", ",").split(","):
        if not token:
            continue
        try:
            ids.add(int(token))
        except ValueError:
            logger.warning("Ignoring invalid ADMIN_IDS entry: %s", token)
    return ids


def is_admin(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True if the given Telegram user_id is an admin."""
    return user_id in context.application.bot_data.get("admin_ids", set())


def get_active_subscription_counts(bot_data: dict) -> dict[str, dict[str, int]]:
    """Compute active subscription counts per node operator, broken down by chat type.

    Returns a mapping: { no_id (str): { 'total': int, 'users': int, 'groups': int, 'channels': int } }
    Only includes operators with total > 0.
    """
    user_ids = bot_data.get("user_ids", set())
    group_ids = bot_data.get("group_ids", set())
    channel_ids = bot_data.get("channel_ids", set())
    actual_chat_ids = user_ids.union(group_ids).union(channel_ids)

    results: dict[str, dict[str, int]] = {}
    for no_id, chats in bot_data.get("no_ids_to_chats", {}).items():
        active = chats.intersection(actual_chat_ids)
        if not active:
            continue
        users = sum(1 for c in active if c in user_ids)
        groups = sum(1 for c in active if c in group_ids)
        channels = sum(1 for c in active if c in channel_ids)
        results[no_id] = {
            "total": len(active),
            "users": users,
            "groups": groups,
            "channels": channels,
        }
    return results


def _get_actual_chat_ids(bot_data: dict) -> set[int]:
    """Return the set of chat IDs where the bot is currently present."""
    return (
        bot_data.get("user_ids", set())
        .union(bot_data.get("group_ids", set()))
        .union(bot_data.get("channel_ids", set()))
    )


def _resolve_target_chats_for_node_operators(bot_data: dict, node_operator_ids: set[str]) -> set[int]:
    """Return target chats that subscribed to any of the provided node operator IDs."""
    actual = _get_actual_chat_ids(bot_data)
    targets: set[int] = set()
    for no_id in node_operator_ids:
        chats = bot_data.get("no_ids_to_chats", {}).get(no_id, set())
        if chats:
            targets.update(chats)
    return targets.intersection(actual)


async def _broadcast_to_chats(context: ContextTypes.DEFAULT_TYPE, chats: set[int], text: str) -> tuple[int, int]:
    """Send text to each chat; returns (sent, failed)."""
    sent, failed = 0, 0
    for chat_id in chats:
        try:
            await context.bot.send_message(chat_id=chat_id, text=text)
            sent += 1
        except Exception as e:  # pragma: no cover - depends on Telegram runtime
            logger.error("Broadcast error to %s: %s", chat_id, e)
            failed += 1
    return sent, failed

async def broadcast_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id, context):
        await query.edit_message_text(text="Not authorized.")
        return States.WELCOME
    keyboard = [
        [InlineKeyboardButton(ADMIN_BROADCAST_ALL, callback_data=Callback.ADMIN_BROADCAST_ALL)],
        [InlineKeyboardButton(ADMIN_BROADCAST_BY_NO, callback_data=Callback.ADMIN_BROADCAST_BY_NO)],
        [InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK)],
    ]
    await query.edit_message_text(text=ADMIN_BROADCAST_MENU_TEXT, reply_markup=InlineKeyboardMarkup(keyboard))
    return States.ADMIN_BROADCAST


async def broadcast_all_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id, context):
        await query.edit_message_text(text="Not authorized.")
        return States.WELCOME
    keyboard = [[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK)]]
    await query.edit_message_text(text=ADMIN_BROADCAST_ENTER_MESSAGE_ALL, reply_markup=InlineKeyboardMarkup(keyboard))
    return States.ADMIN_BROADCAST_MESSAGE_ALL


async def broadcast_all_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    text = message.text.strip()
    if not text:
        await message.reply_text(ADMIN_BROADCAST_ENTER_MESSAGE_ALL,
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK)]]))
        return States.ADMIN_BROADCAST_MESSAGE_ALL
    # Collect target chats
    bot_data = context.bot_data
    all_subscribed: set[int] = set()
    for chats in bot_data.get("no_ids_to_chats", {}).values():
        all_subscribed.update(chats)
    targets = all_subscribed.intersection(_get_actual_chat_ids(bot_data))
    if not targets:
        await message.reply_text("No subscribers to notify.",
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK)]]))
        return States.ADMIN_BROADCAST_MESSAGE_ALL
    sent, failed = await _broadcast_to_chats(context, targets, text)
    await message.reply_text(f"Broadcast sent to {sent} chat(s). Failures: {failed}.",
                             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK)]]))
    return States.ADMIN_BROADCAST_MESSAGE_ALL


async def broadcast_enter_no_ids_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    raw = (message.text or "").strip()
    raw = raw.replace("#", "").replace(" ", ",")
    ids: set[str] = set()
    for token in filter(None, (t.strip() for t in raw.split(","))):
        if token.isdigit():
            ids.add(token)
    if not ids:
        await message.reply_text(ADMIN_BROADCAST_NO_IDS_INVALID,
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK)]]))
        return States.ADMIN_BROADCAST_SELECT_NO
    context.user_data["broadcast_selected"] = ids
    pretty_ids = ", ".join(sorted(f"#{i}" for i in ids))
    await message.reply_text(f"Enter message for: {pretty_ids}",
                             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK)]]))
    return States.ADMIN_BROADCAST_MESSAGE_SELECTED


async def broadcast_by_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id, context):
        await query.edit_message_text(text="Not authorized.")
        return States.WELCOME
    # Prompt for comma-separated NO IDs
    context.user_data.pop("broadcast_selected", None)
    keyboard = [[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK)]]
    await query.edit_message_text(text=ADMIN_BROADCAST_ENTER_NO_IDS, reply_markup=InlineKeyboardMarkup(keyboard))
    return States.ADMIN_BROADCAST_SELECT_NO


# Removed button-based NO selection in favor of text input of IDs.


async def broadcast_selected_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    text = message.text.strip()
    selected: set[str] = context.user_data.get("broadcast_selected", set())
    if not selected:
        await message.reply_text("No node operators selected.",
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK)]]))
        return States.ADMIN_BROADCAST_SELECT_NO
    if not text:
        await message.reply_text("Message text is required.",
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK)]]))
        return States.ADMIN_BROADCAST_MESSAGE_SELECTED
    targets = _resolve_target_chats_for_node_operators(context.bot_data, selected)
    if not targets:
        await message.reply_text("No active subscribers for the selected node operators.",
                                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK)]]))
        return States.ADMIN_BROADCAST_MESSAGE_SELECTED
    sent, failed = await _broadcast_to_chats(context, targets, text)
    pretty_ids = ", ".join(sorted(f"#{i}" for i in selected))
    await message.reply_text(f"Broadcast to {pretty_ids}: sent to {sent} chat(s). Failures: {failed}.",
                             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK)]]))
    return States.ADMIN_BROADCAST_MESSAGE_SELECTED

async def subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: list node operators that currently have subscribers (no chat IDs)."""
    # Support both command and callback usage; answer callback if present
    query = update.callback_query
    if query is not None:
        await query.answer()
    user_id = update.effective_user.id if update.effective_user else None
    if not user_id or not is_admin(user_id, context):
        target_chat = query.message.chat_id if query and query.message else update.effective_chat.id
        await context.bot.send_message(chat_id=target_chat, text="Not authorized.")
        return States.WELCOME

    counts = get_active_subscription_counts(context.bot_data)

    if not counts:
        full_text = "No active subscriptions."
    else:
        # Sort by numeric node operator id when possible
        def sort_key(k: str):
            return (0, int(k)) if k.isdigit() else (1, k)

        lines = ["Active subscriptions:"]
        for no_id in sorted(counts.keys(), key=sort_key):
            c = counts[no_id]
            sub_word = "subscriber" if c["total"] == 1 else "subscribers"
            lines.append(
                f"#{no_id}: {c['total']} {sub_word} (users:{c['users']}, groups:{c['groups']}, channels:{c['channels']})"
            )
        full_text = "\n".join(lines)

    chunks = chunk_text(full_text)
    back_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK)]])

    if query is not None:
        chat_id = query.message.chat_id if query.message else update.effective_chat.id
        if len(chunks) == 1:
            # Single message: keep Back on this one
            await query.edit_message_text(text=chunks[0], reply_markup=back_keyboard)
        else:
            # Multi-part: first chunk without Back (clear keyboard), intermediates without Back, last with Back
            await query.edit_message_text(text=chunks[0], reply_markup=None)
            for chunk in chunks[1:-1]:
                await context.bot.send_message(chat_id=chat_id, text=chunk)
            await context.bot.send_message(chat_id=chat_id, text=chunks[-1], reply_markup=back_keyboard)
        return States.ADMIN
    else:
        # Command path: send chunks and put Back only on the last one
        chat_id = update.effective_chat.id
        if len(chunks) == 1:
            await context.bot.send_message(chat_id=chat_id, text=chunks[0], reply_markup=back_keyboard)
        else:
            for chunk in chunks[:-1]:
                await context.bot.send_message(chat_id=chat_id, text=chunk)
            await context.bot.send_message(chat_id=chat_id, text=chunks[-1], reply_markup=back_keyboard)
        return States.WELCOME

async def main():
    await application.initialize()
    await application.start()
    application.add_error_handler(error_handler)
    if "no_ids_to_chats" not in application.bot_data:
        application.bot_data["no_ids_to_chats"] = defaultdict(set)
    if "block" not in application.bot_data:
        application.bot_data["block"] = 0
    # Load admin IDs once at startup
    application.bot_data["admin_ids"] = get_admin_ids_from_env()
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
                CallbackQueryHandler(admin_menu, pattern="^" + Callback.ADMIN + "$"),
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
            States.ADMIN: [
                CallbackQueryHandler(start_over, pattern="^" + Callback.BACK + "$"),
                CallbackQueryHandler(subscriptions, pattern="^" + Callback.ADMIN_SUBSCRIPTIONS + "$"),
                CallbackQueryHandler(broadcast_menu, pattern="^" + Callback.ADMIN_BROADCAST + "$"),
            ],
            States.ADMIN_BROADCAST: [
                CallbackQueryHandler(start_over, pattern="^" + Callback.BACK + "$"),
                CallbackQueryHandler(broadcast_all_prompt, pattern="^" + Callback.ADMIN_BROADCAST_ALL + "$"),
                CallbackQueryHandler(broadcast_by_no, pattern="^" + Callback.ADMIN_BROADCAST_BY_NO + "$"),
            ],
            States.ADMIN_BROADCAST_MESSAGE_ALL: [
                CallbackQueryHandler(broadcast_menu, pattern="^" + Callback.BACK + "$"),
                MessageHandler(filters.TEXT, broadcast_all_message),
            ],
            States.ADMIN_BROADCAST_SELECT_NO: [
                CallbackQueryHandler(broadcast_menu, pattern="^" + Callback.BACK + "$"),
                MessageHandler(filters.TEXT, broadcast_enter_no_ids_message),
            ],
            States.ADMIN_BROADCAST_MESSAGE_SELECTED: [
                CallbackQueryHandler(broadcast_by_no, pattern="^" + Callback.BACK + "$"),
                MessageHandler(filters.TEXT, broadcast_selected_message),
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
