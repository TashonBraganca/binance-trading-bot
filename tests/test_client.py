
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.client.binance_client import BinanceClient
from binance.exceptions import BinanceAPIException

@pytest.fixture
def mock_async_client_create():
    """Patch the AsyncClient.create to avoid real network calls."""
    with patch('binance.AsyncClient.create') as mock_create:
        mock_client = AsyncMock()
        mock_client.get_server_time = AsyncMock()
        mock_create.return_value = mock_client
        yield mock_create

@pytest.mark.asyncio
async def test_client_initialization_success(mock_async_client_create):
    """Test successful client initialization."""
    client = BinanceClient()
    result = await client.initialize()
    assert result is True
    assert client.client is not None
    mock_async_client_create.assert_called_once()
    client.client.get_server_time.assert_called_once()

@pytest.mark.asyncio
async def test_client_initialization_failure(mock_async_client_create):
    """Test failed client initialization."""
    mock_async_client_create.side_effect = BinanceAPIException("Invalid API Key")
    client = BinanceClient()
    result = await client.initialize()
    assert result is False

@pytest.mark.asyncio
async def test_execute_request_retry_logic(mock_async_client_create):
    """Test the retry logic in the _execute_request wrapper."""
    client = BinanceClient()
    await client.initialize()

    # Mock a method on the actual client instance
    mock_method = AsyncMock(
        side_effect=[
            BinanceAPIException("Rate limit exceeded", 429),
            BinanceAPIException("Rate limit exceeded", 429),
            {"success": True} # Success on the third attempt
        ]
    )
    
    # Mock the sleep function to avoid waiting
    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        result = await client._execute_request(mock_method, "arg1", kwarg1="value1")

    assert mock_method.call_count == 3
    assert mock_sleep.call_count == 2 # Should sleep twice before the successful call
    assert result == {"success": True}
