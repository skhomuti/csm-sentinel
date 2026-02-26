from types import SimpleNamespace
from unittest.mock import AsyncMock

from hexbytes import HexBytes
import pytest

from src.csm_bot.app.storage import BotStorage
from src.csm_bot.models import Block, Event
from src.csm_bot.services.subscription import TelegramSubscription


def _make_event(block: int) -> Event:
    return Event(
        event="TestEvent",
        args={"nodeOperatorId": 1},
        block=block,
        tx=HexBytes("0xdeadbeef"),
        address="0x0000000000000000000000000000000000000000",
    )


def _make_context(block: int) -> SimpleNamespace:
    bot_storage = BotStorage({"block": block, "user_ids": set(), "no_ids_to_chats": {}})
    return SimpleNamespace(bot_storage=bot_storage, bot=AsyncMock())


def _make_subscription(event_messages_return=None) -> TelegramSubscription:
    sub = TelegramSubscription.__new__(TelegramSubscription)
    sub.event_messages = SimpleNamespace(
        get_notification_plan=AsyncMock(return_value=event_messages_return),
    )
    return sub


@pytest.mark.asyncio
async def test_handle_event_log_advances_persisted_block():
    sub = _make_subscription(event_messages_return=None)
    context = _make_context(block=100)

    await sub.handle_event_log(_make_event(block=200), context)

    assert context.bot_storage.block.value == 200


@pytest.mark.asyncio
async def test_handle_event_log_does_not_regress_persisted_block():
    sub = _make_subscription(event_messages_return=None)
    context = _make_context(block=500)

    await sub.handle_event_log(_make_event(block=300), context)

    assert context.bot_storage.block.value == 500


@pytest.mark.asyncio
async def test_handle_event_log_advances_block_with_notification_plan():
    plan = SimpleNamespace(
        per_node_operator={},
        broadcast=None,
        broadcast_node_operator_ids=None,
    )
    sub = _make_subscription(event_messages_return=plan)
    context = _make_context(block=100)

    await sub.handle_event_log(_make_event(block=200), context)

    assert context.bot_storage.block.value == 200


@pytest.mark.asyncio
async def test_process_new_block_advances_persisted_block():
    sub = TelegramSubscription.__new__(TelegramSubscription)
    sub.application = SimpleNamespace(bot_data={"block": 100})

    await sub.process_new_block(Block(number=200))

    assert BotStorage(sub.application.bot_data).block.value == 200


@pytest.mark.asyncio
async def test_process_new_block_does_not_regress_persisted_block():
    sub = TelegramSubscription.__new__(TelegramSubscription)
    sub.application = SimpleNamespace(bot_data={"block": 500})

    await sub.process_new_block(Block(number=300))

    assert BotStorage(sub.application.bot_data).block.value == 500
