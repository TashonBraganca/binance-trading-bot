import time
import threading
from typing import Dict, Any, Optional

from src.client.binance_client import BinanceClient
from src.client.websocket_client import WebSocketClient
from src.orders.executor import OrderExecutor
from src.orders.validator import OrderValidator
from src.risk.manager import RiskManager
from src.risk.calculator import RiskCalculator
from src.portfolio.tracker import PortfolioTracker
from src.portfolio.analytics import PortfolioAnalytics
from src.strategies.twap import TWAPStrategy
from src.strategies.grid import GridStrategy
from src.strategies.oco import OCOStrategy
from src.strategies.trailing_stop import TrailingStopStrategy
from src.config.settings import settings
from src.config.constants import OrderSide, OrderType, PositionMode, MarginType
from src.utils.logger import main_logger, errors_logger, orders_logger, positions_logger

class TradingBot:
    def __init__(self):
        main_logger.info("Initializing TradingBot...")
        self.binance_client = BinanceClient()
        self.order_validator = OrderValidator(self.binance_client)
        self.order_executor = OrderExecutor(self.binance_client, self.order_validator)
        self.risk_calculator = RiskCalculator()
        self.risk_manager = RiskManager(self.binance_client, self.risk_calculator)
        self.portfolio_tracker = PortfolioTracker(self.binance_client)
        self.portfolio_analytics = PortfolioAnalytics()

        # Initialize strategies
        self.twap_strategy = TWAPStrategy(self.binance_client, self.order_executor, self.risk_manager, self.portfolio_tracker)
        self.grid_strategy = GridStrategy(self.binance_client, self.order_executor, self.risk_manager, self.portfolio_tracker)
        self.oco_strategy = OCOStrategy(self.binance_client, self.order_executor, self.risk_manager, self.portfolio_tracker)
        self.trailing_stop_strategy = TrailingStopStrategy(self.binance_client, self.order_executor, self.risk_manager, self.portfolio_tracker)

        self.strategies = {
            "TWAP": self.twap_strategy,
            "GRID": self.grid_strategy,
            "OCO": self.oco_strategy,
            "TRAILING_STOP": self.trailing_stop_strategy,
        }

        self.websocket_client: Optional[WebSocketClient] = None
        self.is_running = False
        self.market_data: Dict[str, Any] = {}

        # CRITICAL: Track strategy threads for graceful shutdown
        self.strategy_threads: Dict[str, threading.Thread] = {}

        self._setup_initial_account_settings()

    def _setup_initial_account_settings(self):
        """Sets up initial account settings like position mode and leverage."""
        try:
            # Set position mode to One-way (if not already)
            # Binance Futures API for setting position mode is not directly available in python-binance client
            # It's usually done via the UI or a specific endpoint not covered by simple client methods.
            # For this exercise, we'll assume it's set to one-way or handle it if an API method becomes available.
            # self.binance_client.change_position_mode(PositionMode.ONE_WAY) # Example if method existed
            main_logger.info("Assuming One-way position mode is set manually or by default.")

            # Set default leverage for a symbol (example: BTCUSDT)
            # This should ideally be done per symbol when a position is opened or strategy starts
            # For now, we'll just log a reminder.
            main_logger.info("Leverage and Margin Type should be set per symbol as needed.")

        except Exception as e:
            errors_logger.error(f"Error setting up initial account settings: {e}")

    def _market_data_handler(self, msg: Dict[str, Any]):
        """Handles incoming WebSocket market data."""
        event_type = msg.get("e")
        symbol = msg.get("s")

        if event_type == "markPriceUpdate" and symbol:
            self.market_data[symbol] = {"markPrice": float(msg["p"])}
            # main_logger.debug(f"Mark Price Update for {symbol}: {self.market_data[symbol]["markPrice"]}")
        elif event_type == "kline" and symbol:
            kline = msg["k"]
            self.market_data[symbol] = {"closePrice": float(kline["c"])}
            # main_logger.debug(f"Kline Close Price for {symbol}: {self.market_data[symbol]["closePrice"]}")
        # Add more handlers for other stream types (depth, trades, etc.)

    def start_websocket(self, streams: Dict[str, Any]):
        """Starts the WebSocket client with specified streams."""
        if self.websocket_client and self.websocket_client.is_running:
            main_logger.warning("WebSocket client is already running.")
            return
        
        # Add the market data handler to all streams
        streams_with_handler = {stream_name: self._market_data_handler for stream_name in streams}
        self.websocket_client = WebSocketClient(streams_with_handler)
        self.websocket_client.start()

    def stop_websocket(self):
        """Stops the WebSocket client."""
        if self.websocket_client:
            self.websocket_client.stop()

    def run_bot(self):
        """Main loop for the trading bot to run periodic tasks."""
        self.is_running = True
        main_logger.info("TradingBot started.")

        # CRITICAL: Start all active strategies and track their threads for graceful shutdown
        for strategy_name, strategy_instance in self.strategies.items():
            if strategy_instance.is_active:
                # Create non-daemon threads so we can join them on shutdown
                t = threading.Thread(
                    target=strategy_instance.run,
                    daemon=False,  # Non-daemon so we can wait for completion
                    name=f"strategy_{strategy_name}"
                )
                t.start()
                self.strategy_threads[strategy_name] = t
                main_logger.info(f"Started {strategy_name} strategy thread (ID: {t.ident})")

        while self.is_running:
            try:
                self.portfolio_tracker.update_account_balances()
                self.portfolio_tracker.update_open_positions()
                self.risk_manager.check_daily_loss_limit()  # This will update daily_pnl_start_balance if new day

                # Example: Update PnL for analytics
                total_equity = self.portfolio_tracker.get_total_equity()
                if total_equity > 0:
                    self.portfolio_analytics.update_daily_pnl(time.time(), total_equity)  # Using timestamp as date for simplicity

                # Cancel stale orders periodically
                # For all symbols in open positions or tracked by strategies
                tracked_symbols = set(self.portfolio_tracker.open_positions.keys())
                for strategy in self.strategies.values():
                    if hasattr(strategy, 'active_grids'):  # For GridStrategy
                        for grid_id in strategy.active_grids:
                            tracked_symbols.add(strategy.active_grids[grid_id]['symbol'])
                    # Add other strategy-specific symbol tracking if needed

                for symbol in tracked_symbols:
                    self.order_executor.cancel_stale_orders(symbol)

            except Exception as e:
                errors_logger.error(f"Error in main bot loop: {e}")

            time.sleep(5)  # Run periodic tasks every 5 seconds

    def stop_bot(self):
        """Stops the trading bot and all active components.

        CRITICAL: Graceful shutdown sequence:
        1. Signal all strategies to stop (is_running = False)
        2. Wait for strategy threads to complete (with timeout)
        3. Stop WebSocket connections
        4. Clean up resources
        """
        main_logger.info("Stopping TradingBot...")
        self.is_running = False

        # Signal all strategies to stop
        for strategy_instance in self.strategies.values():
            strategy_instance.stop()

        # CRITICAL: Wait for strategy threads to finish (with timeout)
        thread_timeout = 5.0  # Max 5 seconds per thread
        for strategy_name, thread in self.strategy_threads.items():
            if thread and thread.is_alive():
                main_logger.info(f"Waiting for {strategy_name} strategy thread to finish (timeout: {thread_timeout}s)...")
                thread.join(timeout=thread_timeout)
                if thread.is_alive():
                    errors_logger.warning(
                        f"Strategy thread '{strategy_name}' did not finish within {thread_timeout}s. "
                        f"It will be forcefully terminated with the process."
                    )

        # Stop WebSocket connection
        self.stop_websocket()

        main_logger.info("TradingBot stopped gracefully.")

    def get_current_market_price(self, symbol: str) -> float:
        """Retrieves the latest market price from the WebSocket data."""
        return self.market_data.get(symbol, {}).get("markPrice", 0.0) or \
               self.market_data.get(symbol, {}).get("closePrice", 0.0)

    def test_connection(self):
        """Tests the Binance API connection and prints account balance."""
        try:
            server_time = self.binance_client.get_server_time()
            main_logger.info(f"✓ Binance API connection successful. Server Time: {server_time}")
            
            account_info = self.binance_client.get_account_information()
            usdt_balance = next((a['walletBalance'] for a in account_info['assets'] if a['asset'] == 'USDT'), "N/A")
            main_logger.info(f"✓ Account balance: {usdt_balance} USDT")
            main_logger.info(f"✓ Testnet mode: {'ACTIVE' if settings.TESTNET else 'INACTIVE'}")
            return True
        except Exception as e:
            errors_logger.critical(f"✗ Binance API connection failed: {e}")
            return False