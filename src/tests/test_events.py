import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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


@pytest.mark.asyncio
@patch.dict('os.environ', {
    'ETHERSCAN_URL': 'https://etherscan.io',
    'BEACONCHAIN_URL': 'https://beaconcha.in',
    'CSM_ADDRESS': '0x1234567890123456789012345678901234567890',
    'ACCOUNTING_ADDRESS': '0x1234567890123456789012345678901234567890'
})
async def test_has_active_keys_with_deposited_keys():
    """Test that has_active_keys returns True when node operator has deposited but not withdrawn keys."""
    from src.csm_bot.events import EventMessages
    
    # Mock Web3 and contract
    mock_w3 = AsyncMock()
    
    # Mock node operator with 5 deposited keys and 2 withdrawn keys
    mock_node_operator = MagicMock()
    mock_node_operator.totalDepositedKeys = 5
    mock_node_operator.totalWithdrawnKeys = 2
    
    # Mock the contract call chain
    mock_csm_contract = MagicMock()
    mock_functions = MagicMock()
    mock_get_node_operator = MagicMock()
    
    mock_get_node_operator.call = AsyncMock(return_value=mock_node_operator)
    mock_functions.getNodeOperator.return_value = mock_get_node_operator
    mock_csm_contract.functions = mock_functions
    
    event_messages = EventMessages(mock_w3)
    event_messages.csm = mock_csm_contract
    
    result = await event_messages.has_active_keys(1)
    assert result is True


@pytest.mark.asyncio
@patch.dict('os.environ', {
    'ETHERSCAN_URL': 'https://etherscan.io',
    'BEACONCHAIN_URL': 'https://beaconcha.in',
    'CSM_ADDRESS': '0x1234567890123456789012345678901234567890',
    'ACCOUNTING_ADDRESS': '0x1234567890123456789012345678901234567890'
})
async def test_has_active_keys_with_no_active_keys():
    """Test that has_active_keys returns False when node operator has no active keys."""
    from src.csm_bot.events import EventMessages
    
    # Mock Web3 and contract
    mock_w3 = AsyncMock()
    
    # Mock node operator with all keys withdrawn
    mock_node_operator = MagicMock()
    mock_node_operator.totalDepositedKeys = 5
    mock_node_operator.totalWithdrawnKeys = 5
    
    # Mock the contract call chain
    mock_csm_contract = MagicMock()
    mock_functions = MagicMock()
    mock_get_node_operator = MagicMock()
    
    mock_get_node_operator.call = AsyncMock(return_value=mock_node_operator)
    mock_functions.getNodeOperator.return_value = mock_get_node_operator
    mock_csm_contract.functions = mock_functions
    
    event_messages = EventMessages(mock_w3)
    event_messages.csm = mock_csm_contract
    
    result = await event_messages.has_active_keys(1)
    assert result is False


@pytest.mark.asyncio
@patch.dict('os.environ', {
    'ETHERSCAN_URL': 'https://etherscan.io',
    'BEACONCHAIN_URL': 'https://beaconcha.in',
    'CSM_ADDRESS': '0x1234567890123456789012345678901234567890',
    'ACCOUNTING_ADDRESS': '0x1234567890123456789012345678901234567890'
})
async def test_has_active_keys_with_no_deposited_keys():
    """Test that has_active_keys returns False when node operator has no deposited keys."""
    from src.csm_bot.events import EventMessages
    
    # Mock Web3 and contract
    mock_w3 = AsyncMock()
    
    # Mock node operator with no deposited keys
    mock_node_operator = MagicMock()
    mock_node_operator.totalDepositedKeys = 0
    mock_node_operator.totalWithdrawnKeys = 0
    
    # Mock the contract call chain
    mock_csm_contract = MagicMock()
    mock_functions = MagicMock()
    mock_get_node_operator = MagicMock()
    
    mock_get_node_operator.call = AsyncMock(return_value=mock_node_operator)
    mock_functions.getNodeOperator.return_value = mock_get_node_operator
    mock_csm_contract.functions = mock_functions
    
    event_messages = EventMessages(mock_w3)
    event_messages.csm = mock_csm_contract
    
    result = await event_messages.has_active_keys(1)
    assert result is False


@pytest.mark.asyncio
@patch.dict('os.environ', {
    'ETHERSCAN_URL': 'https://etherscan.io',
    'BEACONCHAIN_URL': 'https://beaconcha.in',
    'CSM_ADDRESS': '0x1234567890123456789012345678901234567890',
    'ACCOUNTING_ADDRESS': '0x1234567890123456789012345678901234567890'
})
async def test_has_active_keys_exception_handling():
    """Test that has_active_keys returns False when an exception occurs."""
    from src.csm_bot.events import EventMessages
    
    # Mock Web3 and contract
    mock_w3 = AsyncMock()
    
    # Mock the contract call chain to raise an exception
    mock_csm_contract = MagicMock()
    mock_functions = MagicMock()
    mock_get_node_operator = MagicMock()
    
    mock_get_node_operator.call = AsyncMock(side_effect=Exception("RPC error"))
    mock_functions.getNodeOperator.return_value = mock_get_node_operator
    mock_csm_contract.functions = mock_functions
    
    event_messages = EventMessages(mock_w3)
    event_messages.csm = mock_csm_contract
    
    result = await event_messages.has_active_keys(1)
    assert result is False
