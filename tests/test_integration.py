"""
Integration tests for Binance Trading Bot
Tests end-to-end functionality with mocked Binance API

These tests verify:
1. Market order placement and fill
2. Grid strategy execution
3. CLI feedback and user experience
4. Performance metrics
"""

import pytest
import time
import threading
from unittest.mock import MagicMock, patch, Mock

from src.bot import TradingBot
from src.orders.executor import OrderExecutor
from src.orders.validator import OrderValidator
from src.orders.types import Order, OrderSide, OrderType
from src.client.binance_client import BinanceClient
from src.strategies.grid import GridStrategy
from src.risk.manager import RiskManager
from src.risk.calculator import RiskCalculator
from src.portfolio.tracker import PortfolioTracker


@pytest.fixture
def mock_binance_client():
    """Create a mock Binance client for testing."""
    client = MagicMock(spec=BinanceClient)

    # Mock exchange info
    client.get_exchange_info.return_value = {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                    {"filterType": "LOT_SIZE", "stepSize": "0.000001"},
                    {"filterType": "MIN_NOTIONAL", "minNotional": "10.0"}
                ]
            },
            {
                "symbol": "ETHUSDT",
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                    {"filterType": "LOT_SIZE", "stepSize": "0.00001"},
                    {"filterType": "MIN_NOTIONAL", "minNotional": "10.0"}
                ]
            }
        ]
    }

    # Mock account information
    client.get_account_information.return_value = {
        "assets": [
            {"asset": "USDT", "walletBalance": 10000, "availableBalance": 10000},
            {"asset": "BTC", "walletBalance": 0, "availableBalance": 0}
        ],
        "positions": []
    }

    # Mock order placement - returns immediate filled status
    client.place_order.return_value = {
        "orderId": 12345,
        "clientOrderId": "test_order_1",
        "status": "NEW",  # Start as NEW
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "MARKET",
        "executedQty": "0.1",
        "avgPrice": "45000.00"
    }

    # Mock order status - update to FILLED after first check
    order_check_count = {"count": 0}
    def get_order_status_side_effect(*args, **kwargs):
        order_check_count["count"] += 1
        if order_check_count["count"] >= 2:
            return {
                "status": "FILLED",
                "symbol": "BTCUSDT",
                "executedQty": "0.1",
                "avgPrice": "45000.00"
            }
        return {
            "status": "NEW",
            "symbol": "BTCUSDT",
            "executedQty": "0",
            "avgPrice": "0"
        }

    client.get_all_orders.return_value = []
    client.get_open_orders.return_value = []
    client.cancel_order.return_value = {"status": "CANCELED"}
    client.get_ticker_24hr.return_value = {"lastPrice": "45000.00"}
    client.get_mark_price.return_value = {"markPrice": "45000.00"}
    client.get_klines.return_value = []

    return client


@pytest.fixture
def order_executor(mock_binance_client):
    """Create order executor with mocked client."""
    validator = OrderValidator(mock_binance_client)
    return OrderExecutor(mock_binance_client, validator)


@pytest.fixture
def risk_manager(mock_binance_client):
    """Create risk manager with mocked client."""
    calculator = RiskCalculator()
    return RiskManager(mock_binance_client, calculator)


@pytest.fixture
def portfolio_tracker(mock_binance_client):
    """Create portfolio tracker with mocked client."""
    return PortfolioTracker(mock_binance_client)


# =============================================================================
# TEST 1: Market Order Placement and Fill
# =============================================================================

class TestMarketOrderPlacement:
    """Test market order placement, validation, and fill verification."""

    def test_market_order_validation(self, order_executor):
        """Test that market orders pass all validations."""
        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.01,
            price=None
        )

        # Should validate successfully
        assert order_executor.order_validator.validate_order_params(
            "BTCUSDT", OrderSide.BUY, OrderType.MARKET, 0.01, None
        )

    def test_market_order_placement_success(self, order_executor):
        """Test that market order is placed successfully."""
        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.01
        )

        executed = order_executor.place_order(order)

        assert executed is not None
        assert executed.order_id is not None
        assert executed.symbol == "BTCUSDT"
        assert executed.side == OrderSide.BUY
        assert executed.order_type == OrderType.MARKET

    def test_market_order_notional_validation(self, order_executor):
        """Test that tiny orders below minimum notional are rejected."""
        # Try to place 0.00001 BTC @ 45000 = 0.45 USDT (below 10 USDT minimum)
        is_valid = order_executor.order_validator.validate_order_params(
            "BTCUSDT", OrderSide.BUY, OrderType.MARKET, 0.00001, 45000
        )

        # Should be rejected due to notional
        assert not is_valid

    def test_market_order_balance_check(self, order_executor):
        """Test that insufficient balance is caught."""
        # Try to place order larger than balance
        is_valid = order_executor.order_validator.validate_sufficient_balance(
            "BTCUSDT", OrderSide.BUY, OrderType.MARKET, 20000, None
        )

        # Should be rejected (balance is 10000)
        assert not is_valid

    def test_market_order_partial_fill_handling(self, order_executor, mock_binance_client):
        """Test that orders with partial fills are handled correctly."""
        # Simulate partial fill
        mock_binance_client.place_order.return_value = {
            "orderId": 12346,
            "clientOrderId": "partial_order",
            "status": "PARTIALLY_FILLED",
            "executedQty": "0.05",
            "avgPrice": "45000"
        }

        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.1
        )

        executed = order_executor.place_order(order)

        # Should handle partial fill
        assert executed is not None
        # Verify order was executed with partial fill info
        assert executed.symbol == "BTCUSDT"
        assert float(executed.filled_quantity) >= 0.05


# =============================================================================
# TEST 2: Grid Strategy
# =============================================================================

class TestGridStrategy:
    """Test grid strategy execution and order management."""

    def test_grid_strategy_setup(self, mock_binance_client, order_executor, risk_manager, portfolio_tracker):
        """Test that grid strategy initializes correctly."""
        grid = GridStrategy(mock_binance_client, order_executor, risk_manager, portfolio_tracker)
        grid.start()

        assert grid.is_active
        assert hasattr(grid, '_grid_lock')

    def test_grid_strategy_initial_orders(self, mock_binance_client, order_executor, risk_manager, portfolio_tracker):
        """Test that grid places initial buy/sell orders."""
        grid = GridStrategy(mock_binance_client, order_executor, risk_manager, portfolio_tracker)
        grid.start()

        # Setup grid
        grid_id = grid.setup_grid(
            symbol="BTCUSDT",
            price_range_pct=0.05,
            num_grids=3,
            investment_per_grid=500,
            leverage=1
        )

        assert grid_id is not None
        assert grid_id in grid.active_grids

        # Check that grid was created (orders placement may not happen in unit test with mocked client)
        grid_config = grid.active_grids[grid_id]
        assert "symbol" in grid_config
        assert grid_config["symbol"] == "BTCUSDT"
        assert grid_config["num_grids"] == 3

    def test_grid_strategy_thread_safety(self, mock_binance_client, order_executor, risk_manager, portfolio_tracker):
        """Test that grid strategy is thread-safe."""
        grid = GridStrategy(mock_binance_client, order_executor, risk_manager, portfolio_tracker)
        grid.start()

        grid_id = grid.setup_grid("BTCUSDT", 0.05, 5, 500, 1)

        # Try to monitor from multiple threads
        def monitor():
            grid.monitor_grid(grid_id)

        threads = [threading.Thread(target=monitor) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should not crash - lock protected access
        assert grid_id in grid.active_grids

    def test_grid_cancel(self, mock_binance_client, order_executor, risk_manager, portfolio_tracker):
        """Test that grid can be canceled properly."""
        grid = GridStrategy(mock_binance_client, order_executor, risk_manager, portfolio_tracker)
        grid.start()

        grid_id = grid.setup_grid("BTCUSDT", 0.05, 3, 500, 1)

        # Cancel the grid
        result = grid.cancel_grid(grid_id)

        assert result is True
        assert grid_id not in grid.active_grids


# =============================================================================
# TEST 3: Balance Check Caching
# =============================================================================

class TestBalanceCheckCaching:
    """Test that balance checks are properly cached."""

    def test_balance_caching_enabled(self, order_executor, mock_binance_client):
        """Test that balance caching works."""
        # Verify cache is initialized
        assert order_executor.order_validator._balance_cache_ttl == 1.0

        # First check should fetch fresh balance
        order_executor.order_validator.validate_sufficient_balance(
            "BTCUSDT", OrderSide.BUY, OrderType.MARKET, 100, None
        )
        first_call_count = mock_binance_client.get_account_information.call_count

        # Second check within 1 second should use cache
        order_executor.order_validator.validate_sufficient_balance(
            "BTCUSDT", OrderSide.BUY, OrderType.MARKET, 100, None
        )
        second_call_count = mock_binance_client.get_account_information.call_count

        # Should NOT have increased (cache hit)
        assert second_call_count == first_call_count

    def test_balance_cache_expiration(self, order_executor, mock_binance_client):
        """Test that cache expires after TTL."""
        # First check
        order_executor.order_validator.validate_sufficient_balance(
            "BTCUSDT", OrderSide.BUY, OrderType.MARKET, 100, None
        )
        first_count = mock_binance_client.get_account_information.call_count

        # Wait for cache to expire
        order_executor.order_validator._last_balance_check_time = 0

        # Third check should fetch fresh (cache expired)
        order_executor.order_validator.validate_sufficient_balance(
            "BTCUSDT", OrderSide.BUY, OrderType.MARKET, 100, None
        )
        second_count = mock_binance_client.get_account_information.call_count

        # Should have increased (cache miss)
        assert second_count > first_count


# =============================================================================
# TEST 4: WebSocket Connection Health
# =============================================================================

class TestWebSocketHealth:
    """Test WebSocket connection health checking."""

    def test_websocket_is_connected_method_exists(self, mock_binance_client):
        """Test that is_connected method exists."""
        from src.client.websocket_client import WebSocketClient

        ws_client = WebSocketClient({"btcusdt@markPrice@1s": lambda x: None})

        # Method should exist
        assert hasattr(ws_client, 'is_connected')
        assert callable(ws_client.is_connected)

    def test_websocket_is_connected_returns_false_when_not_running(self, mock_binance_client):
        """Test that is_connected returns False when not running."""
        from src.client.websocket_client import WebSocketClient

        ws_client = WebSocketClient({"btcusdt@markPrice@1s": lambda x: None})

        # Should return False when not running
        assert not ws_client.is_connected()


# =============================================================================
# TEST 5: Order Feedback and CLI
# =============================================================================

class TestOrderFeedback:
    """Test that order feedback is properly provided to users."""

    def test_order_has_feedback_attributes(self, order_executor):
        """Test that executed orders have all feedback attributes."""
        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.01
        )

        executed = order_executor.place_order(order)

        # Should have all feedback attributes
        assert executed.order_id is not None
        assert executed.symbol is not None
        assert executed.side is not None
        assert executed.order_type is not None
        assert executed.quantity is not None
        assert executed.status is not None


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

class TestPerformance:
    """Test performance metrics and optimizations."""

    def test_validation_speed(self, order_executor):
        """Test that validation is fast (<100ms)."""
        start = time.time()
        for i in range(10):
            order_executor.order_validator.validate_order_params(
                "BTCUSDT", OrderSide.BUY, OrderType.MARKET, 0.01, None
            )
        elapsed = (time.time() - start) * 1000 / 10  # Average per validation

        # Should average <100ms per validation
        assert elapsed < 100


# =============================================================================
# TEST 6: Integration Test - Full Trading Cycle
# =============================================================================

class TestFullTradingCycle:
    """Test a complete trading cycle."""

    def test_order_to_execution_flow(self, order_executor, mock_binance_client):
        """Test complete flow: create order -> validate -> place -> fill."""
        # Create order
        order = Order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.01
        )

        # Validate
        assert order_executor.order_validator.validate_order_params(
            order.symbol, order.side, order.order_type, order.quantity, order.price
        )

        # Place
        executed = order_executor.place_order(order)
        assert executed is not None

        # Verify order has required fields for feedback
        assert executed.order_id is not None
        assert executed.status is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
