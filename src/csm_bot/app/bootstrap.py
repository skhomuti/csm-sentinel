import asyncio
import logging
from pathlib import Path

from telegram.ext import AIORateLimiter, ApplicationBuilder, ContextTypes
from web3 import AsyncWeb3, WebSocketProvider

from csm_bot.app.context import BotContext
from csm_bot.app.module_adapter import build_module_adapter_from_config
from csm_bot.app.runtime import BotRuntime, attach_runtime
from csm_bot.app.storage import create_persistence
from csm_bot.config import get_config
from csm_bot.utils import normalize_block_number
from csm_bot.handlers.errors import error_handler, build_error_callback
from csm_bot.services.subscription import TelegramSubscription
from csm_bot.events import EventMessages
from csm_bot.jobs import JobContext

logger = logging.getLogger(__name__)


def create_runtime() -> BotRuntime:
    cfg = get_config()

    storage_path = Path(cfg.filestorage_path)
    storage_path.mkdir(parents=True, exist_ok=True)

    persistence = create_persistence(storage_path)

    context_types = ContextTypes(context=BotContext)

    application = (
        ApplicationBuilder()
        .token(cfg.token)
        .context_types(context_types)
        .persistence(persistence)
        .rate_limiter(AIORateLimiter(max_retries=5))
        .build()
    )

    persistent_provider = AsyncWeb3(
        WebSocketProvider(cfg.web3_socket_provider, max_connection_retries=-1)
    )
    rpc_provider = AsyncWeb3(
        WebSocketProvider(cfg.web3_socket_provider, max_connection_retries=-1)
    )

    module_adapter = build_module_adapter_from_config(cfg, rpc_provider)
    event_messages = EventMessages(rpc_provider, module_adapter)
    subscription = TelegramSubscription(
        persistent_provider,
        application,
        event_messages,
        module_adapter.allowed_events(),
    )
    job_context = JobContext()

    runtime = BotRuntime(
        config=cfg,
        application=application,
        subscription=subscription,
        event_messages=event_messages,
        job_context=job_context,
        module_adapter=module_adapter,
    )
    attach_runtime(runtime)
    return runtime


async def _run(runtime: BotRuntime) -> None:
    application = runtime.application
    subscription = runtime.subscription
    job_context = runtime.job_context
    cfg = runtime.config

    await application.initialize()
    await application.start()
    application.add_error_handler(error_handler)

    subscription.ensure_state_containers()

    application.bot_data["admin_ids"] = cfg.admin_ids

    block_from = (
        cfg.block_from
        if cfg.block_from is not None
        else normalize_block_number(application.bot_data.get("block"))
    )

    await job_context.schedule(application)

    logger.info(
        "Bot started. Latest processed block number: %s",
        block_from,
    )

    try:
        error_callback = build_error_callback(application)
        await application.updater.start_polling(error_callback=error_callback)
        subscription.setup_signal_handlers(asyncio.get_running_loop())
        if block_from:
            await subscription.process_blocks_from(block_from)
        await subscription.subscribe()
    except asyncio.CancelledError:  # pragma: no cover - shutdown guard
        pass
    finally:
        await subscription.shutdown()
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


def run(runtime: BotRuntime) -> None:
    asyncio.run(_run(runtime))
