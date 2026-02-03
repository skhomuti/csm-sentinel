from csm_bot.texts import build_event_list_text


def test_build_event_list_text_for_common_group():
    allowed_events = {"Initialized"}
    text = build_event_list_text(allowed_events)
    expected = (
        "Here is the list of events you will receive notifications for:\n"
        "A 🚨 means urgent action is required from you\n"
        "\n"
        "*Common CSM Events for all the Node Operators:*\n"
        "\\- 🎉 CSM v2 launched on mainnet\n"
        "\n"
        "\n"
    )
    assert text == expected


def test_build_event_list_text_for_key_management_group():
    allowed_events = {"DepositedSigningKeysCountChanged"}
    text = build_event_list_text(allowed_events)
    expected = (
        "Here is the list of events you will receive notifications for:\n"
        "A 🚨 means urgent action is required from you\n"
        "\n"
        "*Key Management Events:*\n"
        "Changes related to keys and their status\\.\n"
        "\\- 🤩 Node Operator's keys received deposits\n"
        "\n"
        "\n"
    )
    assert text == expected
