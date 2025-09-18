from dataclasses import dataclass
from typing import TYPE_CHECKING

from csm_bot.config import Config

if TYPE_CHECKING:
    from telegram.ext import Application

    from csm_bot.events import EventMessages
    from csm_bot.jobs import JobContext
    from csm_bot.services.subscription import TelegramSubscription


_RUNTIME_ATTR = "_csm_runtime"


@dataclass(slots=True)
class BotRuntime:
    """Lightweight container for the long-lived bot context."""

    config: Config
    application: "Application"
    subscription: "TelegramSubscription"
    event_messages: "EventMessages"
    job_context: "JobContext"


def attach_runtime(runtime: BotRuntime) -> None:
    """Attach the runtime to the Application instance for easy lookup."""
    setattr(runtime.application, _RUNTIME_ATTR, runtime)


def get_runtime_from_application(application: "Application") -> BotRuntime:
    runtime = getattr(application, _RUNTIME_ATTR, None)
    if runtime is None:
        raise RuntimeError("Bot runtime is not attached to the application")
    return runtime
