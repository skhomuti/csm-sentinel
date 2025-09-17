import logging
from typing import Iterable, Set

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from csm_bot.handlers.admin.common import admin_only
from csm_bot.handlers.state import Callback, States
from csm_bot.handlers.utils import (
    get_actual_chat_ids,
    reply_with_markup,
    resolve_target_chats_for_node_operators,
)
from csm_bot.texts import (
    ADMIN_BROADCAST_ALL,
    ADMIN_BROADCAST_BY_NO,
    ADMIN_BROADCAST_ENTER_MESSAGE_ALL,
    ADMIN_BROADCAST_ENTER_NO_IDS,
    ADMIN_BROADCAST_MENU_TEXT,
    ADMIN_BROADCAST_NO_IDS_INVALID,
    BUTTON_BACK,
)

logger = logging.getLogger(__name__)


@admin_only(States.WELCOME)
async def broadcast_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    query = update.callback_query
    if query is not None:
        await query.answer()
    keyboard = [
        [InlineKeyboardButton(ADMIN_BROADCAST_ALL, callback_data=Callback.ADMIN_BROADCAST_ALL.value)],
        [InlineKeyboardButton(ADMIN_BROADCAST_BY_NO, callback_data=Callback.ADMIN_BROADCAST_BY_NO.value)],
        [InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK.value)],
    ]
    await query.edit_message_text(text=ADMIN_BROADCAST_MENU_TEXT, reply_markup=InlineKeyboardMarkup(keyboard))
    return States.ADMIN_BROADCAST


@admin_only(States.WELCOME)
async def broadcast_all_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    query = update.callback_query
    if query is not None:
        await query.answer()
    keyboard = [[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK.value)]]
    await query.edit_message_text(
        text=ADMIN_BROADCAST_ENTER_MESSAGE_ALL,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return States.ADMIN_BROADCAST_MESSAGE_ALL


@admin_only(States.WELCOME)
async def broadcast_by_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    query = update.callback_query
    if query is not None:
        await query.answer()
    context.user_data.pop("broadcast_selected", None)
    keyboard = [[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK.value)]]
    await query.edit_message_text(
        text=ADMIN_BROADCAST_ENTER_NO_IDS,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return States.ADMIN_BROADCAST_SELECT_NO


@admin_only(States.ADMIN_BROADCAST_MESSAGE_ALL)
async def broadcast_all_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    message = update.message
    keyboard = [[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK.value)]]
    markup = InlineKeyboardMarkup(keyboard)
    if message is None or not message.text:
        await reply_with_markup(update, context, ADMIN_BROADCAST_ENTER_MESSAGE_ALL, markup)
        return States.ADMIN_BROADCAST_MESSAGE_ALL
    text = message.text.strip()
    if not text:
        await reply_with_markup(update, context, ADMIN_BROADCAST_ENTER_MESSAGE_ALL, markup)
        return States.ADMIN_BROADCAST_MESSAGE_ALL

    bot_data = context.bot_data
    all_subscribed: Set[int] = set()
    for chats in bot_data.get("no_ids_to_chats", {}).values():
        all_subscribed.update(chats)
    targets = all_subscribed.intersection(get_actual_chat_ids(bot_data))
    if not targets:
        await reply_with_markup(update, context, "No subscribers to notify.", markup)
        return States.ADMIN_BROADCAST_MESSAGE_ALL
    sent, failed = await _broadcast_to_chats(context, targets, text)
    await reply_with_markup(
        update,
        context,
        f"Broadcast sent to {sent} chat(s). Failures: {failed}.",
        markup,
    )
    return States.ADMIN_BROADCAST_MESSAGE_ALL


@admin_only(States.ADMIN_BROADCAST_SELECT_NO)
async def broadcast_enter_no_ids_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    message = update.message
    keyboard = [[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK.value)]]
    markup = InlineKeyboardMarkup(keyboard)
    if message is None or message.text is None:
        await reply_with_markup(update, context, ADMIN_BROADCAST_NO_IDS_INVALID, markup)
        return States.ADMIN_BROADCAST_SELECT_NO
    raw = message.text.strip()
    raw = raw.replace("#", "").replace(" ", ",")
    ids: set[str] = set()
    for token in filter(None, (t.strip() for t in raw.split(","))):
        if token.isdigit():
            ids.add(token)
    if not ids:
        await reply_with_markup(update, context, ADMIN_BROADCAST_NO_IDS_INVALID, markup)
        return States.ADMIN_BROADCAST_SELECT_NO
    context.user_data["broadcast_selected"] = ids
    pretty_ids = ", ".join(sorted(f"#{i}" for i in ids))
    await reply_with_markup(
        update,
        context,
        f"Enter message for: {pretty_ids}",
        markup,
    )
    return States.ADMIN_BROADCAST_MESSAGE_SELECTED


@admin_only(States.ADMIN_BROADCAST_MESSAGE_SELECTED)
async def broadcast_selected_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> States:
    message = update.message
    keyboard = [[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK.value)]]
    markup = InlineKeyboardMarkup(keyboard)

    if message is None or message.text is None:
        await reply_with_markup(update, context, "Message text is required.", markup)
        return States.ADMIN_BROADCAST_MESSAGE_SELECTED
    text = message.text.strip()
    selected = context.user_data.get("broadcast_selected")
    if not selected:
        await reply_with_markup(
            update,
            context,
            "No node operators selected.",
            markup,
        )
        return States.ADMIN_BROADCAST_SELECT_NO
    if not text:
        await reply_with_markup(update, context, "Message text is required.", markup)
        return States.ADMIN_BROADCAST_MESSAGE_SELECTED

    targets = resolve_target_chats_for_node_operators(context.bot_data, selected)
    if not targets:
        await reply_with_markup(
            update,
            context,
            "No active subscribers for the selected node operators.",
            markup,
        )
        return States.ADMIN_BROADCAST_MESSAGE_SELECTED

    sent, failed = await _broadcast_to_chats(context, targets, text)
    pretty_ids = ", ".join(sorted(f"#{i}" for i in selected))
    await reply_with_markup(
        update,
        context,
        f"Broadcast to {pretty_ids}: sent to {sent} chat(s). Failures: {failed}.",
        markup,
    )
    return States.ADMIN_BROADCAST_MESSAGE_SELECTED


async def _broadcast_to_chats(
    context: ContextTypes.DEFAULT_TYPE,
    chats: Iterable[int],
    text: str,
) -> tuple[int, int]:
    sent, failed = 0, 0
    for chat_id in chats:
        try:
            await context.bot.send_message(chat_id=chat_id, text=text)
            sent += 1
        except Exception as exc:  # pragma: no cover - depends on Telegram runtime
            logger.error("Broadcast error to %s: %s", chat_id, exc)
            failed += 1
    return sent, failed
