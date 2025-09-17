import logging
from typing import Iterable, Set

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def is_admin(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True if the given Telegram user_id is registered as an admin."""
    return user_id in context.application.bot_data.get("admin_ids", set())


async def reply_with_markup(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    message = update.message
    if message is not None:
        await message.reply_text(text, reply_markup=reply_markup)
        return

    chat = update.effective_chat
    if chat is not None:
        await context.bot.send_message(chat_id=chat.id, text=text, reply_markup=reply_markup)
        return

    logger.warning("Cannot send reply for update without message or chat: %s", update)


def get_actual_chat_ids(bot_data: dict) -> Set[int]:
    """Return chat IDs where the bot is currently present."""
    return (
        bot_data.get("user_ids", set())
        .union(bot_data.get("group_ids", set()))
        .union(bot_data.get("channel_ids", set()))
    )


def resolve_target_chats_for_node_operators(
    bot_data: dict,
    node_operator_ids: Iterable[str],
) -> Set[int]:
    actual = get_actual_chat_ids(bot_data)
    targets: set[int] = set()
    for no_id in node_operator_ids:
        chats = bot_data.get("no_ids_to_chats", {}).get(no_id, set())
        if chats:
            targets.update(chats)
    return targets.intersection(actual)


def get_active_subscription_counts(bot_data: dict) -> dict[str, dict[str, int]]:
    """Compute active subscription counts per node operator, broken down by chat type."""
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
