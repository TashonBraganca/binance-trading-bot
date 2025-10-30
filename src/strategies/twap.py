import time
import math
from typing import Optional

from src.strategies.base import BaseStrategy
from src.orders.types import Order, OrderSide, OrderType, TimeInForce
from src.utils.logger import main_logger, orders_logger, errors_logger

class TWAPStrategy(BaseStrategy):
    def __init__(self, binance_client, order_executor, risk_manager, portfolio_tracker):
        super().__init__(binance_client, order_executor, risk_manager, portfolio_tracker)
        self.strategy_name = "TWAP"

    def execute(self, symbol: str, total_quantity: float, duration_minutes: int, side: OrderSide, 
                interval_seconds: int = 60, leverage: int = 1) -> bool:
        """
        Executes a TWAP order.
        :param symbol: Trading pair (e.g., BTCUSDT)
        :param total_quantity: Total quantity to trade
        :param duration_minutes: Total duration over which to execute the order in minutes
        :param side: BUY or SELL
        :param interval_seconds: Interval between child orders in seconds (default: 60s)
        :param leverage: Leverage to use for the order
        :return: True if strategy initiated successfully, False otherwise
        """
        if not self.is_active:
            main_logger.warning(f"{self.strategy_name} strategy is not active. Start it first.")
            return False

        if duration_minutes <= 0 or total_quantity <= 0 or interval_seconds <= 0:
            errors_logger.error("Invalid TWAP parameters: duration, quantity, or interval must be positive.")
            return False

        num_orders = math.ceil((duration_minutes * 60) / interval_seconds)
        if num_orders == 0: # Handle case where duration is less than interval
            num_orders = 1
        
        quantity_per_order = total_quantity / num_orders

        main_logger.info(f"Initiating TWAP for {symbol}: Total {total_quantity} {side.value} over {duration_minutes} mins in {num_orders} orders of {quantity_per_order:.4f} every {interval_seconds}s")

        start_time = time.time()
        for i in range(num_orders):
            if not self.is_active:
                main_logger.info(f"{self.strategy_name} strategy stopped during execution.")
                return False

            current_price = self.get_current_price(symbol)
            if current_price == 0.0:
                errors_logger.error(f"Could not get current price for {symbol}. Skipping TWAP child order.")
                time.sleep(interval_seconds)
                continue

            # Pre-trade risk check
            temp_order = Order(symbol=symbol, side=side, order_type=OrderType.MARKET, quantity=quantity_per_order)
            if not self.risk_manager.pre_trade_check(temp_order, current_price, leverage, self.portfolio_tracker.get_open_positions_list()):
                main_logger.warning(f"TWAP child order {i+1}/{num_orders} for {symbol} rejected by risk manager.")
                # Depending on policy, could stop TWAP or just skip this order
                time.sleep(interval_seconds)
                continue

            order = Order(
                symbol=symbol,
                side=side,
                order_type=OrderType.MARKET, # TWAP typically uses market orders
                quantity=quantity_per_order,
                client_order_id=f"TWAP_{symbol}_{int(time.time())}_{i}"
            )
            executed_order = self.order_executor.place_order(order)

            if executed_order and executed_order.status == "FILLED":
                orders_logger.info(f"TWAP child order {i+1}/{num_orders} for {symbol} executed. Qty: {executed_order.filled_quantity}, Avg Price: {executed_order.avg_fill_price}")
            else:
                errors_logger.error(f"TWAP child order {i+1}/{num_orders} for {symbol} failed or not filled.")
            
            if i < num_orders - 1:
                time_to_wait = interval_seconds - (time.time() - start_time) % interval_seconds
                if time_to_wait > 0:
                    time.sleep(time_to_wait)

        main_logger.info(f"TWAP strategy for {symbol} completed.")
        return True

    def run(self):
        """TWAP strategy is executed via the `execute` method, not a continuous run loop."""
        main_logger.warning("TWAP strategy does not have a continuous run loop. Use .execute() method.")