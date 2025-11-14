from functools import wraps
from typing import TYPE_CHECKING

from telegram.constants import ChatType

from csm_bot.handlers.state import States
from csm_bot.handlers.utils import is_admin
from csm_bot.texts import ADMIN_PRIVATE_CHAT_REQUIRED

if TYPE_CHECKING:
    from csm_bot.app.context import BotContext


async def _notify_not_authorized(update, context: "BotContext") -> None:
    query = update.callback_query
    if query is not None:
        await query.answer()
        chat_id = query.message.chat_id if query.message else update.effective_chat.id
    else:
        chat = update.effective_chat
        chat_id = chat.id if chat is not None else None

    if chat_id is not None:
        await context.bot.send_message(chat_id=chat_id, text="Not authorized.")


async def _notify_private_chat_required(update, context: "BotContext") -> None:
    chat = update.effective_chat
    if chat is None:
        return
    await context.bot.send_message(chat_id=chat.id, text=ADMIN_PRIVATE_CHAT_REQUIRED)


def admin_only(failure_state: States):
    """Decorate a handler to ensure only admins can invoke it."""

    def decorator(func):
        @wraps(func)
        async def wrapper(update, context: "BotContext", *args, **kwargs):
            user = update.effective_user
            if user is None or not is_admin(user.id, context):
                await _notify_not_authorized(update, context)
                return failure_state
            chat = update.effective_chat
            if chat is None or chat.type != ChatType.PRIVATE:
                await _notify_private_chat_required(update, context)
                return failure_state
            return await func(update, context, *args, **kwargs)

        return wrapper

    return decorator
