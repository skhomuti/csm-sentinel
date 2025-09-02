import os
from unittest.mock import patch

from hexbytes import HexBytes


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
    from src.csm_bot.main import get_active_subscription_counts

    bot_data = {
        "user_ids": {1},
        "group_ids": {2},
        "channel_ids": {3},
        "no_ids_to_chats": {
            "10": {1, 2},  # one user, one group
            "20": {2, 4},  # one group, one inactive
        },
    }

    counts = get_active_subscription_counts(bot_data)
    assert counts["10"]["total"] == 2
    assert counts["10"]["users"] == 1
    assert counts["10"]["groups"] == 1
    assert counts["10"]["channels"] == 0

    assert counts["20"]["total"] == 1
    assert counts["20"]["users"] == 0
    assert counts["20"]["groups"] == 1
    assert counts["20"]["channels"] == 0


def test_main_resolve_target_chats():
    from src.csm_bot.main import _resolve_target_chats_for_node_operators

    bot_data = {
        "user_ids": {1},
        "group_ids": {2},
        "channel_ids": {3},
        "no_ids_to_chats": {
            "10": {1, 2},
            "20": {2, 4},
        },
    }
    targets = _resolve_target_chats_for_node_operators(bot_data, {"10", "20"})
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
        "BLOCK_FROM": "789",
    },
)
def test_config_parsing_and_templates():
    from src.csm_bot.config import get_config

    # Clear cache to re-read envs
    get_config.cache_clear()
    cfg = get_config()

    assert cfg.admin_ids == {1, 2, 3, 4}
    assert cfg.block_batch_size == 12345
    assert cfg.block_from == 789
    assert cfg.etherscan_block_url_template == "https://etherscan.io/block/{}"
    assert cfg.etherscan_tx_url_template == "https://etherscan.io/tx/{}"
    assert cfg.beaconchain_url_template == "https://beaconcha.in/validator/{}"


@patch.dict(os.environ, {}, clear=True)
def test_config_templates_none_when_missing_envs():
    from src.csm_bot.config import get_config

    get_config.cache_clear()
    cfg = get_config()

    assert cfg.etherscan_block_url_template is None
    assert cfg.etherscan_tx_url_template is None
    assert cfg.beaconchain_url_template is None

