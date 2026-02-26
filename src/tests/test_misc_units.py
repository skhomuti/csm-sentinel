import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import patch

from hexbytes import HexBytes
import pytest

from csm_bot.config import clear_config


def test_event_readable_string():
    from src.csm_bot.models import Event

    event = Event(
        event="TestEvent",
        args={"a": 1, "b": 2},
        block=100,
        tx=HexBytes("0x" + "00" * 32),
        address="0x0000000000000000000000000000000000000000",
    )
    s = event.readable()
    assert s.startswith("TestEvent(")
    assert "a=1" in s and "b=2" in s


def test_main_subscription_helpers_counts():
    from src.csm_bot.handlers.utils import get_active_subscription_counts, get_subscription_totals
    from src.csm_bot.app.storage import BotStorage

    bot_data = {
        "user_ids": {1},
        "group_ids": {2},
        "channel_ids": {3},
        "no_ids_to_chats": {
            "10": {1, 2},  # one user, one group
            "20": {2, 4},  # one group, one inactive
        },
    }

    storage = BotStorage(bot_data)
    counts = get_active_subscription_counts(storage)
    assert counts["10"]["total"] == 2
    assert counts["10"]["users"] == 1
    assert counts["10"]["groups"] == 1
    assert counts["10"]["channels"] == 0

    assert counts["20"]["total"] == 1
    assert counts["20"]["users"] == 0
    assert counts["20"]["groups"] == 1
    assert counts["20"]["channels"] == 0

    subscribers, node_operators = get_subscription_totals(storage)
    assert subscribers == 2  # chat ids 1 and 2 are active across all NOs
    assert node_operators == 2


def test_main_resolve_target_chats():
    from src.csm_bot.handlers.utils import resolve_target_chats_for_node_operators
    from src.csm_bot.app.storage import BotStorage

    bot_data = {
        "user_ids": {1},
        "group_ids": {2},
        "channel_ids": {3},
        "no_ids_to_chats": {
            "10": {1, 2},
            "20": {2, 4},
        },
    }
    storage = BotStorage(bot_data)
    targets = resolve_target_chats_for_node_operators(storage, {"10", "20"})
    assert targets == {1, 2}


def test_texts_manager_address_change_proposed_messages():
    from web3.constants import ADDRESS_ZERO
    from src.csm_bot.texts import node_operator_manager_address_change_proposed

    msg_revoked = node_operator_manager_address_change_proposed(ADDRESS_ZERO)
    assert "revoked" in msg_revoked

    msg_proposed = node_operator_manager_address_change_proposed("0x123")
    assert "New manager address proposed" in msg_proposed


@patch.dict(
    os.environ,
    {
        "ETHERSCAN_URL": "https://etherscan.io",
        "BEACONCHAIN_URL": "https://beaconcha.in",
        "ADMIN_IDS": "1, 2 3,invalid,4",
        "BLOCK_BATCH_SIZE": "12345",
        "PROCESS_BLOCKS_REQUESTS_PER_SECOND": "3.5",
        "BLOCK_FROM": "789",
        "WEB3_SOCKET_PROVIDER": "wss://example.invalid",
        "CSM_ADDRESS": "0x0000000000000000000000000000000000000001",
    },
    clear=True,
)
def test_config_parsing_and_templates(monkeypatch, stub_discover_contract_addresses):
    from csm_bot.config import get_config

    clear_config()
    cfg = get_config()

    assert cfg.admin_ids == {1, 2, 3, 4}
    assert cfg.block_batch_size == 12345
    assert cfg.process_blocks_requests_per_second == 3.5
    assert cfg.block_from == 789
    assert cfg.etherscan_block_url_template == "https://etherscan.io/block/{}"
    assert cfg.etherscan_tx_url_template == "https://etherscan.io/tx/{}"
    assert cfg.beaconchain_url_template == "https://beaconcha.in/validator/{}"
    clear_config()


@pytest.mark.asyncio
@patch.dict(
    os.environ,
    {
        "WEB3_SOCKET_PROVIDER": "wss://example.invalid",
        "CSM_ADDRESS": "0x0000000000000000000000000000000000000001",
        "PROCESS_BLOCKS_REQUESTS_PER_SECOND": "2",
    },
    clear=True,
)
async def test_process_blocks_rate_limit(monkeypatch, stub_discover_contract_addresses):
    from csm_bot.config import get_config_async
    from csm_bot.rpc import Subscription

    class DummyW3:
        provider = None

    clear_config()
    await get_config_async()
    from csm_bot.texts import EVENT_DESCRIPTIONS

    subscription = Subscription(DummyW3(), set(EVENT_DESCRIPTIONS.keys()))
    try:
        start = asyncio.get_running_loop().time()
        await subscription._throttle_process_blocks_request()
        await subscription._throttle_process_blocks_request()
        elapsed = asyncio.get_running_loop().time() - start
        assert elapsed >= 0.45
    finally:
        clear_config()


@pytest.mark.asyncio
async def test_get_block_number_uses_persistent_provider():
    from src.csm_bot.rpc import Subscription

    main_w3 = SimpleNamespace(
        provider=SimpleNamespace(
            is_connected=AsyncMock(return_value=True),
            connect=AsyncMock(),
        ),
        eth=SimpleNamespace(get_block_number=AsyncMock(return_value=111)),
    )
    backfill_w3 = SimpleNamespace(
        provider=SimpleNamespace(
            is_connected=AsyncMock(return_value=True),
            connect=AsyncMock(),
        ),
        eth=SimpleNamespace(get_block_number=AsyncMock(return_value=222)),
    )

    subscription = Subscription.__new__(Subscription)
    subscription._w3 = main_w3
    subscription._backfill_w3 = backfill_w3

    latest = await subscription.get_block_number()

    assert latest == 111
    main_w3.eth.get_block_number.assert_awaited_once()
    backfill_w3.eth.get_block_number.assert_not_awaited()
