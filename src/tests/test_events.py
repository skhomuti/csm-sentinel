from src.csm_bot.texts import target_validators_count_changed

def test_limit_set_mode_1():
    result = target_validators_count_changed(0, 0, 1, 10)
    expected = ("🚨 *Target validators count changed*\n\n"
                "The limit has been set to 10\.\n"
                "10 keys will be requested to exit first\.")
    assert result == expected

def test_limit_set_mode_2():
    result = target_validators_count_changed(0, 0, 2, 10)
    expected = ("🚨 *Target validators count changed*\n\n"
                "The limit has been set to 10\.\n"
                "10 keys will be requested to exit immediately\.")
    assert result == expected

def test_limit_set_mode_2_from_1():
    result = target_validators_count_changed(1, 5, 2, 10)
    expected = ("🚨 *Target validators count changed*\n\n"
                "The limit has been set to 10\.\n"
                "10 keys will be requested to exit immediately\.")
    assert result == expected

def test_limit_set_mode_1_from_2():
    result = target_validators_count_changed(2, 5, 1, 10)
    expected = ("🚨 *Target validators count changed*\n\n"
                "The limit has been set to 10\.\n"
                "10 keys will be requested to exit first\.")
    assert result == expected


def test_limit_decreased_mode_1():
    result = target_validators_count_changed(1, 10, 1, 3)
    expected = ("🚨 *Target validators count changed*\n\n"
                "The limit has been decreased from 10 to 3\.\n"
                "7 more key\(s\) will be requested to exit first\.")
    assert result == expected

def test_limit_decreased_mode_2():
    result = target_validators_count_changed(2, 10, 2, 3)
    expected = ("🚨 *Target validators count changed*\n\n"
                "The limit has been decreased from 10 to 3\.\n"
                "7 more key\(s\) will be requested to exit immediately\.")
    assert result == expected

def test_limit_unset_1():
    result = target_validators_count_changed(1, 10, 0, 0)
    expected = ("🚨 *Target validators count changed*\n\n"
                "The limit has been set to zero\. No keys will be requested to exit\.")
    assert result == expected

def test_limit_unset_2():
    result = target_validators_count_changed(2, 10, 0, 0)
    expected = ("🚨 *Target validators count changed*\n\n"
                "The limit has been set to zero\. No keys will be requested to exit\.")
    assert result == expected
