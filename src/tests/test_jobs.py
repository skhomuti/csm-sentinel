from types import SimpleNamespace

import pytest

from src.csm_bot.app.storage import BotStorage
from src.csm_bot.jobs import JobContext
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


@pytest.mark.asyncio
async def test_job_context_notifies_admins_only_once_per_block():
    admin_ids = {1, 99}
    bot = StubBot()
    context = _make_context(admin_ids, block=123_456, bot=bot)

    job_context = JobContext()

    # Initial run seeds the latest block without notifying.
    await job_context.callback_block_processing_check(context)
    assert job_context.latest_block == 123_456
    assert not bot.sent_messages

    # Second run without progress triggers a single alert to all admins.
    await job_context.callback_block_processing_check(context)
    expected_message = NO_NEW_BLOCKS_ADMIN_ALERT.format(
        minutes=job_context.alert_interval_minutes,
        block=123_456,
    )
    assert sorted(bot.sent_messages) == sorted((admin_id, expected_message) for admin_id in admin_ids)

    # Further runs for the same block do not re-alert until progress happens.
    await job_context.callback_block_processing_check(context)
    assert len(bot.sent_messages) == len(admin_ids)

    # Simulate new block -> state resets.
    context.bot_storage.block.update(123_457)
    await job_context.callback_block_processing_check(context)
    assert job_context.latest_block == 123_457
    assert job_context.alerted_for_block is None

    # Stalling again on the new block should notify one more time.
    await job_context.callback_block_processing_check(context)
    assert len(bot.sent_messages) == len(admin_ids) * 2
