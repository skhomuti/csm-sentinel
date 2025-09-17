import logging

from csm_bot.app.bootstrap import create_runtime, run
from csm_bot.events import EVENTS_TO_FOLLOW
from csm_bot.handlers import register_handlers
from csm_bot.texts import EVENT_DESCRIPTIONS, EVENT_MESSAGES

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)



def _assert_event_mappings() -> None:
    events = set(EVENTS_TO_FOLLOW.keys())
    messages = set(EVENT_MESSAGES.keys())
    descriptions = set(EVENT_DESCRIPTIONS.keys())
    assert events == messages, "Missed events: " + str(events.symmetric_difference(messages))
    assert events == descriptions, "Missed events: " + str(events.symmetric_difference(descriptions))


if __name__ == "__main__":
    _assert_event_mappings()
    runtime = create_runtime()
    register_handlers(runtime)
    logger.info("Starting CSM bot")
    run(runtime)
