from csm_bot.app.storage import (
    BlockState,
    BotStorage,
    ChatIdSet,
    ChatStorage,
    NodeOperatorChats,
    NodeOperatorSubscriptions,
    ensure_int_set,
    normalise_node_operator_ids,
    normalise_node_operator_map,
)


# _ensure_int_set

def test_ensure_int_set_none_returns_empty():
    assert ensure_int_set(None) == set()


def test_ensure_int_set_preserves_int_set():
    values = {1, 2, 3}
    assert ensure_int_set(values) is values


def test_ensure_int_set_casts_iterable_values():
    result = ensure_int_set(["1", 2, 3.0])
    assert result == {1, 2, 3}


def test_ensure_int_set_logs_on_unhashable_iterable(caplog):
    caplog.set_level("WARNING")
    # object without iteration support triggers the defensive branch
    result = ensure_int_set(5)  # type: ignore[arg-type]
    assert result == set()
    assert "Ignoring malformed chat id container" in caplog.text


def test_ensure_int_set_skips_non_convertible_items(caplog):
    caplog.set_level("WARNING")
    result = ensure_int_set(["1", "bad"])  # type: ignore[list-item]
    assert result == {1}
    assert "Skipping non-integer chat id" in caplog.text


# _normalise_node_operator_map

def test_normalise_node_operator_map_basic_conversion():
    mapping = {"no": ["1", 2], 2: {3}}
    result = normalise_node_operator_map(mapping)
    assert result == {"no": {1, 2}, "2": {3}}


def test_normalise_node_operator_map_handles_invalid_mapping(caplog):
    caplog.set_level("WARNING")
    result = normalise_node_operator_map([1, 2])  # type: ignore[arg-type]
    assert result == {}
    assert "Ignoring malformed node operator mapping" in caplog.text


# _normalise_node_operator_ids

def test_normalise_node_operator_ids_filters_none():
    result = normalise_node_operator_ids(["1", 2, None])
    assert result == {"1", "2"}


def test_normalise_node_operator_ids_logs_on_invalid_iterable(caplog):
    caplog.set_level("WARNING")
    result = normalise_node_operator_ids(1)  # type: ignore[arg-type]
    assert result == set()
    assert "Ignoring malformed node operator list" in caplog.text


# BlockState

def test_block_state_defaults_and_updates():
    bot_data: dict[str, object] = {}
    state = BlockState(bot_data)

    assert state.value == 0

    state.update(42)
    assert state.value == 42
    assert bot_data["block"] == 42

    bot_data_with_existing = {"block": "7"}
    state_existing = BlockState(bot_data_with_existing)
    assert state_existing.value == 7


# ChatIdSet

def test_chat_id_set_normalisation_and_mutations():
    bot_data: dict[str, object] = {"user_ids": {"1", 2, 3.0}}
    chat_ids = ChatIdSet(bot_data, "user_ids")

    assert chat_ids.all() == {1, 2, 3}

    chat_ids.add("4")
    assert chat_ids.contains(4)

    chat_ids.remove(2)
    assert not chat_ids.contains(2)

    snapshot = chat_ids.all()
    snapshot.add(99)
    assert 99 not in chat_ids.all()


# NodeOperatorChats

def test_node_operator_chats_initial_normalisation():
    initial_mapping = {"1": ["10", 11], "empty": []}
    bot_data = {"no_ids_to_chats": initial_mapping}

    chats = NodeOperatorChats(bot_data)

    assert chats.ids() == {"1", "empty"}
    assert chats.chats_for("1") == {10, 11}
    assert chats.chats_for("empty") == set()


def test_node_operator_chats_subscribe_unsubscribe_preserve_keys():
    bot_data: dict[str, object] = {}
    chats = NodeOperatorChats(bot_data)

    chats.subscribe("alpha", 100)
    chats.subscribe("alpha", "200")
    assert chats.chats_for("alpha") == {100, 200}

    chats.unsubscribe("alpha", 100)
    assert chats.chats_for("alpha") == {200}

    chats.unsubscribe("alpha", 200)
    assert chats.ids() == {"alpha"}
    assert chats.chats_for("alpha") == set()


def test_node_operator_chats_resolve_targets_filters_non_actual():
    bot_data: dict[str, object] = {}
    chats = NodeOperatorChats(bot_data)
    chats.subscribe("alpha", 100)
    chats.subscribe("alpha", 300)
    chats.subscribe("beta", 200)

    result = chats.resolve_targets(["alpha", "beta"], actual_chat_ids=[100, 200])
    assert result == {100, 200}


def test_node_operator_chats_subscription_counts_breakdown():
    bot_data: dict[str, object] = {}
    chats = NodeOperatorChats(bot_data)
    chats.subscribe("alpha", 100)
    chats.subscribe("alpha", 300)
    chats.subscribe("beta", 200)
    chats.subscribe("beta", 400)

    counts = chats.subscription_counts(
        actual_chat_ids=[100, 200, 300],
        user_ids=[100],
        group_ids=[200],
        channel_ids=[300],
    )

    assert counts == {
        "alpha": {"total": 2, "users": 1, "groups": 0, "channels": 1},
        "beta": {"total": 1, "users": 0, "groups": 1, "channels": 0},
    }


# BotStorage

def test_bot_storage_wrappers_use_underlying_helpers():
    bot_data: dict[str, object] = {}
    storage = BotStorage(bot_data)

    storage.users.add(100)
    storage.groups.add(200)
    storage.channels.add(300)

    storage.node_operator_chats.subscribe("alpha", 100)
    storage.node_operator_chats.subscribe("alpha", 400)
    storage.node_operator_chats.subscribe("beta", 200)

    assert storage.actual_chat_ids() == {100, 200, 300}
    assert storage.resolve_target_chats(["alpha"]) == {100}

    assert storage.subscription_counts() == {
        "alpha": {"total": 1, "users": 1, "groups": 0, "channels": 0},
        "beta": {"total": 1, "users": 0, "groups": 1, "channels": 0},
    }


# NodeOperatorSubscriptions

def test_node_operator_subscriptions_follow_and_unfollow():
    chat_data: dict[str, object] = {"node_operators": ["1", 2, None]}
    subscriptions = NodeOperatorSubscriptions(chat_data)

    assert subscriptions.ids() == {"1", "2"}

    subscriptions.follow(3)
    assert subscriptions.ids() == {"1", "2", "3"}

    assert subscriptions.unfollow("2") is True
    assert subscriptions.unfollow("missing") is False
    assert subscriptions.ids() == {"1", "3"}


# ChatStorage

def test_chat_storage_exposes_node_operator_helper():
    chat_data: dict[str, object] = {}
    storage = ChatStorage(chat_data)

    helper = storage.node_operators
    helper.follow("alpha")

    assert storage.node_operators is helper
    assert chat_data["node_operators"] == {"alpha"}
