"""
Position Monitor - Monitors open positions and executes stop-loss/take-profit
Automatically closes positions when price targets are hit
"""
import time
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass

from src.client.binance_client import BinanceClient
from src.orders.executor import OrderExecutor
from src.orders.types import Order, OrderSide, OrderType
from src.portfolio.tracker import PortfolioTracker
from src.utils.logger import main_logger, errors_logger


@dataclass
class StopLossConfig:
    """Stop Loss Configuration"""
    enabled: bool = True
    percent: float = 2.0  # 2% below entry
    absolute_price: Optional[float] = None  # Or use absolute price


@dataclass
class TakeProfitConfig:
    """Take Profit Configuration"""
    enabled: bool = True
    percent: float = 5.0  # 5% above entry
    absolute_price: Optional[float] = None  # Or use absolute price


class PositionMonitor:
    """Monitors open positions and executes stop-loss/take-profit orders."""

    def __init__(self, binance_client: BinanceClient, order_executor: OrderExecutor,
                 portfolio_tracker: PortfolioTracker):
        self.binance_client = binance_client
        self.order_executor = order_executor
        self.portfolio_tracker = portfolio_tracker

        self.is_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.check_interval = 5  # Check every 5 seconds

        # Price cache for efficiency
        self._price_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 10  # 10 seconds

        # Triggered orders tracking
        self.triggered_stops: set = set()  # Track triggered stop losses
        self.triggered_takes: set = set()  # Track triggered take profits

    def get_current_price(self, symbol: str) -> float:
        """Get cached price or fetch fresh one."""
        current_time = time.time()

        # Check cache
        if symbol in self._price_cache:
            cached = self._price_cache[symbol]
            if current_time - cached["timestamp"] < self._cache_ttl:
                return cached["price"]

        # Fetch fresh price
        try:
            ticker = self.binance_client.get_ticker_24hr(symbol)
            price = float(ticker.get("lastPrice", 0.0))

            # Cache it
            if price > 0:
                self._price_cache[symbol] = {"price": price, "timestamp": current_time}

            return price
        except Exception as e:
            errors_logger.warning(f"Could not fetch price for {symbol}: {e}")
            return 0.0

    def check_stop_loss(self, position: Dict[str, Any], current_price: float) -> bool:
        """Check if position should be stopped out."""
        symbol = position.get("symbol", "")
        entry_price = float(position.get("entry_price", 0.0))
        side = position.get("side", "BUY")
        stop_loss = float(position.get("stop_loss", 0.0))

        if stop_loss == 0:
            return False

        # BUY: stop loss is below entry
        if side == "BUY" and current_price <= stop_loss:
            return True

        # SELL: stop loss is above entry
        if side == "SELL" and current_price >= stop_loss:
            return True

        return False

    def check_take_profit(self, position: Dict[str, Any], current_price: float) -> bool:
        """Check if position should be taken profit."""
        symbol = position.get("symbol", "")
        entry_price = float(position.get("entry_price", 0.0))
        side = position.get("side", "BUY")
        take_profit = float(position.get("take_profit", 0.0))

        if take_profit == 0:
            return False

        # BUY: take profit is above entry
        if side == "BUY" and current_price >= take_profit:
            return True

        # SELL: take profit is below entry
        if side == "SELL" and current_price <= take_profit:
            return True

        return False

    def close_position(self, position: Dict[str, Any], reason: str) -> bool:
        """Close a position with market order."""
        try:
            symbol = position.get("symbol", "")
            quantity = float(position.get("quantity", 0.0))
            side = position.get("side", "BUY")

            # Close position with opposite side
            close_side = OrderSide.SELL if side == "BUY" else OrderSide.BUY

            close_order = Order(
                symbol=symbol,
                side=close_side,
                order_type=OrderType.MARKET,
                quantity=quantity,
                client_order_id=f"CLOSE_{symbol}_{reason}_{int(time.time() * 1000)}"
            )

            executed = self.order_executor.place_order(close_order)

            if executed:
                main_logger.info(f"Position closed for {symbol}: {reason} "
                               f"(Price target hit at {self.get_current_price(symbol):.2f})")
                return True
            else:
                errors_logger.error(f"Failed to close position for {symbol}: {reason}")
                return False

        except Exception as e:
            errors_logger.error(f"Error closing position: {e}")
            return False

    def monitor_positions(self) -> None:
        """Monitor all open positions and execute stops/takes."""
        while self.is_active:
            try:
                positions = self.portfolio_tracker.get_open_positions_list()

                for pos in positions:
                    symbol = pos.get("symbol", "")
                    position_id = f"{symbol}_{pos.get('entry_price')}_{pos.get('timestamp', '')}"

                    current_price = self.get_current_price(symbol)

                    if current_price == 0:
                        continue

                    # Check stop loss
                    if (position_id not in self.triggered_stops and
                        self.check_stop_loss(pos, current_price)):

                        main_logger.warning(f"STOP LOSS triggered for {symbol} at ${current_price:.2f}")
                        if self.close_position(pos, "STOP_LOSS"):
                            self.triggered_stops.add(position_id)

                    # Check take profit
                    if (position_id not in self.triggered_takes and
                        self.check_take_profit(pos, current_price)):

                        main_logger.info(f"TAKE PROFIT triggered for {symbol} at ${current_price:.2f}")
                        if self.close_position(pos, "TAKE_PROFIT"):
                            self.triggered_takes.add(position_id)

                time.sleep(self.check_interval)

            except Exception as e:
                errors_logger.error(f"Error in position monitor: {e}")
                time.sleep(self.check_interval)

    def start(self) -> None:
        """Start monitoring positions."""
        if self.is_active:
            main_logger.warning("Position monitor already active")
            return

        self.is_active = True
        self.monitor_thread = threading.Thread(target=self.monitor_positions, daemon=True)
        self.monitor_thread.start()
        main_logger.info("Position monitor started")

    def stop(self) -> None:
        """Stop monitoring positions."""
        self.is_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        main_logger.info("Position monitor stopped")

    def set_stop_loss(self, symbol: str, entry_price: float, stop_loss_price: float) -> None:
        """Set stop loss for a position."""
        positions = self.portfolio_tracker.get_open_positions_list()

        for pos in positions:
            if pos.get("symbol") == symbol and float(pos.get("entry_price", 0)) == entry_price:
                pos["stop_loss"] = stop_loss_price
                main_logger.info(f"Stop loss set for {symbol}: ${stop_loss_price:.2f}")
                return

        main_logger.warning(f"Position not found for {symbol} at ${entry_price:.2f}")

    def set_take_profit(self, symbol: str, entry_price: float, take_profit_price: float) -> None:
        """Set take profit for a position."""
        positions = self.portfolio_tracker.get_open_positions_list()

        for pos in positions:
            if pos.get("symbol") == symbol and float(pos.get("entry_price", 0)) == entry_price:
                pos["take_profit"] = take_profit_price
                main_logger.info(f"Take profit set for {symbol}: ${take_profit_price:.2f}")
                return

        main_logger.warning(f"Position not found for {symbol} at ${entry_price:.2f}")

    def set_auto_sl_tp(self, symbol: str, entry_price: float,
                      sl_percent: float = 2.0, tp_percent: float = 5.0) -> None:
        """Automatically set stop loss and take profit based on percentages."""
        positions = self.portfolio_tracker.get_open_positions_list()

        for pos in positions:
            if pos.get("symbol") == symbol and float(pos.get("entry_price", 0)) == entry_price:
                side = pos.get("side", "BUY")

                if side == "BUY":
                    stop_loss = entry_price * (1 - sl_percent / 100)
                    take_profit = entry_price * (1 + tp_percent / 100)
                else:  # SELL
                    stop_loss = entry_price * (1 + sl_percent / 100)
                    take_profit = entry_price * (1 - tp_percent / 100)

                pos["stop_loss"] = stop_loss
                pos["take_profit"] = take_profit

                main_logger.info(f"Auto SL/TP set for {symbol}: "
                               f"SL=${stop_loss:.2f}, TP=${take_profit:.2f}")
                return

        main_logger.warning(f"Position not found for {symbol} at ${entry_price:.2f}")

    def get_position_status(self, symbol: str) -> Dict[str, Any]:
        """Get detailed status of a position."""
        positions = self.portfolio_tracker.get_open_positions_list()

        for pos in positions:
            if pos.get("symbol") == symbol:
                current_price = self.get_current_price(symbol)
                entry_price = float(pos.get("entry_price", 0.0))
                stop_loss = float(pos.get("stop_loss", 0.0))
                take_profit = float(pos.get("take_profit", 0.0))
                side = pos.get("side", "BUY")

                # Calculate distances
                if side == "BUY":
                    sl_distance = current_price - stop_loss if stop_loss > 0 else 0
                    tp_distance = take_profit - current_price if take_profit > 0 else 0
                else:
                    sl_distance = stop_loss - current_price if stop_loss > 0 else 0
                    tp_distance = current_price - take_profit if take_profit > 0 else 0

                return {
                    "symbol": symbol,
                    "current_price": current_price,
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "distance_to_sl": sl_distance,
                    "distance_to_tp": tp_distance,
                    "side": side
                }

        return {}
