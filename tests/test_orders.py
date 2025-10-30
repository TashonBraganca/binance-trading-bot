import pytest
import time
from unittest.mock import MagicMock, patch

from src.orders.types import Order, OrderSide, OrderType
from src.orders.validator import OrderValidator
from src.orders.executor import OrderExecutor
from src.client.binance_client import BinanceClient

@pytest.fixture
def mock_binance_client():
    client = MagicMock(spec=BinanceClient)
    # Mock get_exchange_info to return a basic symbol info
    client.get_exchange_info.return_value = {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                    {"filterType": "LOT_SIZE", "stepSize": "0.000001"},
                    {"filterType": "MIN_NOTIONAL", "minNotional": "10.0"}
                ]
            }
        ]
    }
    # Mock get_account_information for balance checks
    client.get_account_information.return_value = {
        "assets": [
            {"asset": "USDT", "walletBalance": "10000.0", "availableBalance": "9000.0"}
        ]
    }
    client.get_balance.return_value = [
        {"asset": "USDT", "walletBalance": "10000.0", "crossWalletBalance": "10000.0", "crossUnPnl": "0.0", "availableBalance": "9000.0"}
    ]
    return client

@pytest.fixture
def order_validator(mock_binance_client):
    return OrderValidator(mock_binance_client)

@pytest.fixture
def order_executor(mock_binance_client, order_validator):
    return OrderExecutor(mock_binance_client, order_validator)

# Test OrderValidator
def test_validate_order_params_valid(order_validator):
    assert order_validator.validate_order_params("BTCUSDT", OrderSide.BUY, OrderType.MARKET, 0.001)
    assert order_validator.validate_order_params("BTCUSDT", OrderSide.BUY, OrderType.LIMIT, 0.001, 30000.00)

def test_validate_order_params_invalid_symbol(order_validator):
    assert not order_validator.validate_order_params("INVALID", OrderSide.BUY, OrderType.MARKET, 0.001)

def test_validate_order_params_invalid_quantity(order_validator):
    assert not order_validator.validate_order_params("BTCUSDT", OrderSide.BUY, OrderType.MARKET, -0.001)
    assert not order_validator.validate_order_params("BTCUSDT", OrderSide.BUY, OrderType.MARKET, 0.00123) # Invalid step size

def test_validate_order_params_invalid_price(order_validator):
    assert not order_validator.validate_order_params("BTCUSDT", OrderSide.BUY, OrderType.LIMIT, 0.001, -100.00)
    assert not order_validator.validate_order_params("BTCUSDT", OrderSide.BUY, OrderType.LIMIT, 0.001, 30000.001) # Invalid tick size

@pytest.mark.asyncio # This test is not async anymore, but keeping the decorator for now
def test_validate_sufficient_balance_success(order_validator):
    # Mock current price for calculation
    with patch.object(order_validator.binance_client, 'get_account_information', return_value={
        "assets": [
            {"asset": "USDT", "walletBalance": "10000.0", "availableBalance": "9000.0"}
        ]
    }):
        assert order_validator.validate_sufficient_balance("BTCUSDT", OrderSide.BUY, OrderType.MARKET, 100.0, 30000.00) # Assuming quantity is in USDT for market order

def test_validate_sufficient_balance_insufficient(order_validator):
    with patch.object(order_validator.binance_client, 'get_account_information', return_value={
        "assets": [
            {"asset": "USDT", "walletBalance": "100.0", "availableBalance": "20.0"} # Make available balance insufficient
        ]
    }):
        assert not order_validator.validate_sufficient_balance("BTCUSDT", OrderSide.BUY, OrderType.LIMIT, 0.001, 30000.00) # Cost 30, available 20

# Test OrderExecutor
def test_place_order_success(order_executor, mock_binance_client):
    mock_binance_client.place_order.return_value = {"orderId": 123, "status": "NEW", "executedQty": "0.0", "avgPrice": "0.0"}
    mock_binance_client.get_account_information.return_value = {"assets": [{"asset": "USDT", "walletBalance": "10000.0", "availableBalance": "9000.0"}]}

    order = Order("BTCUSDT", OrderSide.BUY, OrderType.MARKET, 0.001)
    result = order_executor.place_order(order)
    assert result is not None
    assert result.order_id == 123
    assert result.status == "NEW"
    mock_binance_client.place_order.assert_called_once()

def test_place_order_validation_failure(order_executor, mock_binance_client):
    with patch.object(order_executor.order_validator, 'validate_order_params', return_value=False):
        order = Order("INVALID", OrderSide.BUY, OrderType.MARKET, 0.001)
        result = order_executor.place_order(order)
        assert result is None
        mock_binance_client.place_order.assert_not_called()

def test_cancel_order_success(order_executor, mock_binance_client):
    mock_binance_client.cancel_order.return_value = {"symbol": "BTCUSDT", "orderId": 123}
    result = order_executor.cancel_order("BTCUSDT", order_id=123)
    assert result is True
    mock_binance_client.cancel_order.assert_called_once_with(symbol="BTCUSDT", order_id=123, orig_client_order_id=None)

def test_cancel_stale_orders(order_executor, mock_binance_client):
    # Mock open orders, one stale, one fresh
    current_time_ms = int(time.time() * 1000)
    stale_order_time = current_time_ms - (15 * 60 * 1000) # 15 minutes ago
    fresh_order_time = current_time_ms - (5 * 60 * 1000) # 5 minutes ago

    mock_binance_client.get_open_orders.return_value = [
        {"orderId": 1, "symbol": "BTCUSDT", "time": stale_order_time},
        {"orderId": 2, "symbol": "BTCUSDT", "time": fresh_order_time}
    ]
    mock_binance_client.cancel_order.return_value = {"symbol": "BTCUSDT", "orderId": 1}

    cancelled_count = order_executor.cancel_stale_orders("BTCUSDT")
    assert cancelled_count == 1
    mock_binance_client.cancel_order.assert_called_once_with(symbol="BTCUSDT", order_id=1, orig_client_order_id=None)

def test_verify_order_fill_filled(order_executor, mock_binance_client):
    order = Order("BTCUSDT", OrderSide.BUY, OrderType.MARKET, 0.001, order_id=123)
    mock_binance_client.get_all_orders.return_value = [
        {"orderId": 123, "status": "FILLED", "executedQty": "0.001", "avgPrice": "30000.0"}
    ]
    with patch('time.sleep'): # Prevent actual sleep during test
        result = order_executor.verify_order_fill(order, timeout=1)
        assert result is True
        assert order.status == "FILLED"
        assert order.filled_quantity == 0.001
        assert order.avg_fill_price == 30000.0

def test_verify_order_fill_timeout(order_executor, mock_binance_client):
    order = Order("BTCUSDT", OrderSide.BUY, OrderType.MARKET, 0.001, order_id=123)
    mock_binance_client.get_all_orders.return_value = [
        {"orderId": 123, "status": "NEW", "executedQty": "0.0", "avgPrice": "0.0"}
    ]
    with patch('time.sleep'): # Prevent actual sleep during test
        result = order_executor.verify_order_fill(order, timeout=1)
        assert result is False
        assert order.status == "EXPIRED"