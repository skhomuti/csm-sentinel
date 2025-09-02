import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.csm_bot.texts import target_validators_count_changed
from hexbytes import HexBytes

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

# IPFS Distribution Filter Tests

@pytest.mark.asyncio 
@patch('aiohttp.ClientSession.get')
@patch.dict('os.environ', {
    'ETHERSCAN_URL': 'https://etherscan.io',
    'BEACONCHAIN_URL': 'https://beaconcha.in',
    'CSM_ADDRESS': '0x1234567890123456789012345678901234567890',
    'ACCOUNTING_ADDRESS': '0x1234567890123456789012345678901234567890'
})
async def test_ipfs_distribution_filter_with_matching_operator(mock_get):
    """Test that IPFSDistributionFilter returns True when node operator exists in IPFS data."""
    from src.csm_bot.events import IPFSDistributionFilter
    from src.csm_bot.models import Event
    
    # Mock IPFS response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "operators": {
            "123": {"some": "data"},
            "456": {"other": "data"}
        }
    })
    
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)
    mock_get.return_value = mock_context_manager
    
    # Create test event
    event = Event(
        event="DistributionLogUpdated",
        args={"logCid": "QmTestHash123"},
        block=123456,
        tx=HexBytes("0x1234567890123456789012345678901234567890123456789012345678901234"),
        address="0x0000000000000000000000000000000000000000",
    )
    
    # Test the filter
    filter_instance = IPFSDistributionFilter()
    result = await filter_instance.should_notify(event, 123, None)
    
    assert result is True
    mock_get.assert_called_once_with("https://ipfs.io/ipfs/QmTestHash123")


@pytest.mark.asyncio
@patch('aiohttp.ClientSession.get')
@patch.dict('os.environ', {
    'ETHERSCAN_URL': 'https://etherscan.io',
    'BEACONCHAIN_URL': 'https://beaconcha.in',
    'CSM_ADDRESS': '0x1234567890123456789012345678901234567890',
    'ACCOUNTING_ADDRESS': '0x1234567890123456789012345678901234567890'
})
async def test_ipfs_distribution_filter_with_non_matching_operator(mock_get):
    """Test that IPFSDistributionFilter returns False when node operator doesn't exist in IPFS data."""
    from src.csm_bot.events import IPFSDistributionFilter
    from src.csm_bot.models import Event
    
    # Mock IPFS response
    mock_response = AsyncMock()
    mock_response.status = 200 
    mock_response.json = AsyncMock(return_value={
        "operators": {
            "123": {"some": "data"},
            "456": {"other": "data"}
        }
    })
    
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)
    mock_get.return_value = mock_context_manager
    
    # Create test event
    event = Event(
        event="DistributionLogUpdated",
        args={"logCid": "QmTestHash123"},
        block=123456,
        tx=HexBytes("0x1234567890123456789012345678901234567890123456789012345678901234"),
        address="0x0000000000000000000000000000000000000000",
    )
    
    # Test the filter
    filter_instance = IPFSDistributionFilter()
    result = await filter_instance.should_notify(event, 999, None)  # Non-existing operator
    
    assert result is False
    mock_get.assert_called_once_with("https://ipfs.io/ipfs/QmTestHash123")


@pytest.mark.asyncio
@patch('aiohttp.ClientSession.get')
@patch.dict('os.environ', {
    'ETHERSCAN_URL': 'https://etherscan.io',
    'BEACONCHAIN_URL': 'https://beaconcha.in',
    'CSM_ADDRESS': '0x1234567890123456789012345678901234567890',
    'ACCOUNTING_ADDRESS': '0x1234567890123456789012345678901234567890'
})
async def test_ipfs_distribution_filter_caches_data(mock_get):
    """Test that IPFSDistributionFilter caches data and doesn't fetch multiple times for same event."""
    from src.csm_bot.events import IPFSDistributionFilter
    from src.csm_bot.models import Event
    
    # Mock IPFS response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "operators": {
            "123": {"some": "data"},
            "456": {"other": "data"}
        }
    })
    
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)
    mock_get.return_value = mock_context_manager
    
    # Create test event
    event = Event(
        event="DistributionLogUpdated",
        args={"logCid": "QmTestHash123"},
        block=123456,
        tx=HexBytes("0x1234567890123456789012345678901234567890123456789012345678901234"),
        address="0x0000000000000000000000000000000000000000",
    )
    
    # Test the filter multiple times with same event
    filter_instance = IPFSDistributionFilter()
    
    result1 = await filter_instance.should_notify(event, 123, None)
    result2 = await filter_instance.should_notify(event, 456, None)
    result3 = await filter_instance.should_notify(event, 999, None)
    
    assert result1 is True
    assert result2 is True
    assert result3 is False
    
    # Should only fetch once despite multiple calls
    assert mock_get.call_count == 1
    mock_get.assert_called_with("https://ipfs.io/ipfs/QmTestHash123")


@pytest.mark.asyncio
@patch('aiohttp.ClientSession.get')
@patch.dict('os.environ', {
    'ETHERSCAN_URL': 'https://etherscan.io',
    'BEACONCHAIN_URL': 'https://beaconcha.in',
    'CSM_ADDRESS': '0x1234567890123456789012345678901234567890',
    'ACCOUNTING_ADDRESS': '0x1234567890123456789012345678901234567890'
})
async def test_ipfs_distribution_filter_handles_http_error(mock_get):
    """Test that IPFSDistributionFilter handles HTTP errors gracefully."""
    from src.csm_bot.events import IPFSDistributionFilter
    from src.csm_bot.models import Event
    
    # Mock HTTP error response
    mock_response = AsyncMock()
    mock_response.status = 404
    
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)
    mock_get.return_value = mock_context_manager
    
    # Create test event
    event = Event(
        event="DistributionLogUpdated",
        args={"logCid": "QmTestHash123"},
        block=123456,
        tx=HexBytes("0x1234567890123456789012345678901234567890123456789012345678901234"),
        address="0x0000000000000000000000000000000000000000",
    )
    
    # Test the filter
    filter_instance = IPFSDistributionFilter()
    result = await filter_instance.should_notify(event, 123, None)
    
    # Should return False when unable to fetch data
    assert result is False


@pytest.mark.asyncio
@patch.dict('os.environ', {
    'ETHERSCAN_URL': 'https://etherscan.io',
    'BEACONCHAIN_URL': 'https://beaconcha.in',
    'CSM_ADDRESS': '0x1234567890123456789012345678901234567890',
    'ACCOUNTING_ADDRESS': '0x1234567890123456789012345678901234567890'
})
async def test_ipfs_distribution_filter_handles_missing_tree_cid():
    """Test that IPFSDistributionFilter handles missing logCid gracefully."""
    from src.csm_bot.events import IPFSDistributionFilter
    from src.csm_bot.models import Event
    
    # Create test event without logCid
    event = Event(
        event="DistributionLogUpdated", 
        args={"someOtherField": "value"},  # No logCid
        block=123456,
        tx=HexBytes("0x1234567890123456789012345678901234567890123456789012345678901234"),
        address="0x0000000000000000000000000000000000000000",
    )
    
    # Test the filter
    filter_instance = IPFSDistributionFilter()
    result = await filter_instance.should_notify(event, 123, None)
    
    # Should return False when logCid is missing
    assert result is False


@pytest.mark.asyncio
@patch('aiohttp.ClientSession.get')
@patch.dict('os.environ', {
    'ETHERSCAN_URL': 'https://etherscan.io',
    'BEACONCHAIN_URL': 'https://beaconcha.in',
    'CSM_ADDRESS': '0x1234567890123456789012345678901234567890',
    'ACCOUNTING_ADDRESS': '0x1234567890123456789012345678901234567890'
})
async def test_ipfs_distribution_filter_handles_empty_operators(mock_get):
    """Test that IPFSDistributionFilter handles empty operators object."""
    from src.csm_bot.events import IPFSDistributionFilter
    from src.csm_bot.models import Event
    
    # Mock IPFS response with empty operators
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={
        "operators": {}
    })
    
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)
    mock_get.return_value = mock_context_manager
    
    # Create test event
    event = Event(
        event="DistributionLogUpdated",
        args={"logCid": "QmTestHash123"},
        block=123456,
        tx=HexBytes("0x1234567890123456789012345678901234567890123456789012345678901234"),
        address="0x0000000000000000000000000000000000000000",
    )
    
    # Test the filter
    filter_instance = IPFSDistributionFilter()
    result = await filter_instance.should_notify(event, 123, None)
    
    assert result is False


@pytest.mark.asyncio
@patch('aiohttp.ClientSession.get')
@patch.dict('os.environ', {
    'ETHERSCAN_URL': 'https://etherscan.io',
    'BEACONCHAIN_URL': 'https://beaconcha.in',
    'CSM_ADDRESS': '0x1234567890123456789012345678901234567890',
    'ACCOUNTING_ADDRESS': '0x1234567890123456789012345678901234567890'
})
async def test_ipfs_distribution_filter_handles_timeout(mock_get):
    """Test that IPFSDistributionFilter handles timeout errors gracefully."""
    from src.csm_bot.events import IPFSDistributionFilter
    from src.csm_bot.models import Event
    import asyncio
    
    # Mock timeout error
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError("Timeout"))
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)
    mock_get.return_value = mock_context_manager
    
    # Create test event
    event = Event(
        event="DistributionLogUpdated",
        args={"logCid": "QmTestHash123"},
        block=123456,
        tx=HexBytes("0x1234567890123456789012345678901234567890123456789012345678901234"),
        address="0x0000000000000000000000000000000000000000",
    )
    
    # Test the filter
    filter_instance = IPFSDistributionFilter()
    result = await filter_instance.should_notify(event, 123, None)
    
    # Should return False when timeout occurs
    assert result is False
