from abc import ABC, abstractmethod
from typing import Dict, Any
import time

from src.client.binance_client import BinanceClient
from src.orders.executor import OrderExecutor
from src.risk.manager import RiskManager
from src.portfolio.tracker import PortfolioTracker
from src.utils.logger import main_logger

class BaseStrategy(ABC):
    def __init__(self, binance_client: BinanceClient, order_executor: OrderExecutor, risk_manager: RiskManager, portfolio_tracker: PortfolioTracker):
        self.binance_client = binance_client
        self.order_executor = order_executor
        self.risk_manager = risk_manager
        self.portfolio_tracker = portfolio_tracker
        self.is_active = False
        # OPTIMIZATION: Cache prices to reduce API calls
        self._price_cache: Dict[str, Dict[str, Any]] = {}  # {symbol: {"price": float, "timestamp": float}}
        self._price_cache_ttl = 0.5  # Cache prices for 0.5 seconds
        main_logger.info(f"Strategy {self.__class__.__name__} initialized.")

    @abstractmethod
    def run(self):
        """Main method to run the strategy logic."""
        pass

    def start(self):
        """Activates the strategy."""
        self.is_active = True
        main_logger.info(f"Strategy {self.__class__.__name__} started.")

    def stop(self):
        """Deactivates the strategy."""
        self.is_active = False
        main_logger.info(f"Strategy {self.__class__.__name__} stopped.")

    def get_current_price(self, symbol: str) -> float:
        """Helper to get the current mark price for a symbol with caching."""
        current_time = time.time()

        # Check cache first
        if symbol in self._price_cache:
            cached_data = self._price_cache[symbol]
            if current_time - cached_data["timestamp"] < self._price_cache_ttl:
                # Cache hit - return cached price
                return cached_data["price"]

        # Cache miss or expired - fetch fresh price
        try:
            mark_price_data = self.binance_client.get_mark_price(symbol)
            price = 0.0

            if isinstance(mark_price_data, list):
                for item in mark_price_data:
                    if item['symbol'] == symbol:
                        price = float(item['markPrice'])
                        break
            else:
                price = float(mark_price_data['markPrice'])

            # Cache the price
            if price > 0:
                self._price_cache[symbol] = {"price": price, "timestamp": current_time}

            return price
        except Exception as e:
            main_logger.error(f"Could not get mark price for {symbol}: {e}")
            return 0.0