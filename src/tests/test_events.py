import aiohttp
import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

from csm_bot.config import get_config_async, set_config
from src.csm_bot.texts import target_validators_count_changed
from hexbytes import HexBytes


class _DummyConnectProvider:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

def test_limit_set_mode_1():
    result = target_validators_count_changed(0, 0, 1, 10)
    expected = ("🚨 *Target validators count changed*\n\n"
                r"The limit has been set to 10\."
                "\n"
                r"10 keys will be requested to exit first\.")
    assert result == expected

def test_limit_set_mode_2():
    result = target_validators_count_changed(0, 0, 2, 10)
    expected = ("🚨 *Target validators count changed*\n\n"
                r"The limit has been set to 10\."
                "\n"
                r"10 keys will be requested to exit immediately\.")
    assert result == expected

def test_limit_set_mode_2_from_1():
    result = target_validators_count_changed(1, 5, 2, 10)
    expected = ("🚨 *Target validators count changed*\n\n"
                r"The limit has been set to 10\."
                "\n"
                r"10 keys will be requested to exit immediately\.")
    assert result == expected

def test_limit_set_mode_1_from_2():
    result = target_validators_count_changed(2, 5, 1, 10)
    expected = ("🚨 *Target validators count changed*\n\n"
                r"The limit has been set to 10\."
                "\n"
                r"10 keys will be requested to exit first\.")
    assert result == expected


def test_limit_decreased_mode_1():
    result = target_validators_count_changed(1, 10, 1, 3)
    expected = ("🚨 *Target validators count changed*\n\n"
                r"The limit has been decreased from 10 to 3\."
                "\n"
                r"7 more key\(s\) will be requested to exit first\.")
    assert result == expected

def test_limit_decreased_mode_2():
    result = target_validators_count_changed(2, 10, 2, 3)
    expected = ("🚨 *Target validators count changed*\n\n"
                r"The limit has been decreased from 10 to 3\."
                "\n"
                r"7 more key\(s\) will be requested to exit immediately\.")
    assert result == expected

def test_limit_to_zero_exit_first():
    result = target_validators_count_changed(1, 10, 1, 0)
    expected = ("🚨 *Target validators count changed*\n\n"
                r"The limit has been set to zero\."
                "\n"
                r"All keys will be requested to exit first\.")
    assert result == expected

def test_limit_to_zero_exit_immediately():
    result = target_validators_count_changed(2, 10, 2, 0)
    expected = ("🚨 *Target validators count changed*\n\n"
                r"The limit has been set to zero\."
                "\n"
                r"All keys will be requested to exit immediately\.")
    assert result == expected

def test_limit_to_zero_exit_first_no_previous_limit():
    result = target_validators_count_changed(0, 0, 1, 0)
    expected = ("🚨 *Target validators count changed*\n\n"
                r"The limit has been set to zero\."
                "\n"
                r"All keys will be requested to exit first\.")
    assert result == expected

def test_limit_to_zero_exit_immediately_no_previous_limit():
    result = target_validators_count_changed(0, 0, 2, 0)
    expected = ("🚨 *Target validators count changed*\n\n"
                r"The limit has been set to zero\."
                "\n"
                r"All keys will be requested to exit immediately\.")
    assert result == expected

def test_limit_unset_mode_zero():
    result = target_validators_count_changed(1, 10, 0, 0)
    expected = ("🚨 *Target validators count changed*\n\n"
                r"The limit has been set to zero\. No keys will be requested to exit\.")
    assert result == expected

@pytest.mark.asyncio
@patch.dict('os.environ', {
    'ETHERSCAN_URL': 'https://etherscan.io',
    'BEACONCHAIN_URL': 'https://beaconcha.in',
    'CSM_ADDRESS': '0x1234567890123456789012345678901234567890',
    'ACCOUNTING_ADDRESS': '0x1234567890123456789012345678901234567890'
})
@patch('aiohttp.ClientSession.get')
async def test_fetch_distribution_log_success(mock_get):
    from src.csm_bot.events import EventMessages

    response = AsyncMock()
    response.status = 200
    response.json = AsyncMock(return_value={"operators": {"123": {}}})

    context_manager = AsyncMock()
    context_manager.__aenter__.return_value = response
    context_manager.__aexit__.return_value = None
    mock_get.return_value = context_manager

    event_messages = EventMessages.__new__(EventMessages)

    data = await event_messages._fetch_distribution_log("QmCID")

    assert data == {"operators": {"123": {}}}
    mock_get.assert_called_once_with("https://ipfs.io/ipfs/QmCID")


@pytest.mark.asyncio
@patch.dict('os.environ', {
    'ETHERSCAN_URL': 'https://etherscan.io',
    'BEACONCHAIN_URL': 'https://beaconcha.in',
    'CSM_ADDRESS': '0x1234567890123456789012345678901234567890',
    'ACCOUNTING_ADDRESS': '0x1234567890123456789012345678901234567890'
})
@patch('aiohttp.ClientSession.get')
async def test_fetch_distribution_log_caches(mock_get):
    from src.csm_bot.events import EventMessages

    response = AsyncMock()
    response.status = 200
    response.json = AsyncMock(return_value={"operators": {}})

    context_manager = AsyncMock()
    context_manager.__aenter__.return_value = response
    context_manager.__aexit__.return_value = None
    mock_get.return_value = context_manager

    event_messages = EventMessages.__new__(EventMessages)

    await event_messages._fetch_distribution_log("QmCID")
    await event_messages._fetch_distribution_log("QmCID")

    mock_get.assert_called_once()


@pytest.mark.asyncio
@patch.dict('os.environ', {
    'ETHERSCAN_URL': 'https://etherscan.io',
    'BEACONCHAIN_URL': 'https://beaconcha.in',
    'CSM_ADDRESS': '0x1234567890123456789012345678901234567890',
    'ACCOUNTING_ADDRESS': '0x1234567890123456789012345678901234567890'
})
@patch('aiohttp.ClientSession.get')
async def test_fetch_distribution_log_handles_http_error(mock_get):
    from src.csm_bot.events import EventMessages

    response = AsyncMock()
    response.status = 404

    context_manager = AsyncMock()
    context_manager.__aenter__.return_value = response
    context_manager.__aexit__.return_value = None
    mock_get.return_value = context_manager

    event_messages = EventMessages.__new__(EventMessages)

    with pytest.raises(aiohttp.ClientError):
        await event_messages._fetch_distribution_log("QmCID")


@pytest.mark.asyncio
@patch.dict('os.environ', {
    'ETHERSCAN_URL': 'https://etherscan.io',
    'BEACONCHAIN_URL': 'https://beaconcha.in',
    'CSM_ADDRESS': '0x1234567890123456789012345678901234567890',
    'ACCOUNTING_ADDRESS': '0x1234567890123456789012345678901234567890'
})
async def test_fetch_distribution_log_requires_cid():
    from src.csm_bot.events import EventMessages

    event_messages = EventMessages.__new__(EventMessages)

    with pytest.raises(ValueError):
        await event_messages._fetch_distribution_log(None)


@pytest.mark.asyncio
@patch.dict('os.environ', {
    'ETHERSCAN_URL': 'https://etherscan.io',
    'BEACONCHAIN_URL': 'https://beaconcha.in',
    'CSM_ADDRESS': '0x1234567890123456789012345678901234567890',
    'ACCOUNTING_ADDRESS': '0x1234567890123456789012345678901234567890'
})
@patch('aiohttp.ClientSession.get')
async def test_fetch_distribution_log_handles_timeout(mock_get):
    from src.csm_bot.events import EventMessages

    context_manager = AsyncMock()
    context_manager.__aenter__.side_effect = asyncio.TimeoutError("timeout")
    context_manager.__aexit__.return_value = None
    mock_get.return_value = context_manager

    event_messages = EventMessages.__new__(EventMessages)

    with pytest.raises(asyncio.TimeoutError):
        await event_messages._fetch_distribution_log("QmCID")


@pytest.mark.asyncio
async def test_distribution_log_updated_produces_strike_notifications():
    from src.csm_bot.events import EventMessages, NotificationPlan
    from src.csm_bot.models import Event
    import src.csm_bot.texts as texts

    set_config(SimpleNamespace(
        etherscan_tx_url_template="https://etherscan.io/tx/{}",
        csm_ui_url="https://csm.lido.fi",
    ))
    event_messages = EventMessages.__new__(EventMessages)
    event_messages.cfg = await get_config_async()

    payload = [
        {
            "operators": {
                "42": {
                    "validators": {
                        "123": {"strikes": 0},
                        "124": {"strikes": 2},
                    }
                },
                "777": {
                    "validators": {
                        "900": {"strikes": 0}
                    }
                },
            }
        }
    ]

    fetch_calls: list[str | None] = []

    async def fake_fetch(log_cid):
        fetch_calls.append(log_cid)
        return payload

    event_messages._fetch_distribution_log = fake_fetch

    event = Event(
        event="DistributionLogUpdated",
        args={"logCid": "cid123"},
        block=123,
        tx=HexBytes("0xdeadbeef"),
        address="0x0000000000000000000000000000000000000000",
    )

    plan = await EventMessages.distribution_log_updated(event_messages, event)

    assert isinstance(plan, NotificationPlan)
    assert plan.broadcast_node_operator_ids == {"42", "777"}

    expected_base = texts.distribution_data_updated()
    expected_foot = event_messages.footer(event)
    assert plan.broadcast == f"{expected_base}{expected_foot}"

    assert "42" in plan.per_node_operator
    operator_message = plan.per_node_operator["42"]
    assert expected_base in operator_message
    assert "⚠️" in operator_message
    assert "Validators with strikes: `1`" in operator_message
    assert operator_message.endswith(expected_foot)

    assert "777" not in plan.per_node_operator
    assert fetch_calls == ["cid123"]


@pytest.mark.asyncio
async def test_get_notification_plan_sets_node_operator_target():
    from src.csm_bot.events import EventMessages, NotificationPlan
    from src.csm_bot.models import Event

    event_messages = EventMessages.__new__(EventMessages)
    event_messages.connectProvider = _DummyConnectProvider()
    event_messages.cfg = SimpleNamespace(etherscan_tx_url_template="https://etherscan.io/tx/{}")
    event_messages.footer = EventMessages.footer.__get__(event_messages)

    event = Event(
        event="DepositedSigningKeysCountChanged",
        args={"nodeOperatorId": 321, "depositedKeysCount": 1},
        block=1,
        tx=HexBytes("0xdeadbeef"),
        address="0x0000000000000000000000000000000000000000",
    )

    plan = await EventMessages.get_notification_plan(event_messages, event)

    assert isinstance(plan, NotificationPlan)
    assert plan.broadcast_node_operator_ids == {"321"}
    assert plan.broadcast is not None
