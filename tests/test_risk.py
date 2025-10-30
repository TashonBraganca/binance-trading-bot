import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from src.risk.calculator import RiskCalculator
from src.risk.manager import RiskManager
from src.client.binance_client import BinanceClient
from src.orders.types import Position, Order, OrderSide, OrderType
from src.config.constants import DEFAULT_MAX_POSITION_SIZE_PCT, DEFAULT_MAX_LEVERAGE, DEFAULT_MAX_DAILY_LOSS_PCT, DEFAULT_MAX_OPEN_POSITIONS

@pytest.fixture
def mock_binance_client():
    client = MagicMock(spec=BinanceClient)
    client.get_balance.return_value = [
        {"asset": "USDT", "walletBalance": "10000.0", "crossWalletBalance": "10000.0", "crossUnPnl": "0.0", "availableBalance": "9000.0"}
    ]
    client.get_position_information.return_value = [] # No open positions by default
    return client

@pytest.fixture
def risk_calculator():
    return RiskCalculator()

@pytest.fixture
def risk_manager(mock_binance_client, risk_calculator):
    manager = RiskManager(mock_binance_client, risk_calculator)
    # Mock the initial balance snapshot to avoid API call during fixture setup
    manager.daily_pnl_start_balance = 10000.0
    return manager

# Test RiskCalculator
def test_calculate_unrealized_pnl_long(risk_calculator):
    position = Position("BTCUSDT", 30000.0, 30500.0, 0.01, 0.0, 1, "ISOLATED", position_side="LONG")
    assert risk_calculator.calculate_unrealized_pnl(position, 30500.0) == 5.0

def test_calculate_unrealized_pnl_short(risk_calculator):
    position = Position("BTCUSDT", 30000.0, 29500.0, -0.01, 0.0, 1, "ISOLATED", position_side="SHORT")
    assert risk_calculator.calculate_unrealized_pnl(position, 29500.0) == 5.0

def test_calculate_total_unrealized_pnl(risk_calculator):
    positions = [
        Position("BTCUSDT", 30000.0, 30500.0, 0.01, 0.0, 1, "ISOLATED", position_side="LONG"),
        Position("ETHUSDT", 2000.0, 1950.0, -0.1, 0.0, 1, "ISOLATED", position_side="SHORT")
    ]
    current_prices = {"BTCUSDT": 30500.0, "ETHUSDT": 1950.0}
    expected_pnl = 5.0 + 5.0 # 0.01 * 500.0 + 0.1 * 50.0
    assert risk_calculator.calculate_total_unrealized_pnl(positions, current_prices) == expected_pnl

def test_calculate_position_value(risk_calculator):
    position = Position("BTCUSDT", 30000.0, 30500.0, 0.01, 0.0, 1, "ISOLATED", position_side="LONG")
    assert risk_calculator.calculate_position_value(position, 30500.0) == 0.01 * 30500.0

def test_calculate_risk_reward_ratio_long(risk_calculator):
    # Entry 100, SL 90 (Risk 10), TP 120 (Reward 20) -> Ratio 2
    assert risk_calculator.calculate_risk_reward_ratio(100.0, 90.0, 120.0, True) == 2.0

def test_calculate_risk_reward_ratio_short(risk_calculator):
    # Entry 100, SL 110 (Risk 10), TP 80 (Reward 20) -> Ratio 2
    assert risk_calculator.calculate_risk_reward_ratio(100.0, 110.0, 80.0, False) == 2.0

# Test RiskManager
def test_check_daily_loss_limit_not_hit(risk_manager):
    # Current balance is 10000, start balance is 10000, no loss
    assert not risk_manager.check_daily_loss_limit()

def test_check_daily_loss_limit_hit(risk_manager, mock_binance_client):
    # Simulate balance drop to trigger daily loss limit
    mock_binance_client.get_balance.return_value = [
        {"asset": "USDT", "walletBalance": "9400.0", "crossWalletBalance": "9400.0", "crossUnPnl": "0.0", "availableBalance": "9400.0"}
    ]
    # Max daily loss is 5%, so 9500 is the threshold
    assert risk_manager.check_daily_loss_limit()

def test_check_position_size_limit_within_limit(risk_manager, mock_binance_client):
    # Max position size 10% of 10000 = 1000 USDT
    # Order value 0.01 BTC * 30000 = 300 USDT
    order = Order("BTCUSDT", OrderSide.BUY, OrderType.MARKET, 0.01)
    assert risk_manager.check_position_size_limit("BTCUSDT", 0.01, 30000.0, True)

def test_check_position_size_limit_exceeded(risk_manager, mock_binance_client):
    # Max position size 10% of 10000 = 1000 USDT
    # Order value 0.05 BTC * 30000 = 1500 USDT
    order = Order("BTCUSDT", OrderSide.BUY, OrderType.MARKET, 0.05)
    assert not risk_manager.check_position_size_limit("BTCUSDT", 0.05, 30000.0, True)

def test_check_leverage_limit_within_limit(risk_manager):
    assert risk_manager.check_leverage_limit(5)

def test_check_leverage_limit_exceeded(risk_manager):
    assert not risk_manager.check_leverage_limit(15) # Default max is 10

def test_check_max_open_positions_within_limit(risk_manager):
    open_positions = [Position("BTCUSDT", 0,0,0,0,0,"ISOLATED", position_side="BOTH")]
    assert risk_manager.check_max_open_positions(open_positions)

def test_check_max_open_positions_exceeded(risk_manager):
    open_positions = [Position(f"SYM{i}", 0,0,0,0,0,"ISOLATED", position_side="BOTH") for i in range(DEFAULT_MAX_OPEN_POSITIONS + 1)]
    assert not risk_manager.check_max_open_positions(open_positions)

def test_pre_trade_check_success(risk_manager, mock_binance_client):
    order = Order("BTCUSDT", OrderSide.BUY, OrderType.MARKET, 0.001)
    open_positions = []
    assert risk_manager.pre_trade_check(order, 30000.0, 5, open_positions)

def test_pre_trade_check_failure_daily_loss(risk_manager, mock_binance_client):
    mock_binance_client.get_balance.return_value = [
        {"asset": "USDT", "walletBalance": "9400.0", "crossWalletBalance": "9400.0", "crossUnPnl": "0.0", "availableBalance": "9400.0"}
    ]
    order = Order("BTCUSDT", OrderSide.BUY, OrderType.MARKET, 0.001)
    open_positions = []
    assert not risk_manager.pre_trade_check(order, 30000.0, 5, open_positions)