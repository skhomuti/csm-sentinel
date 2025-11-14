import logging
from typing import Iterable, TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.error import BadRequest, TelegramError

from csm_bot.handlers.admin.common import admin_only
from csm_bot.handlers.state import Callback, States
from csm_bot.handlers.utils import resolve_target_chats_for_node_operators
from csm_bot.texts import (
    ADMIN_BROADCAST_ALL,
    ADMIN_BROADCAST_BY_NO,
    ADMIN_BROADCAST_CONFIRM_HINT,
    ADMIN_BROADCAST_ENTER_MESSAGE_ALL,
    ADMIN_BROADCAST_ENTER_NO_IDS,
    ADMIN_BROADCAST_MENU_TEXT,
    ADMIN_BROADCAST_NO_IDS_INVALID,
    ADMIN_BROADCAST_PREVIEW_ALL,
    ADMIN_BROADCAST_PREVIEW_SELECTED,
    BUTTON_BACK,
    BUTTON_SEND_BROADCAST,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from csm_bot.app.context import BotContext


class BroadcastSession:
    PROMPT_CHAT_ID_KEY = "broadcast_prompt_chat_id"
    PROMPT_MESSAGE_ID_KEY = "broadcast_prompt_message_id"
    MESSAGE_TEXT_KEY = "broadcast_message_text"
    SELECTED_IDS_KEY = "broadcast_selected"

    def __init__(self, context: "BotContext") -> None:
        self._context = context

    def store_prompt(self, message: Message | None) -> None:
        if message is None:
            return
        self._context.user_data[self.PROMPT_CHAT_ID_KEY] = message.chat_id
        self._context.user_data[self.PROMPT_MESSAGE_ID_KEY] = message.message_id

    def clear_prompt(self) -> None:
        self._context.user_data.pop(self.PROMPT_CHAT_ID_KEY, None)
        self._context.user_data.pop(self.PROMPT_MESSAGE_ID_KEY, None)

    def set_message_text(self, text: str) -> None:
        self._context.user_data[self.MESSAGE_TEXT_KEY] = text

    def get_message_text(self) -> str | None:
        return self._context.user_data.get(self.MESSAGE_TEXT_KEY)

    def clear_message_text(self) -> None:
        self._context.user_data.pop(self.MESSAGE_TEXT_KEY, None)

    def set_selected_ids(self, ids: set[str]) -> None:
        self._context.user_data[self.SELECTED_IDS_KEY] = ids

    def get_selected_ids(self) -> set[str] | None:
        selected = self._context.user_data.get(self.SELECTED_IDS_KEY)
        return selected if isinstance(selected, set) else None

    def clear_selected_ids(self) -> None:
        self._context.user_data.pop(self.SELECTED_IDS_KEY, None)

    def get_prompt_chat_id(self) -> int | None:
        return self._context.user_data.get(self.PROMPT_CHAT_ID_KEY)

    def get_prompt_message_id(self) -> int | None:
        return self._context.user_data.get(self.PROMPT_MESSAGE_ID_KEY)


@admin_only(failure_state=States.WELCOME)
async def broadcast_menu(update: Update, context: "BotContext") -> States:
    query = update.callback_query
    if query is None:
        return States.ADMIN_BROADCAST
    await query.answer()
    session = BroadcastSession(context)
    keyboard = [
        [InlineKeyboardButton(ADMIN_BROADCAST_ALL, callback_data=Callback.ADMIN_BROADCAST_ALL.value)],
        [InlineKeyboardButton(ADMIN_BROADCAST_BY_NO, callback_data=Callback.ADMIN_BROADCAST_BY_NO.value)],
        [InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK.value)],
    ]
    updated_message = await query.edit_message_text(
        text=ADMIN_BROADCAST_MENU_TEXT,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    session.store_prompt(updated_message)
    session.clear_message_text()
    session.clear_selected_ids()
    return States.ADMIN_BROADCAST


@admin_only(failure_state=States.WELCOME)
async def broadcast_all_prompt(update: Update, context: "BotContext") -> States:
    query = update.callback_query
    if query is None:
        return States.ADMIN_BROADCAST_MESSAGE_ALL
    await query.answer()
    session = BroadcastSession(context)
    keyboard = [[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK.value)]]
    updated_message = await query.edit_message_text(
        text=ADMIN_BROADCAST_ENTER_MESSAGE_ALL,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    session.store_prompt(updated_message)
    session.clear_message_text()
    return States.ADMIN_BROADCAST_MESSAGE_ALL


@admin_only(failure_state=States.WELCOME)
async def broadcast_by_no(update: Update, context: "BotContext") -> States:
    query = update.callback_query
    if query is None:
        return States.ADMIN_BROADCAST_SELECT_NO
    await query.answer()
    session = BroadcastSession(context)
    session.clear_selected_ids()
    session.clear_message_text()
    keyboard = [[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK.value)]]
    updated_message = await query.edit_message_text(
        text=ADMIN_BROADCAST_ENTER_NO_IDS,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    session.store_prompt(updated_message)
    return States.ADMIN_BROADCAST_SELECT_NO


@admin_only(failure_state=States.ADMIN_BROADCAST_MESSAGE_ALL)
async def broadcast_all_message(update: Update, context: "BotContext") -> States:
    message = update.message
    chat_id = _resolve_chat_id(message, update)
    if chat_id is None:
        return States.ADMIN_BROADCAST_MESSAGE_ALL
    session = BroadcastSession(context)
    text = (message.text or "").strip() if message and message.text else ""
    await _delete_user_message(message)

    if not text:
        await _edit_broadcast_prompt_message(
            context,
            chat_id,
            ADMIN_BROADCAST_ENTER_MESSAGE_ALL,
            _back_markup(),
        )
        return States.ADMIN_BROADCAST_MESSAGE_ALL

    session.set_message_text(text)
    await _edit_broadcast_prompt_message(
        context,
        chat_id,
        _format_preview_text(ADMIN_BROADCAST_PREVIEW_ALL, text),
        _confirmation_markup(Callback.ADMIN_BROADCAST_CONFIRM_ALL),
    )
    return States.ADMIN_BROADCAST_MESSAGE_ALL


@admin_only(failure_state=States.ADMIN_BROADCAST_SELECT_NO)
async def broadcast_enter_no_ids_message(update: Update, context: "BotContext") -> States:
    message = update.message
    chat_id = _resolve_chat_id(message, update)
    if chat_id is None:
        return States.ADMIN_BROADCAST_SELECT_NO
    session = BroadcastSession(context)

    raw_input = (message.text or "").strip() if message and message.text else ""
    await _delete_user_message(message)

    if not raw_input:
        await _edit_broadcast_prompt_message(
            context,
            chat_id,
            f"{ADMIN_BROADCAST_NO_IDS_INVALID}\n\n{ADMIN_BROADCAST_ENTER_NO_IDS}",
            _back_markup(),
        )
        return States.ADMIN_BROADCAST_SELECT_NO

    raw = raw_input
    raw = raw.replace("#", "").replace(" ", ",")
    ids: set[str] = set()
    for token in filter(None, (t.strip() for t in raw.split(","))):
        if token.isdigit():
            ids.add(token)
    if not ids:
        await _edit_broadcast_prompt_message(
            context,
            chat_id,
            f"{ADMIN_BROADCAST_NO_IDS_INVALID}\n\n{ADMIN_BROADCAST_ENTER_NO_IDS}",
            _back_markup(),
        )
        return States.ADMIN_BROADCAST_SELECT_NO
    session.set_selected_ids(ids)
    session.clear_message_text()
    pretty_ids = ", ".join(sorted(f"#{i}" for i in ids))
    prompt_text = (
        f"Node operators selected: {pretty_ids}\n\n"
        "Please enter the message to broadcast to these node operators:"
    )
    await _edit_broadcast_prompt_message(
        context,
        chat_id,
        prompt_text,
        _back_markup(),
    )
    return States.ADMIN_BROADCAST_MESSAGE_SELECTED


@admin_only(failure_state=States.ADMIN_BROADCAST_MESSAGE_SELECTED)
async def broadcast_selected_message(update: Update, context: "BotContext") -> States:
    message = update.message
    chat_id = _resolve_chat_id(message, update)
    if chat_id is None:
        return States.ADMIN_BROADCAST_MESSAGE_SELECTED
    session = BroadcastSession(context)
    text = (message.text or "").strip() if message and message.text else ""
    await _delete_user_message(message)

    selected = session.get_selected_ids()
    if not selected:
        await _edit_broadcast_prompt_message(
            context,
            chat_id,
            "No node operators selected. Please provide node operator IDs first.",
            _back_markup(),
        )
        return States.ADMIN_BROADCAST_SELECT_NO
    if not text:
        pretty_ids = ", ".join(sorted(f"#{i}" for i in selected))
        await _edit_broadcast_prompt_message(
            context,
            chat_id,
            f"Message text is required for: {pretty_ids}. Please type the broadcast message.",
            _back_markup(),
        )
        return States.ADMIN_BROADCAST_MESSAGE_SELECTED

    pretty_ids = ", ".join(sorted(f"#{i}" for i in selected))
    session.set_message_text(text)
    header = ADMIN_BROADCAST_PREVIEW_SELECTED.format(targets=pretty_ids)
    await _edit_broadcast_prompt_message(
        context,
        chat_id,
        _format_preview_text(header, text),
        _confirmation_markup(Callback.ADMIN_BROADCAST_CONFIRM_SELECTED),
    )
    return States.ADMIN_BROADCAST_MESSAGE_SELECTED


@admin_only(failure_state=States.ADMIN_BROADCAST_MESSAGE_ALL)
async def broadcast_all_confirm(update: Update, context: "BotContext") -> States:
    query = update.callback_query
    if query is None:
        return States.ADMIN_BROADCAST_MESSAGE_ALL
    await query.answer()
    session = BroadcastSession(context)
    text = session.get_message_text()
    if not text:
        updated = await query.edit_message_text(
            text=ADMIN_BROADCAST_ENTER_MESSAGE_ALL,
            reply_markup=_back_markup(),
        )
        session.store_prompt(updated)
        return States.ADMIN_BROADCAST_MESSAGE_ALL

    bot_storage = context.bot_storage
    targets = bot_storage.resolve_target_chats(bot_storage.node_operator_chats.ids())
    if not targets:
        updated = await query.edit_message_text(
            text="No subscribers to notify.",
            reply_markup=_back_markup(),
        )
        session.store_prompt(updated)
        return States.ADMIN_BROADCAST_MESSAGE_ALL

    sent, failed = await _broadcast_to_chats(context, targets, text)
    logger.info("Admin broadcast (all) attempted: sent=%s failed=%s", sent, failed)
    session.clear_message_text()
    result_text = f"Broadcast sent to {sent} chat(s). Failures: {failed}."
    updated = await query.edit_message_text(text=result_text, reply_markup=_back_markup())
    session.store_prompt(updated)
    return States.ADMIN_BROADCAST_MESSAGE_ALL


@admin_only(failure_state=States.ADMIN_BROADCAST_MESSAGE_SELECTED)
async def broadcast_selected_confirm(update: Update, context: "BotContext") -> States:
    query = update.callback_query
    if query is None:
        return States.ADMIN_BROADCAST_MESSAGE_SELECTED
    await query.answer()
    session = BroadcastSession(context)
    selected = session.get_selected_ids()
    if not selected:
        updated = await query.edit_message_text(
            text="No node operators selected. Please enter their IDs to continue.",
            reply_markup=_back_markup(),
        )
        session.store_prompt(updated)
        return States.ADMIN_BROADCAST_SELECT_NO

    text = session.get_message_text()
    if not text:
        pretty_ids = ", ".join(sorted(f"#{i}" for i in selected))
        updated = await query.edit_message_text(
            text=f"Message text is required for: {pretty_ids}. Please type it.",
            reply_markup=_back_markup(),
        )
        session.store_prompt(updated)
        return States.ADMIN_BROADCAST_MESSAGE_SELECTED

    bot_storage = context.bot_storage
    targets = resolve_target_chats_for_node_operators(bot_storage, selected)
    if not targets:
        updated = await query.edit_message_text(
            text="No active subscribers for the selected node operators.",
            reply_markup=_back_markup(),
        )
        session.store_prompt(updated)
        return States.ADMIN_BROADCAST_MESSAGE_SELECTED

    sent, failed = await _broadcast_to_chats(context, targets, text)
    pretty_ids = ", ".join(sorted(f"#{i}" for i in selected))
    logger.info(
        "Admin broadcast (selected) attempted: node_operators=%s sent=%s failed=%s",
        pretty_ids,
        sent,
        failed,
    )
    session.clear_message_text()
    session.clear_selected_ids()
    result_text = f"Broadcast to {pretty_ids}: sent to {sent} chat(s). Failures: {failed}."
    updated = await query.edit_message_text(text=result_text, reply_markup=_back_markup())
    session.store_prompt(updated)
    return States.ADMIN_BROADCAST_MESSAGE_SELECTED


async def _broadcast_to_chats(
    context: "BotContext",
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


async def _edit_broadcast_prompt_message(
    context: "BotContext",
    chat_id: int | None,
    text: str,
    reply_markup: InlineKeyboardMarkup | None,
) -> None:
    session = BroadcastSession(context)
    target_chat_id = chat_id or session.get_prompt_chat_id()
    if target_chat_id is None:
        logger.warning("Cannot edit broadcast prompt without a chat id")
        return
    message_id = session.get_prompt_message_id()
    if not message_id:
        sent = await context.bot.send_message(chat_id=target_chat_id, text=text, reply_markup=reply_markup)
        session.store_prompt(sent)
        return
    try:
        updated = await context.bot.edit_message_text(
            chat_id=target_chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
        )
        session.store_prompt(updated)
    except BadRequest as exc:
        logger.debug("Failed to edit broadcast prompt message: %s", exc)
        sent = await context.bot.send_message(chat_id=target_chat_id, text=text, reply_markup=reply_markup)
        session.store_prompt(sent)


async def _delete_user_message(message: Message | None) -> None:
    if message is None:
        return
    try:
        await message.delete()
    except TelegramError as exc:
        logger.debug("Failed to delete admin broadcast input: %s", exc)


def _back_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK.value)]])


def _confirmation_markup(callback: Callback) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(BUTTON_SEND_BROADCAST, callback_data=callback.value)],
            [InlineKeyboardButton(BUTTON_BACK, callback_data=Callback.BACK.value)],
        ]
    )


def _format_preview_text(header: str, message_text: str) -> str:
    return f"{header}\n\n{ADMIN_BROADCAST_CONFIRM_HINT}\n\n{message_text}"


def _resolve_chat_id(message: Message | None, update: Update) -> int | None:
    if message is not None:
        return message.chat_id
    chat = update.effective_chat
    return chat.id if chat is not None else None
