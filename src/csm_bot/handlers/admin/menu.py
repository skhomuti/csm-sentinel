from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update

from csm_bot.handlers.admin.common import admin_only
from csm_bot.handlers.state import Callback, States
from csm_bot.handlers.utils import get_active_subscription_counts
from csm_bot.texts import (
    ADMIN_BUTTON_BROADCAST,
    ADMIN_BUTTON_SUBSCRIPTIONS,
    ADMIN_MENU_TEXT,
    BUTTON_BACK,
)
from csm_bot.utils import chunk_text

if TYPE_CHECKING:
    from csm_bot.app.context import BotContext

@admin_only(States.WELCOME)
async def admin_menu(update: Update, context: "BotContext") -> States:
    query = update.callback_query
    if query is not None:
        await query.answer()
    keyboard = [
        [InlineKeyboardButton(ADMIN_BUTTON_SUBSCRIPTIONS, callback_data=Callback.ADMIN_SUBSCRIPTIONS.value)],
        [InlineKeyboardButton(ADMIN_BUTTON_BROADCAST, callback_data=Callback.ADMIN_BROADCAST.value)],
        [InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK.value)],
    ]
    await query.edit_message_text(text=ADMIN_MENU_TEXT, reply_markup=InlineKeyboardMarkup(keyboard))
    return States.ADMIN


@admin_only(States.WELCOME)
async def subscriptions(update: Update, context: "BotContext"):
    query = update.callback_query
    if query is not None:
        await query.answer()

    counts = get_active_subscription_counts(context.bot_storage)

    if not counts:
        full_text = "No active subscriptions."
    else:
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
    back_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK.value)]])

    if query is not None:
        chat_id = query.message.chat_id if query.message else update.effective_chat.id
        if len(chunks) == 1:
            await query.edit_message_text(text=chunks[0], reply_markup=back_keyboard)
        else:
            await query.edit_message_text(text=chunks[0], reply_markup=None)
            for chunk in chunks[1:-1]:
                await context.bot.send_message(chat_id=chat_id, text=chunk)
            await context.bot.send_message(chat_id=chat_id, text=chunks[-1], reply_markup=back_keyboard)
        return States.ADMIN

    chat_id = update.effective_chat.id
    if len(chunks) == 1:
        await context.bot.send_message(chat_id=chat_id, text=chunks[0], reply_markup=back_keyboard)
    else:
        for chunk in chunks[:-1]:
            await context.bot.send_message(chat_id=chat_id, text=chunk)
        await context.bot.send_message(chat_id=chat_id, text=chunks[-1], reply_markup=back_keyboard)
    return States.WELCOME
