import logging
from typing import Iterable, Set, TYPE_CHECKING

from telegram import InlineKeyboardMarkup, Update

from csm_bot.app.storage import BotStorage

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from csm_bot.app.context import BotContext


def is_admin(user_id: int, context: "BotContext") -> bool:
    """Return True if the given Telegram user_id is registered as an admin."""
    return user_id in context.application.bot_data.get("admin_ids", set())


async def reply_with_markup(
    update: Update,
    context: "BotContext",
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


def resolve_target_chats_for_node_operators(
    storage: BotStorage,
    node_operator_ids: Iterable[str],
) -> Set[int]:
    return storage.resolve_target_chats(node_operator_ids)


def get_active_subscription_counts(storage: BotStorage) -> dict[str, dict[str, int]]:
    """Compute active subscription counts per node operator, broken down by chat type."""
    return storage.subscription_counts()


def get_subscription_totals(storage: BotStorage) -> tuple[int, int]:
    """Return total active subscribers and node operators with active subscriptions."""
    active_counts = storage.subscription_counts()
    active_subscribers = storage.resolve_target_chats(storage.node_operator_chats.ids())
    return len(active_subscribers), len(active_counts)
