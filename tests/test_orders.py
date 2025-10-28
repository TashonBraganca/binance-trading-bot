
import pytest
from unittest.mock import AsyncMock, MagicMock, ANY
from decimal import Decimal
from src.orders.executor import OrderExecutor

@pytest.fixture
def mock_binance_client():
    client = MagicMock()
    client.place_order = AsyncMock(return_value={'symbol': 'BTCUSDT', 'orderId': 123, 'status': 'NEW'})
    client.get_order = AsyncMock(return_value={'symbol': 'BTCUSDT', 'orderId': 123, 'status': 'FILLED', 'avgPrice': '50000', 'executedQty': '0.1'})
    return client

@pytest.fixture
def mock_risk_manager():
    manager = MagicMock()
    manager.pre_trade_check = AsyncMock(return_value=True)
    return manager

@pytest.fixture
def mock_order_validator(mock_binance_client, mock_risk_manager):
    validator = MagicMock()
    validator.validate_order = AsyncMock(return_value=True)
    # Mock the internal method for quantity formatting
    validator._get_symbol_filters = MagicMock(return_value={
        'LOT_SIZE': {'stepSize': '0.001'}
    })
    return validator

@pytest.fixture
def order_executor(mock_binance_client, mock_risk_manager):
    executor = OrderExecutor(mock_binance_client, mock_risk_manager)
    # Replace the real validator with our mock
    executor.validator = mock_order_validator(mock_binance_client, mock_risk_manager)
    return executor

@pytest.mark.asyncio
async def test_execute_order_success(order_executor, mock_binance_client):
    """Test successful order execution path."""
    order_data = {
        'symbol': 'BTCUSDT',
        'side': 'BUY',
        'type': 'MARKET',
        'quantity': Decimal('0.1')
    }

    result = await order_executor.execute_order(order_data)

    # Assert that validation was called
    order_executor.validator.validate_order.assert_called_once_with(order_data)
    
    # Assert that the order was placed
    mock_binance_client.place_order.assert_called_once()
    
    # Assert that verification was attempted
    mock_binance_client.get_order.assert_called_once_with(symbol='BTCUSDT', orderId=123)

    assert result['status'] == 'FILLED'

@pytest.mark.asyncio
async def test_execute_order_validation_failure(order_executor, mock_binance_client):
    """Test the case where order validation fails."""
    order_executor.validator.validate_order.return_value = False
    order_data = {'symbol': 'BTCUSDT', 'side': 'BUY', 'type': 'MARKET', 'quantity': Decimal('0.1')}

    result = await order_executor.execute_order(order_data)

    # Assert that place_order was NOT called
    mock_binance_client.place_order.assert_not_called()
    assert result['status'] == 'REJECTED'
    assert 'Validation failed' in result['error']

@pytest.mark.asyncio
async def test_quantity_formatting(order_executor):
    """Test that the quantity is correctly formatted to the symbol's step size."""
    unformatted_qty = Decimal("0.123456")
    formatted_qty = order_executor._format_quantity("BTCUSDT", unformatted_qty)
    
    # Based on the mock LOT_SIZE filter ('stepSize': '0.001')
    assert formatted_qty == Decimal("0.123")

@pytest.mark.asyncio
async def test_verification_partial_fill(order_executor, mock_binance_client):
    """Test the verification logic for a partially filled order."""
    placed_order = {'symbol': 'BTCUSDT', 'orderId': 456}
    mock_binance_client.get_order.return_value = {
        'symbol': 'BTCUSDT', 
        'orderId': 456, 
        'status': 'PARTIALLY_FILLED',
        'origQty': '1.0',
        'executedQty': '0.5'
    }

    result = await order_executor._verify_execution(placed_order)

    assert result['status'] == 'PARTIALLY_FILLED'
