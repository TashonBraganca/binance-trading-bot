
import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
from src.risk.manager import RiskManager

@pytest.fixture
def mock_binance_client():
    """Fixture to create a mock BinanceClient."""
    client = MagicMock()
    client.get_account_info = AsyncMock()
    client.get_ticker = AsyncMock()
    return client

@pytest.fixture
def risk_manager(mock_binance_client):
    """Fixture to create a RiskManager with a mocked client."""
    return RiskManager(mock_binance_client)

@pytest.mark.asyncio
async def test_leverage_check_pass(risk_manager):
    """Test that leverage check passes when within limits."""
    order_data = {'leverage': 5}
    risk_manager.max_leverage = 10
    assert risk_manager._check_leverage(order_data) is True

@pytest.mark.asyncio
async def test_leverage_check_fail(risk_manager):
    """Test that leverage check fails when exceeding limits."""
    order_data = {'leverage': 20}
    risk_manager.max_leverage = 10
    assert risk_manager._check_leverage(order_data) is False

@pytest.mark.asyncio
async def test_max_open_positions_check_pass(risk_manager):
    """Test that max open positions check passes."""
    risk_manager.open_positions = [{}, {}, {}] # 3 open positions
    risk_manager.max_open_positions = 5
    assert risk_manager._check_max_open_positions() is True

@pytest.mark.asyncio
async def test_max_open_positions_check_fail(risk_manager):
    """Test that max open positions check fails."""
    risk_manager.open_positions = [{}, {}, {}, {}, {}] # 5 open positions
    risk_manager.max_open_positions = 5
    assert risk_manager._check_max_open_positions() is False

@pytest.mark.asyncio
async def test_position_size_check_pass(risk_manager):
    """Test that position size check passes."""
    order_data = {'symbol': 'BTCUSDT', 'quantity': '0.1', 'price': '50000'}
    account_balance = Decimal('100000')
    risk_manager.max_position_size_pct = Decimal('0.1') # 10%
    risk_manager.client.get_ticker.return_value = {'lastPrice': '50000'}
    
    assert await risk_manager._check_position_size(order_data, account_balance) is True

@pytest.mark.asyncio
async def test_position_size_check_fail(risk_manager):
    """Test that position size check fails due to exceeding percentage."""
    order_data = {'symbol': 'BTCUSDT', 'quantity': '0.3', 'price': '50000'} # 15k position
    account_balance = Decimal('100000') # 100k balance
    risk_manager.max_position_size_pct = Decimal('0.1') # 10% limit (10k)
    risk_manager.client.get_ticker.return_value = {'lastPrice': '50000'}

    assert await risk_manager._check_position_size(order_data, account_balance) is False

@pytest.mark.asyncio
async def test_daily_loss_limit_check_pass(risk_manager):
    """Test that daily loss limit check passes."""
    account_balance = Decimal('10000')
    risk_manager.daily_pnl = Decimal('-400') # -4% loss
    risk_manager.max_daily_loss_pct = Decimal('-0.05') # -5% limit
    assert risk_manager._check_daily_loss_limit(account_balance) is True

@pytest.mark.asyncio
async def test_daily_loss_limit_check_fail(risk_manager):
    """Test that daily loss limit check fails."""
    account_balance = Decimal('10000')
    risk_manager.daily_pnl = Decimal('-600') # -6% loss
    risk_manager.max_daily_loss_pct = Decimal('-0.05') # -5% limit
    assert risk_manager._check_daily_loss_limit(account_balance) is False
