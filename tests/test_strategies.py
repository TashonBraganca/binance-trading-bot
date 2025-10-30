import pytest
from unittest.mock import MagicMock, patch
import time

from src.strategies.twap import TWAPStrategy
from src.strategies.grid import GridStrategy
from src.strategies.oco import OCOStrategy
from src.strategies.trailing_stop import TrailingStopStrategy
from src.orders.types import Order, OrderSide, OrderType
from src.client.binance_client import BinanceClient
from src.orders.executor import OrderExecutor
from src.orders.validator import OrderValidator
from src.risk.manager import RiskManager
from src.risk.calculator import RiskCalculator
from src.portfolio.tracker import PortfolioTracker

@pytest.fixture
def mock_binance_client():
    client = MagicMock(spec=BinanceClient)
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
    client.get_account_information.return_value = {
        "assets": [
            {"asset": "USDT", "walletBalance": "10000.0", "availableBalance": "9000.0"}
        ]
    }
    client.get_balance.return_value = [
        {"asset": "USDT", "walletBalance": "10000.0", "crossWalletBalance": "10000.0", "crossUnPnl": "0.0", "availableBalance": "9000.0"}
    ]
    client.get_position_information.return_value = []
    client.place_order.return_value = {"orderId": 1, "status": "FILLED", "executedQty": "0.001", "avgPrice": "30000.0"}
    client.cancel_order.return_value = {"orderId": 1, "status": "CANCELED"}
    return client

@pytest.fixture
def order_validator(mock_binance_client):
    return OrderValidator(mock_binance_client)

@pytest.fixture
def order_executor(mock_binance_client, order_validator):
    return OrderExecutor(mock_binance_client, order_validator)

@pytest.fixture
def risk_calculator():
    return RiskCalculator()

@pytest.fixture
def risk_manager(mock_binance_client, risk_calculator):
    manager = RiskManager(mock_binance_client, risk_calculator)
    manager.daily_pnl_start_balance = 10000.0
    return manager

@pytest.fixture
def portfolio_tracker(mock_binance_client):
    return PortfolioTracker(mock_binance_client)

# Test TWAPStrategy
def test_twap_strategy_execute(mock_binance_client, order_executor, risk_manager, portfolio_tracker):
    twap_strategy = TWAPStrategy(mock_binance_client, order_executor, risk_manager, portfolio_tracker)
    twap_strategy.start()
    
    # Mock get_current_price
    with patch.object(twap_strategy, 'get_current_price', return_value=30000.0):
        # Mock pre_trade_check to always pass
        with patch.object(risk_manager, 'pre_trade_check', return_value=True):
            # Mock place_order to return a filled order
            order_executor.place_order = MagicMock(return_value=Order("BTCUSDT", OrderSide.BUY, OrderType.MARKET, 0.001, order_id=1, status="FILLED", filled_quantity=0.001, avg_fill_price=30000.0))
            
            # Execute 2 orders over 2 minutes, with 60s interval
            twap_strategy.execute("BTCUSDT", 0.002, 2, OrderSide.BUY, interval_seconds=60)
            assert order_executor.place_order.call_count == 2

# Test GridStrategy
def test_grid_strategy_setup_grid(mock_binance_client, order_executor, risk_manager, portfolio_tracker):
    grid_strategy = GridStrategy(mock_binance_client, order_executor, risk_manager, portfolio_tracker)
    grid_strategy.start()

    with patch.object(grid_strategy, 'get_current_price', return_value=100.0):
        with patch.object(risk_manager, 'pre_trade_check', return_value=True):
            order_executor.place_order = MagicMock(return_value=Order("TESTUSDT", OrderSide.BUY, OrderType.LIMIT, 1.0, 95.0, order_id=1, status="NEW"))
            grid_id = grid_strategy.setup_grid("TESTUSDT", 0.1, 2, 10.0) # 10% range, 2 grids, 10 USDT investment
            assert grid_id is not None
            assert len(grid_strategy.active_grids[grid_id]["buy_orders"]) > 0
            assert len(grid_strategy.active_grids[grid_id]["sell_orders"]) > 0

# Test OCOStrategy
def test_oco_strategy_place_oco_order(mock_binance_client, order_executor, risk_manager, portfolio_tracker):
    oco_strategy = OCOStrategy(mock_binance_client, order_executor, risk_manager, portfolio_tracker)
    oco_strategy.start()

    with patch.object(oco_strategy, 'get_current_price', return_value=30000.0):
        with patch.object(risk_manager, 'pre_trade_check', return_value=True):
            # Mock place_order for limit, stop-market, take-profit-market
            order_executor.place_order = MagicMock(side_effect=[
                Order("BTCUSDT", OrderSide.BUY, OrderType.LIMIT, 0.001, 30000.0, order_id=1, status="FILLED"),
                Order("BTCUSDT", OrderSide.SELL, OrderType.STOP_MARKET, 0.001, stop_price=29000.0, order_id=2, status="NEW"),
                Order("BTCUSDT", OrderSide.SELL, OrderType.TAKE_PROFIT_MARKET, 0.001, stop_price=31000.0, order_id=3, status="NEW"),
            ])
            oco_order = oco_strategy.place_oco_order("BTCUSDT", OrderSide.BUY, 0.001, 30000.0, 29000.0, 31000.0)
            assert oco_order is not None
            assert len(oco_order.orders) == 3
            assert order_executor.place_order.call_count == 3

# Test TrailingStopStrategy
def test_trailing_stop_strategy_start_trailing_stop(mock_binance_client, order_executor, risk_manager, portfolio_tracker):
    trailing_stop_strategy = TrailingStopStrategy(mock_binance_client, order_executor, risk_manager, portfolio_tracker)
    trailing_stop_strategy.start()

    # Mock an open position
    portfolio_tracker.get_position = MagicMock(return_value=MagicMock(position_amt=0.01, entry_price=30000.0, mark_price=30000.0, symbol="BTCUSDT"))
    
    with patch.object(trailing_stop_strategy, 'get_current_price', return_value=30000.0):
        ts_id = trailing_stop_strategy.start_trailing_stop("BTCUSDT", 0.01) # 1% callback rate
        assert ts_id is not None
        assert trailing_stop_strategy.active_trailing_stops[ts_id]["current_stop_price"] == 30000.0 * (1 - 0.01)

def test_trailing_stop_strategy_monitor_long_position_adjust(mock_binance_client, order_executor, risk_manager, portfolio_tracker):
    trailing_stop_strategy = TrailingStopStrategy(mock_binance_client, order_executor, risk_manager, portfolio_tracker)
    trailing_stop_strategy.start()

    # Setup initial trailing stop
    portfolio_tracker.get_position = MagicMock(return_value=MagicMock(position_amt=0.01, entry_price=30000.0, mark_price=30000.0, symbol="BTCUSDT"))
    with patch.object(trailing_stop_strategy, 'get_current_price', return_value=30000.0):
        ts_id = trailing_stop_strategy.start_trailing_stop("BTCUSDT", 0.01)

    # Simulate price moving up
    with patch.object(trailing_stop_strategy, 'get_current_price', return_value=30500.0):
        trailing_stop_strategy.monitor_trailing_stop(ts_id)
        assert trailing_stop_strategy.active_trailing_stops[ts_id]["highest_price"] == 30500.0
        assert trailing_stop_strategy.active_trailing_stops[ts_id]["current_stop_price"] == 30500.0 * (1 - 0.01)

def test_trailing_stop_strategy_monitor_long_position_trigger(mock_binance_client, order_executor, risk_manager, portfolio_tracker):
    trailing_stop_strategy = TrailingStopStrategy(mock_binance_client, order_executor, risk_manager, portfolio_tracker)
    trailing_stop_strategy.start()

    # Setup initial trailing stop
    portfolio_tracker.get_position = MagicMock(return_value=MagicMock(position_amt=0.01, entry_price=30000.0, mark_price=30000.0, symbol="BTCUSDT"))
    with patch.object(trailing_stop_strategy, 'get_current_price', return_value=30000.0):
        ts_id = trailing_stop_strategy.start_trailing_stop("BTCUSDT", 0.01)

    # Simulate price moving up and then dropping to trigger
    with patch.object(trailing_stop_strategy, 'get_current_price', side_effect=[30500.0, 30100.0]):
        trailing_stop_strategy.monitor_trailing_stop(ts_id) # Price moves to 30500, stop to 30195
        trailing_stop_strategy.monitor_trailing_stop(ts_id) # Price drops to 30100, triggers
        order_executor.place_order.assert_called_once() # Market order to close position
        assert ts_id not in trailing_stop_strategy.active_trailing_stops # Trailing stop should be removed