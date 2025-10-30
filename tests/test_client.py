import pytest
from unittest.mock import MagicMock, patch
import time

import requests
from src.client.binance_client import BinanceClient
from src.config.settings import settings
from src.config.constants import BINANCE_FUTURES_TESTNET_URL

# Mock settings for testing
@pytest.fixture(autouse=True)
def mock_settings():
    with patch('src.client.binance_client.settings') as mock_obj:
        mock_obj.BINANCE_API_KEY = "test_api_key"
        mock_obj.BINANCE_API_SECRET = "test_api_secret"
        mock_obj.TESTNET = True
        yield

@pytest.fixture
def binance_client():
    return BinanceClient()

def test_binance_client_initialization(binance_client):
    assert binance_client.base_url == BINANCE_FUTURES_TESTNET_URL
    assert binance_client.api_key == "test_api_key"
    assert binance_client.api_secret == "test_api_secret"
    assert binance_client.session is not None

@patch('requests.Session.get')
def test_get_exchange_info_success(mock_get, binance_client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"symbols": [{"symbol": "BTCUSDT"}]}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    response = binance_client.get_exchange_info()
    assert response == {"symbols": [{"symbol": "BTCUSDT"}]}
    mock_get.assert_called_once_with(f"{BINANCE_FUTURES_TESTNET_URL}/fapi/v1/exchangeInfo", params={}, timeout=10)

@patch('requests.Session.get')
def test_get_account_information_success(mock_get, binance_client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"assets": [{"asset": "USDT", "walletBalance": "1000"}]}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    response = binance_client.get_account_information()
    assert response == {"assets": [{"asset": "USDT", "walletBalance": "1000"}]}
    assert "timestamp" in mock_get.call_args.kwargs["params"]
    assert "signature" in mock_get.call_args.kwargs["params"]

@patch('requests.Session.post')
def test_place_order_success(mock_post, binance_client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"orderId": 123, "status": "NEW"}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    response = binance_client.place_order(symbol="BTCUSDT", side="BUY", order_type="MARKET", quantity=0.001)
    assert response == {"orderId": 123, "status": "NEW"}
    assert "timestamp" in mock_post.call_args.kwargs["data"]
    assert "signature" in mock_post.call_args.kwargs["data"]

@patch('requests.Session.get')
def test_rate_limit_handling(mock_get, binance_client):
    mock_response_429 = MagicMock()
    mock_response_429.status_code = 429
    mock_response_429.headers = {"Retry-After": "1"}
    mock_response_429.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response_429)

    mock_response_200 = MagicMock()
    mock_response_200.status_code = 200
    mock_response_200.json.return_value = {"serverTime": 1678886400000}
    mock_response_200.raise_for_status.return_value = None

    mock_get.side_effect = [mock_response_429, mock_response_200]

    # We expect a warning log for rate limit and then a successful response
    with patch('time.sleep') as mock_sleep:
        response = binance_client.get_server_time()
        assert response == 1678886400000
        mock_sleep.assert_called_once_with(1)
        assert mock_get.call_count == 2

@patch('requests.Session.get')
def test_invalid_api_credentials(mock_get, binance_client):
    mock_response_401 = MagicMock()
    mock_response_401.status_code = 401
    mock_response_401.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response_401)

    mock_get.return_value = mock_response_401

    with pytest.raises(requests.exceptions.HTTPError):
        binance_client.get_account_information()

@patch('requests.Session.get')
def test_network_timeout_retry(mock_get, binance_client):
    mock_get.side_effect = [requests.exceptions.Timeout, MagicMock(status_code=200, json=lambda: {"serverTime": 123}, raise_for_status=lambda: None)]

    with patch('time.sleep') as mock_sleep:
        response = binance_client.get_server_time()
        assert response == 123
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once() # Should sleep after first timeout