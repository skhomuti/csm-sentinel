import logging
from typing import TYPE_CHECKING

from telegram import Chat, ChatMember, ChatMemberUpdated, Update

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from csm_bot.app.context import BotContext


async def chat_migration(update: Update, context: "BotContext") -> None:
    message = update.message
    if message is not None:
        context.application.migrate_chat_data(message=message)


async def add_user_if_required(update: Update, context: "BotContext") -> None:
    chat = update.effective_chat
    storage = context.bot_storage

    if chat.type != Chat.PRIVATE or storage.users.contains(chat.id):
        return

    logger.info("%s started a private chat with the bot", update.effective_user.full_name)
    storage.users.add(chat.id)


def extract_status_change(chat_member_update: ChatMemberUpdated) -> tuple[bool, bool] | None:
    """Determine membership change for a chat member update."""
    status_change = chat_member_update.difference().get("status")
    old_is_member, new_is_member = chat_member_update.difference().get("is_member", (None, None))

    if status_change is None:
        return None

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


async def track_chats(update: Update, context: "BotContext") -> None:
    """Track joins/leaves across private chats, groups, and channels."""
    result = extract_status_change(update.my_chat_member)
    if result is None:
        return
    was_member, is_member = result

    cause_name = update.effective_user.full_name
    chat = update.effective_chat
    storage = context.bot_storage
    if chat.type == Chat.PRIVATE:
        if not was_member and is_member:
            logger.info("%s unblocked the bot", cause_name)
            storage.users.add(chat.id)
        elif was_member and not is_member:
            logger.info("%s blocked the bot", cause_name)
            storage.users.remove(chat.id)
    elif chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
        if not was_member and is_member:
            logger.info("%s added the bot to the group %s", cause_name, chat.title)
            storage.groups.add(chat.id)
        elif was_member and not is_member:
            logger.info("%s removed the bot from the group %s", cause_name, chat.title)
            storage.groups.remove(chat.id)
    elif not was_member and is_member:
        logger.info("%s added the bot to the channel %s", cause_name, chat.title)
        storage.channels.add(chat.id)
    elif was_member and not is_member:
        logger.info("%s removed the bot from the channel %s", cause_name, chat.title)
        storage.channels.remove(chat.id)
