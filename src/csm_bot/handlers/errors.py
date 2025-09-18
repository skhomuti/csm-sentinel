import logging

import httpx
import telegram.error

logger = logging.getLogger(__name__)


async def error_handler(update: object, context) -> None:
    if update is None:
        logger.error("A %s occurred: %s", context.error.__class__.__name__, context.error)
    else:
        logger.error("Update %s caused error %s", update, context.error)


def build_error_callback(application):
    """Return an error callback suited for updater.start_polling."""

    def error_callback(error: Exception) -> None:
        if isinstance(error, (telegram.error.Conflict, httpx.ReadError)):
            application.create_task(application.process_error(update=None, error=error))
            return
        logger.error("Unhandled polling error: %s", error)

    return error_callback
