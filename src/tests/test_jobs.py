from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.csm_bot.app.storage import BotStorage
from src.csm_bot.jobs import JobContext, ALERT_INTERVAL_MINUTES
from src.csm_bot.texts import NO_NEW_BLOCKS_ADMIN_ALERT


class StubBot:
    def __init__(self):
        self.sent_messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent_messages.append((chat_id, text))


def _make_context(admin_ids: set[int], block: int, bot: StubBot) -> SimpleNamespace:
    bot_storage = BotStorage({"block": block})
    runtime = SimpleNamespace(config=SimpleNamespace(admin_ids=admin_ids))
    return SimpleNamespace(bot_storage=bot_storage, runtime=runtime, bot=bot)


def _make_subscription(chain_head: int = 0) -> SimpleNamespace:
    sub = SimpleNamespace()
    sub.get_block_number = AsyncMock(return_value=chain_head)
    return sub


@pytest.mark.asyncio
async def test_no_alert_when_chain_head_not_polled():
    bot = StubBot()
    context = _make_context({1}, block=100, bot=bot)
    job_context = JobContext(_make_subscription())

    # chain_head is 0 (not yet polled) -> no alert
    await job_context.callback_block_processing_check(context)
    assert not bot.sent_messages


@pytest.mark.asyncio
async def test_no_alert_on_first_check_after_poll():
    bot = StubBot()
    chain_head = 1000
    context = _make_context({1}, block=0, bot=bot)

    sub = _make_subscription(chain_head)
    job_context = JobContext(sub)
    job_context._chain_head = chain_head

    await job_context.callback_block_processing_check(context)
    assert job_context._last_checked_chain_head == chain_head
    assert not bot.sent_messages


@pytest.mark.asyncio
async def test_alert_when_chain_head_does_not_advance():
    admin_ids = {1, 99}
    bot = StubBot()
    chain_head = 1000
    context = _make_context(admin_ids, block=0, bot=bot)

    sub = _make_subscription(chain_head)
    job_context = JobContext(sub)
    job_context._last_checked_chain_head = chain_head
    job_context._chain_head = chain_head

    await job_context.callback_block_processing_check(context)
    expected_message = NO_NEW_BLOCKS_ADMIN_ALERT.format(
        minutes=ALERT_INTERVAL_MINUTES,
        block=chain_head,
    )
    assert sorted(bot.sent_messages) == sorted((aid, expected_message) for aid in admin_ids)


@pytest.mark.asyncio
async def test_alert_only_once_until_chain_head_advances():
    admin_ids = {1}
    bot = StubBot()
    chain_head = 1000
    context = _make_context(admin_ids, block=0, bot=bot)

    sub = _make_subscription(chain_head)
    job_context = JobContext(sub)
    job_context._last_checked_chain_head = chain_head
    job_context._chain_head = chain_head

    # First check -> alert
    await job_context.callback_block_processing_check(context)
    assert len(bot.sent_messages) == 1

    # Second check, still no progress -> no additional alert
    job_context._chain_head = chain_head
    await job_context.callback_block_processing_check(context)
    assert len(bot.sent_messages) == 1

    # Chain head advances -> reset
    job_context._chain_head = chain_head + 10
    await job_context.callback_block_processing_check(context)
    assert len(bot.sent_messages) == 1
    assert not job_context._alerted

    # Stalls again -> new alert
    await job_context.callback_block_processing_check(context)
    assert len(bot.sent_messages) == 2


@pytest.mark.asyncio
async def test_poll_chain_head():
    sub = _make_subscription(999_999)
    job_context = JobContext(sub)
    context = _make_context({1}, block=100, bot=StubBot())

    await job_context._poll_chain_head(context)
    assert job_context._chain_head == 999_999
    assert context.bot_storage.block.value == 999_999
    sub.get_block_number.assert_awaited_once()


@pytest.mark.asyncio
async def test_poll_chain_head_failure_does_not_crash():
    sub = _make_subscription()
    sub.get_block_number = AsyncMock(side_effect=Exception("connection lost"))
    job_context = JobContext(sub)
    job_context._chain_head = 42

    await job_context._poll_chain_head(None)
    # chain_head should remain unchanged after failure
    assert job_context._chain_head == 42
