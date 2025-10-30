import time
from datetime import datetime
from typing import Optional, Dict, Any

from src.strategies.base import BaseStrategy
from src.orders.types import Order, OrderSide, OrderType
from src.utils.logger import main_logger, orders_logger, errors_logger

class TrailingStopStrategy(BaseStrategy):
    def __init__(self, binance_client, order_executor, risk_manager, portfolio_tracker):
        super().__init__(binance_client, order_executor, risk_manager, portfolio_tracker)
        self.strategy_name = "TRAILING_STOP"
        self.active_trailing_stops: Dict[str, Dict[str, Any]] = {}

    def start_trailing_stop(self, symbol: str, callback_rate: float, leverage: int = 1) -> Optional[str]:
        """
        Starts monitoring a position for a trailing stop.
        :param symbol: Trading pair (e.g., BTCUSDT)
        :param callback_rate: The percentage by which the price must move unfavorably to trigger the stop (e.g., 0.01 for 1%)
        :param leverage: Leverage to use for the closing order
        :return: The trailing stop ID if successful, None otherwise.
        """
        if not self.is_active:
            main_logger.warning(f"{self.strategy_name} strategy is not active. Start it first.")
            return None

        position = self.portfolio_tracker.get_position(symbol)
        if not position or position.position_amt == 0:
            errors_logger.error(f"No open position found for {symbol} to apply a trailing stop.")
            return None

        trailing_stop_id = f"TS_{symbol}_{int(time.time())}"

        current_price = self.get_current_price(symbol)
        if current_price == 0.0:
            errors_logger.error(f"Could not get current price for {symbol}. Cannot start trailing stop.")
            return None

        if position.position_amt > 0: # Long position
            highest_price = current_price
            stop_price = current_price * (1 - callback_rate)
            side = OrderSide.SELL
        else: # Short position
            lowest_price = current_price
            stop_price = current_price * (1 + callback_rate)
            side = OrderSide.BUY

        self.active_trailing_stops[trailing_stop_id] = {
            "symbol": symbol,
            "position_amt": position.position_amt,
            "side": side,
            "callback_rate": callback_rate,
            "leverage": leverage,
            "highest_price": highest_price if position.position_amt > 0 else None,
            "lowest_price": lowest_price if position.position_amt < 0 else None,
            "current_stop_price": stop_price,
            "status": "ACTIVE",
            "created_at": datetime.utcnow()
        }
        main_logger.info(f"Trailing stop {trailing_stop_id} started for {symbol}. Initial stop price: {stop_price:.2f}")
        return trailing_stop_id

    def monitor_trailing_stop(self, trailing_stop_id: str):
        """
        Monitors an active trailing stop and adjusts the stop price or executes the order.
        """
        if trailing_stop_id not in self.active_trailing_stops:
            errors_logger.error(f"Trailing stop ID {trailing_stop_id} not found.")
            return

        ts_config = self.active_trailing_stops[trailing_stop_id]
        symbol = ts_config["symbol"]
        side = ts_config["side"]
        callback_rate = ts_config["callback_rate"]
        leverage = ts_config["leverage"]
        position_amt = ts_config["position_amt"]

        current_price = self.get_current_price(symbol)
        if current_price == 0.0:
            errors_logger.error(f"Could not get current price for {symbol}. Skipping trailing stop monitor.")
            return

        if position_amt > 0: # Long position
            if current_price > ts_config["highest_price"]:
                ts_config["highest_price"] = current_price
                new_stop_price = current_price * (1 - callback_rate)
                if new_stop_price > ts_config["current_stop_price"]:
                    ts_config["current_stop_price"] = new_stop_price
                    main_logger.info(f"Trailing stop {trailing_stop_id} for {symbol} adjusted. New stop price: {new_stop_price:.2f}")
            elif current_price <= ts_config['current_stop_price']:
                main_logger.info(f"Trailing stop {trailing_stop_id} for {symbol} triggered! Current price: {current_price:.2f}, Stop price: {ts_config['current_stop_price']:.2f}")
                self._execute_trailing_stop_order(symbol, side, abs(position_amt), leverage)
                self.stop_trailing_stop(trailing_stop_id)

        else: # Short position
            if current_price < ts_config["lowest_price"]:
                ts_config["lowest_price"] = current_price
                new_stop_price = current_price * (1 + callback_rate)
                if new_stop_price < ts_config["current_stop_price"]:
                    ts_config["current_stop_price"] = new_stop_price
                    main_logger.info(f"Trailing stop {trailing_stop_id} for {symbol} adjusted. New stop price: {new_stop_price:.2f}")
            elif current_price >= ts_config['current_stop_price']:
                main_logger.info(f"Trailing stop {trailing_stop_id} for {symbol} triggered! Current price: {current_price:.2f}, Stop price: {ts_config['current_stop_price']:.2f}")
                self._execute_trailing_stop_order(symbol, side, abs(position_amt), leverage)
                self.stop_trailing_stop(trailing_stop_id)

    def _execute_trailing_stop_order(self, symbol: str, side: OrderSide, quantity: float, leverage: int):
        """Executes the market order to close the position when trailing stop is triggered."""
        order = Order(
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            close_position=True, # Close the position
            client_order_id=f"TS_EXEC_{symbol}_{int(time.time())}"
        )
        # Risk check is implicitly handled by the initial position opening
        executed_order = self.order_executor.place_order(order)
        if executed_order and executed_order.status == "FILLED":
            orders_logger.info(f"Trailing stop market order for {symbol} executed. Qty: {executed_order.filled_quantity}, Avg Price: {executed_order.avg_fill_price}")
        else:
            errors_logger.error(f"Failed to execute trailing stop market order for {symbol}.")

    def stop_trailing_stop(self, trailing_stop_id: str):
        """Stops monitoring a specific trailing stop."""
        if trailing_stop_id in self.active_trailing_stops:
            del self.active_trailing_stops[trailing_stop_id]
            main_logger.info(f"Trailing stop {trailing_stop_id} stopped.")

    def run(self):
        """Continuously monitors all active trailing stops."""
        while self.is_active:
            if not self.active_trailing_stops:
                main_logger.debug("No active trailing stops to monitor. Sleeping...")
                time.sleep(5) # Sleep if no trailing stops are active
                continue

            for ts_id in list(self.active_trailing_stops.keys()): # Iterate over a copy to allow modification
                try:
                    self.monitor_trailing_stop(ts_id)
                except Exception as e:
                    errors_logger.error(f"Error monitoring trailing stop {ts_id}: {e}")
            time.sleep(1) # Monitor every second