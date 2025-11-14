from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from csm_bot.app.runtime import BotRuntime
from csm_bot.handlers import start, tracking
from csm_bot.handlers.admin import (
    admin_menu,
    broadcast_all_confirm,
    broadcast_all_message,
    broadcast_all_prompt,
    broadcast_by_no,
    broadcast_enter_no_ids_message,
    broadcast_menu,
    broadcast_selected_confirm,
    broadcast_selected_message,
    subscriptions,
)
from csm_bot.handlers.state import Callback, States


def build_conversation_handler() -> ConversationHandler:
    text_without_commands = filters.TEXT & ~filters.COMMAND
    return ConversationHandler(
        entry_points=[CommandHandler("start", start.start)],
        states={
            States.WELCOME: [
                CallbackQueryHandler(
                    start.follow_node_operator,
                    pattern="^" + Callback.FOLLOW_TO_NODE_OPERATOR.value + "$",
                ),
                CallbackQueryHandler(
                    start.unfollow_node_operator,
                    pattern="^" + Callback.UNFOLLOW_FROM_NODE_OPERATOR.value + "$",
                ),
                CallbackQueryHandler(
                    start.followed_events,
                    pattern="^" + Callback.FOLLOWED_EVENTS.value + "$",
                ),
                CallbackQueryHandler(
                    admin_menu,
                    pattern="^" + Callback.ADMIN.value + "$",
                ),
            ],
            States.FOLLOW_NODE_OPERATOR: [
                CallbackQueryHandler(start.start_over, pattern="^" + Callback.BACK.value + "$"),
                MessageHandler(text_without_commands, start.follow_node_operator_message),
            ],
            States.UNFOLLOW_NODE_OPERATOR: [
                CallbackQueryHandler(start.start_over, pattern="^" + Callback.BACK.value + "$"),
                MessageHandler(text_without_commands, start.unfollow_node_operator_message),
            ],
            States.FOLLOWED_EVENTS: [
                CallbackQueryHandler(start.start_over, pattern="^" + Callback.BACK.value + "$"),
            ],
            States.ADMIN: [
                CallbackQueryHandler(start.start_over, pattern="^" + Callback.BACK.value + "$"),
                CallbackQueryHandler(subscriptions, pattern="^" + Callback.ADMIN_SUBSCRIPTIONS.value + "$"),
                CallbackQueryHandler(broadcast_menu, pattern="^" + Callback.ADMIN_BROADCAST.value + "$"),
            ],
            States.ADMIN_BROADCAST: [
                CallbackQueryHandler(start.start_over, pattern="^" + Callback.BACK.value + "$"),
                CallbackQueryHandler(
                    broadcast_all_prompt,
                    pattern="^" + Callback.ADMIN_BROADCAST_ALL.value + "$",
                ),
                CallbackQueryHandler(
                    broadcast_by_no,
                    pattern="^" + Callback.ADMIN_BROADCAST_BY_NO.value + "$",
                ),
            ],
            States.ADMIN_BROADCAST_MESSAGE_ALL: [
                CallbackQueryHandler(broadcast_menu, pattern="^" + Callback.BACK.value + "$"),
                CallbackQueryHandler(
                    broadcast_all_confirm,
                    pattern="^" + Callback.ADMIN_BROADCAST_CONFIRM_ALL.value + "$",
                ),
                MessageHandler(text_without_commands, broadcast_all_message),
            ],
            States.ADMIN_BROADCAST_SELECT_NO: [
                CallbackQueryHandler(broadcast_menu, pattern="^" + Callback.BACK.value + "$"),
                MessageHandler(text_without_commands, broadcast_enter_no_ids_message),
            ],
            States.ADMIN_BROADCAST_MESSAGE_SELECTED: [
                CallbackQueryHandler(broadcast_by_no, pattern="^" + Callback.BACK.value + "$"),
                CallbackQueryHandler(
                    broadcast_selected_confirm,
                    pattern="^" + Callback.ADMIN_BROADCAST_CONFIRM_SELECTED.value + "$",
                ),
                MessageHandler(text_without_commands, broadcast_selected_message),
            ],
        },
        fallbacks=[CommandHandler("start", start.start)],
    )


def register_handlers(runtime: BotRuntime) -> None:
    application: Application = runtime.application

    conversation_handler = build_conversation_handler()

    application.add_handler(ChatMemberHandler(tracking.track_chats, ChatMemberHandler.MY_CHAT_MEMBER))
    application.add_handler(conversation_handler)
    application.add_handler(MessageHandler(filters.StatusUpdate.MIGRATE, tracking.chat_migration))
    runtime.subscription.register_handlers()
