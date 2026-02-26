import asyncio
import pytest
from types import SimpleNamespace

from csm_bot.config import get_config_async, set_config
from src.csm_bot.texts import target_validators_count_changed
from hexbytes import HexBytes


class _DummyConnectProvider:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


class _FakeFetcher:
    def __init__(self, result=None, exc: Exception | None = None):
        self.result = result
        self.exc = exc
        self.calls: list[str] = []

    async def __call__(self, log_cid: str):
        self.calls.append(log_cid)
        if self.exc is not None:
            raise self.exc
        return self.result


def test_limit_set_mode_1():
    result = target_validators_count_changed(0, 0, 1, 10)
    expected = (
        "🚨 *Target validators count changed*\n\n"
        r"The limit has been set to 10\."
        "\n"
        r"10 keys will be requested to exit first\."
    )
    assert result == expected


def test_limit_set_mode_2():
    result = target_validators_count_changed(0, 0, 2, 10)
    expected = (
        "🚨 *Target validators count changed*\n\n"
        r"The limit has been set to 10\."
        "\n"
        r"10 keys will be requested to exit immediately\."
    )
    assert result == expected


def test_limit_set_mode_2_from_1():
    result = target_validators_count_changed(1, 5, 2, 10)
    expected = (
        "🚨 *Target validators count changed*\n\n"
        r"The limit has been set to 10\."
        "\n"
        r"10 keys will be requested to exit immediately\."
    )
    assert result == expected


def test_limit_set_mode_1_from_2():
    result = target_validators_count_changed(2, 5, 1, 10)
    expected = (
        "🚨 *Target validators count changed*\n\n"
        r"The limit has been set to 10\."
        "\n"
        r"10 keys will be requested to exit first\."
    )
    assert result == expected


def test_limit_decreased_mode_1():
    result = target_validators_count_changed(1, 10, 1, 3)
    expected = (
        "🚨 *Target validators count changed*\n\n"
        r"The limit has been decreased from 10 to 3\."
        "\n"
        r"7 more key\(s\) will be requested to exit first\."
    )
    assert result == expected


def test_limit_decreased_mode_2():
    result = target_validators_count_changed(2, 10, 2, 3)
    expected = (
        "🚨 *Target validators count changed*\n\n"
        r"The limit has been decreased from 10 to 3\."
        "\n"
        r"7 more key\(s\) will be requested to exit immediately\."
    )
    assert result == expected


def test_limit_to_zero_exit_first():
    result = target_validators_count_changed(1, 10, 1, 0)
    expected = (
        "🚨 *Target validators count changed*\n\n"
        r"The limit has been set to zero\."
        "\n"
        r"All keys will be requested to exit first\."
    )
    assert result == expected


def test_limit_to_zero_exit_immediately():
    result = target_validators_count_changed(2, 10, 2, 0)
    expected = (
        "🚨 *Target validators count changed*\n\n"
        r"The limit has been set to zero\."
        "\n"
        r"All keys will be requested to exit immediately\."
    )
    assert result == expected


def test_limit_to_zero_exit_first_no_previous_limit():
    result = target_validators_count_changed(0, 0, 1, 0)
    expected = (
        "🚨 *Target validators count changed*\n\n"
        r"The limit has been set to zero\."
        "\n"
        r"All keys will be requested to exit first\."
    )
    assert result == expected


def test_limit_to_zero_exit_immediately_no_previous_limit():
    result = target_validators_count_changed(0, 0, 2, 0)
    expected = (
        "🚨 *Target validators count changed*\n\n"
        r"The limit has been set to zero\."
        "\n"
        r"All keys will be requested to exit immediately\."
    )
    assert result == expected


def test_limit_unset_mode_zero():
    result = target_validators_count_changed(1, 10, 0, 0)
    expected = (
        "🚨 *Target validators count changed*\n\n"
        r"The limit has been set to zero\. No keys will be requested to exit\."
    )
    assert result == expected


@pytest.fixture(autouse=True)
def _clear_alru_cache():
    """Reset the alru_cache on _fetch_distribution_log between tests.

    async_lru ≥ 2.2 enforces single-loop usage per cache instance. Since
    pytest-asyncio creates a new event loop per test, we must also reset the
    internal loop binding alongside the cached entries.
    """
    from src.csm_bot.events import EventMessages

    def _reset():
        instance_method = EventMessages._fetch_distribution_log
        instance_method.cache_clear()
        # Reach through to the underlying _LRUCacheWrapper and clear the
        # event-loop binding so the next test can attach its own loop.
        inner = instance_method._LRUCacheWrapperInstanceMethod__wrapper
        inner._LRUCacheWrapper__first_loop = None

    _reset()
    yield
    _reset()


@pytest.mark.asyncio
async def test_fetch_distribution_log_success():
    from src.csm_bot.events import EventMessages

    event_messages = EventMessages.__new__(EventMessages)
    fetcher = _FakeFetcher(result={"operators": {"123": {}}})
    event_messages._distribution_log_fetcher = fetcher

    data = await event_messages._fetch_distribution_log("QmCID")

    assert data == {"operators": {"123": {}}}
    assert fetcher.calls == ["QmCID"]


@pytest.mark.asyncio
async def test_fetch_distribution_log_caches():
    from src.csm_bot.events import EventMessages

    event_messages = EventMessages.__new__(EventMessages)
    fetcher = _FakeFetcher(result={"operators": {}})
    event_messages._distribution_log_fetcher = fetcher

    await event_messages._fetch_distribution_log("QmCID")
    await event_messages._fetch_distribution_log("QmCID")

    assert fetcher.calls == ["QmCID"]


@pytest.mark.asyncio
async def test_fetch_distribution_log_handles_error():
    from src.csm_bot.events import EventMessages

    event_messages = EventMessages.__new__(EventMessages)
    event_messages._distribution_log_fetcher = _FakeFetcher(exc=RuntimeError("boom"))

    with pytest.raises(RuntimeError):
        await event_messages._fetch_distribution_log("QmCID")


@pytest.mark.asyncio
async def test_fetch_distribution_log_requires_cid():
    from src.csm_bot.events import EventMessages

    event_messages = EventMessages.__new__(EventMessages)

    with pytest.raises(ValueError):
        await event_messages._fetch_distribution_log(None)


@pytest.mark.asyncio
async def test_fetch_distribution_log_handles_timeout():
    from src.csm_bot.events import EventMessages

    event_messages = EventMessages.__new__(EventMessages)
    event_messages._distribution_log_fetcher = _FakeFetcher(exc=asyncio.TimeoutError("timeout"))

    with pytest.raises(asyncio.TimeoutError):
        await event_messages._fetch_distribution_log("QmCID")


@pytest.mark.asyncio
async def test_distribution_log_updated_produces_strike_notifications():
    from src.csm_bot.events import EventMessages, NotificationPlan
    from src.csm_bot.models import Event
    import src.csm_bot.texts as texts

    set_config(
        SimpleNamespace(
            etherscan_tx_url_template="https://etherscan.io/tx/{}",
            module_ui_url="https://csm.lido.fi",
        )
    )
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
                "777": {"validators": {"900": {"strikes": 0}}},
            }
        }
    ]

    fetch_calls: list[str | None] = []

    async def fake_fetch(log_cid):
        fetch_calls.append(log_cid)
        return payload

    event_messages._distribution_log_fetcher = fake_fetch

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
async def test_distribution_log_updated_handles_empty_payload():
    from src.csm_bot.events import EventMessages, NotificationPlan
    from src.csm_bot.models import Event
    import src.csm_bot.texts as texts

    set_config(
        SimpleNamespace(
            etherscan_tx_url_template="https://etherscan.io/tx/{}",
            module_ui_url="https://csm.lido.fi",
        )
    )
    event_messages = EventMessages.__new__(EventMessages)
    event_messages.cfg = await get_config_async()
    event_messages._distribution_log_fetcher = _FakeFetcher(result={})

    event = Event(
        event="DistributionLogUpdated",
        args={"logCid": "cid123"},
        block=123,
        tx=HexBytes("0xdeadbeef"),
        address="0x0000000000000000000000000000000000000000",
    )

    plan = await EventMessages.distribution_log_updated(event_messages, event)

    assert isinstance(plan, NotificationPlan)
    assert plan.per_node_operator == {}
    assert plan.broadcast_node_operator_ids is None
    expected_base = texts.distribution_data_updated()
    expected_foot = event_messages.footer(event)
    assert plan.broadcast == f"{expected_base}{expected_foot}"


@pytest.mark.asyncio
async def test_get_notification_plan_skips_disallowed_event():
    from src.csm_bot.events import EventMessages
    from src.csm_bot.models import Event

    class DummyAdapter:
        def allowed_events(self):
            return set()

        async def event_enricher(self, event, messages):
            return None

    event_messages = EventMessages.__new__(EventMessages)
    event_messages.module_adapter = DummyAdapter()

    event = Event(
        event="DepositedSigningKeysCountChanged",
        args={"nodeOperatorId": 321, "depositedKeysCount": 1},
        block=1,
        tx=HexBytes("0xdeadbeef"),
        address="0x0000000000000000000000000000000000000000",
    )

    plan = await EventMessages.get_notification_plan(event_messages, event)

    assert plan is None


@pytest.mark.asyncio
async def test_get_notification_plan_sets_node_operator_target():
    from src.csm_bot.events import EventMessages, NotificationPlan
    from src.csm_bot.models import Event

    class DummyAdapter:
        def allowed_events(self):
            return {"DepositedSigningKeysCountChanged"}

        async def event_enricher(self, event, messages):
            return None

    event_messages = EventMessages.__new__(EventMessages)
    event_messages.connectProvider = _DummyConnectProvider()
    event_messages.cfg = SimpleNamespace(etherscan_tx_url_template="https://etherscan.io/tx/{}")
    event_messages.footer = EventMessages.footer.__get__(event_messages)
    event_messages.module_adapter = DummyAdapter()

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


@pytest.mark.asyncio
async def test_get_notification_plan_uses_adapter_override():
    from src.csm_bot.events import EventMessages, NotificationPlan
    from src.csm_bot.models import Event

    class DummyAdapter:
        def allowed_events(self):
            return {"BondCurveSet"}

        async def event_enricher(self, event, messages):
            if event.event == "BondCurveSet":
                return "override"
            return None

    event_messages = EventMessages.__new__(EventMessages)
    event_messages.connectProvider = _DummyConnectProvider()
    event_messages.module_adapter = DummyAdapter()

    event = Event(
        event="BondCurveSet",
        args={"curveId": 1},
        block=1,
        tx=HexBytes("0xdeadbeef"),
        address="0x0000000000000000000000000000000000000000",
    )

    plan = await EventMessages.get_notification_plan(event_messages, event)

    assert isinstance(plan, NotificationPlan)
    assert plan.broadcast == "override"
