import time
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional

from src.strategies.base import BaseStrategy
from src.orders.types import Order, OrderSide, OrderType, TimeInForce
from src.utils.logger import main_logger, orders_logger, errors_logger

class GridStrategy(BaseStrategy):
    def __init__(self, binance_client, order_executor, risk_manager, portfolio_tracker):
        super().__init__(binance_client, order_executor, risk_manager, portfolio_tracker)
        self.strategy_name = "GRID"
        self.active_grids: Dict[str, Dict[str, Any]] = {}
        self._grid_lock = threading.RLock()  # Reentrant lock for thread-safe grid modifications

    def setup_grid(self, symbol: str, price_range_pct: float, num_grids: int, investment_per_grid: float, 
                   leverage: int = 1, grid_id: Optional[str] = None) -> Optional[str]:
        """
        Sets up a new grid trading strategy.
        :param symbol: Trading pair (e.g., BTCUSDT)
        :param price_range_pct: Total price range for the grid as a percentage (e.g., 0.05 for 5%)
        :param num_grids: Number of buy/sell grids
        :param investment_per_grid: Amount to invest per grid level (e.g., in USDT)
        :param leverage: Leverage to use for grid orders
        :param grid_id: Optional, unique ID for the grid. If None, one will be generated.
        :return: The generated grid_id if successful, None otherwise.
        """
        if not self.is_active:
            main_logger.warning(f"{self.strategy_name} strategy is not active. Start it first.")
            return None

        current_price = self.get_current_price(symbol)
        if current_price == 0.0:
            errors_logger.error(f"Could not get current price for {symbol}. Cannot set up grid.")
            return None

        if grid_id is None:
            grid_id = f"GRID_{symbol}_{int(time.time() * 1000)}"  # Higher precision to avoid collisions

        with self._grid_lock:
            if grid_id in self.active_grids:
                main_logger.warning(f"Grid with ID {grid_id} already exists. Please use a unique ID.")
                return None

        lower_bound = current_price * (1 - price_range_pct / 2)
        upper_bound = current_price * (1 + price_range_pct / 2)
        price_step = (upper_bound - lower_bound) / num_grids

        grid_levels = [lower_bound + i * price_step for i in range(num_grids + 1)]
        main_logger.info(f"Setting up {num_grids} grids for {symbol} from {lower_bound:.2f} to {upper_bound:.2f}")

        buy_orders = []
        sell_orders = []

        # Place initial buy orders below current price and sell orders above
        for i in range(num_grids):
            buy_price = grid_levels[i]
            sell_price = grid_levels[i+1]

            # Place buy order if price is below current price
            if buy_price < current_price:
                buy_order = Order(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType.LIMIT,
                    quantity=investment_per_grid / buy_price, # Convert investment to quantity
                    price=buy_price,
                    time_in_force=TimeInForce.GTC,
                    client_order_id=f"{grid_id}_BUY_{i}"
                )
                # Pre-trade risk check for buy order
                if self.risk_manager.pre_trade_check(buy_order, buy_price, leverage, self.portfolio_tracker.get_open_positions_list()):
                    executed_buy_order = self.order_executor.place_order(buy_order)
                    if executed_buy_order: buy_orders.append(executed_buy_order)
                else:
                    main_logger.warning(f"Grid BUY order {i} for {symbol} rejected by risk manager.")

            # Place sell order if price is above current price
            if sell_price > current_price:
                sell_order = Order(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.LIMIT,
                    quantity=investment_per_grid / sell_price, # Convert investment to quantity
                    price=sell_price,
                    time_in_force=TimeInForce.GTC,
                    client_order_id=f"{grid_id}_SELL_{i}"
                )
                # Pre-trade risk check for sell order (assuming we have position to sell)
                # This check is more complex for grid, as we might not have the position yet.
                # For simplicity, we'll assume risk manager handles potential future position.
                if self.risk_manager.pre_trade_check(sell_order, sell_price, leverage, self.portfolio_tracker.get_open_positions_list()):
                    executed_sell_order = self.order_executor.place_order(sell_order)
                    if executed_sell_order: sell_orders.append(executed_sell_order)
                else:
                    main_logger.warning(f"Grid SELL order {i} for {symbol} rejected by risk manager.")

        with self._grid_lock:
            self.active_grids[grid_id] = {
                "symbol": symbol,
                "lower_bound": lower_bound,
                "upper_bound": upper_bound,
                "num_grids": num_grids,
                "investment_per_grid": investment_per_grid,
                "leverage": leverage,
                "grid_levels": grid_levels,
                "buy_orders": buy_orders,
                "sell_orders": sell_orders,
                "created_at": datetime.utcnow()
            }
        main_logger.info(f"Grid strategy {grid_id} for {symbol} set up successfully.")
        return grid_id

    def monitor_grid(self, grid_id: str):
        """Monitors an active grid strategy and places new orders as old ones fill."""
        with self._grid_lock:
            if grid_id not in self.active_grids:
                errors_logger.error(f"Grid ID {grid_id} not found.")
                return

            grid_config = self.active_grids[grid_id]
            symbol = grid_config["symbol"]
            investment_per_grid = grid_config["investment_per_grid"]
            leverage = grid_config["leverage"]

            # Check all buy orders - iterate over copy to safely remove
            buy_orders_to_remove = []
            for order in list(grid_config["buy_orders"]):
                if order.status == "FILLED":
                    # If a buy order fills, place a corresponding sell order at the next grid level up
                    try:
                        grid_level_idx = self._find_closest_grid_level(order.price, grid_config["grid_levels"])
                        next_grid_level_index = grid_level_idx + 1
                        if next_grid_level_index < len(grid_config["grid_levels"]):
                            sell_price = grid_config["grid_levels"][next_grid_level_index]
                            sell_order = Order(
                                symbol=symbol,
                                side=OrderSide.SELL,
                                order_type=OrderType.LIMIT,
                                quantity=order.filled_quantity,
                                price=sell_price,
                                time_in_force=TimeInForce.GTC,
                                client_order_id=f"{grid_id}_SELL_REFILL_{int(time.time() * 1000)}"
                            )
                            if self.risk_manager.pre_trade_check(sell_order, sell_price, leverage, self.portfolio_tracker.get_open_positions_list()):
                                executed_sell_order = self.order_executor.place_order(sell_order)
                                if executed_sell_order:
                                    grid_config["sell_orders"].append(executed_sell_order)
                            else:
                                main_logger.warning(f"Grid REFILL SELL order for {symbol} rejected by risk manager.")
                        buy_orders_to_remove.append(order)
                    except Exception as e:
                        errors_logger.error(f"Error processing filled buy order in grid {grid_id}: {e}")
                        buy_orders_to_remove.append(order)

            # Safely remove filled orders
            for order in buy_orders_to_remove:
                try:
                    grid_config["buy_orders"].remove(order)
                except ValueError:
                    pass  # Order already removed

            # Check all sell orders - iterate over copy to safely remove
            sell_orders_to_remove = []
            for order in list(grid_config["sell_orders"]):
                if order.status == "FILLED":
                    # If a sell order fills, place a corresponding buy order at the next grid level down
                    try:
                        grid_level_idx = self._find_closest_grid_level(order.price, grid_config["grid_levels"])
                        if grid_level_idx > 0:
                            buy_price = grid_config["grid_levels"][grid_level_idx - 1]
                            buy_order = Order(
                                symbol=symbol,
                                side=OrderSide.BUY,
                                order_type=OrderType.LIMIT,
                                quantity=order.filled_quantity,
                                price=buy_price,
                                time_in_force=TimeInForce.GTC,
                                client_order_id=f"{grid_id}_BUY_REFILL_{int(time.time() * 1000)}"
                            )
                            if self.risk_manager.pre_trade_check(buy_order, buy_price, leverage, self.portfolio_tracker.get_open_positions_list()):
                                executed_buy_order = self.order_executor.place_order(buy_order)
                                if executed_buy_order:
                                    grid_config["buy_orders"].append(executed_buy_order)
                            else:
                                main_logger.warning(f"Grid REFILL BUY order for {symbol} rejected by risk manager.")
                        sell_orders_to_remove.append(order)
                    except Exception as e:
                        errors_logger.error(f"Error processing filled sell order in grid {grid_id}: {e}")
                        sell_orders_to_remove.append(order)

            # Safely remove filled orders
            for order in sell_orders_to_remove:
                try:
                    grid_config["sell_orders"].remove(order)
                except ValueError:
                    pass  # Order already removed

            # Update order statuses for active orders in the grid
            all_grid_orders = grid_config["buy_orders"] + grid_config["sell_orders"]
            for order in all_grid_orders:
                if order.status not in ["FILLED", "CANCELED", "EXPIRED", "REJECTED"]:
                    status_data = self.order_executor.get_order_status(order.symbol, order.order_id, order.client_order_id)
                    if status_data:
                        order.status = status_data.get("status", order.status)
                        order.filled_quantity = float(status_data.get("executedQty", order.filled_quantity))
                        order.avg_fill_price = float(status_data.get("avgPrice", order.avg_fill_price))

    def _find_closest_grid_level(self, price: float, grid_levels: List[float]) -> int:
        """Find the index of the closest grid level to the given price, handling floating point precision."""
        if not grid_levels:
            raise ValueError("Grid levels cannot be empty")

        # Try exact match first (with small tolerance for floating point)
        tolerance = 1e-8
        for idx, level in enumerate(grid_levels):
            if abs(level - price) < tolerance:
                return idx

        # If no exact match, find closest
        closest_idx = min(range(len(grid_levels)), key=lambda i: abs(grid_levels[i] - price))
        return closest_idx

    def cancel_grid(self, grid_id: str) -> bool:
        """Cancels all open orders associated with a grid strategy and removes it."""
        with self._grid_lock:
            if grid_id not in self.active_grids:
                errors_logger.error(f"Grid ID {grid_id} not found for cancellation.")
                return False

            grid_config = self.active_grids[grid_id]
            symbol = grid_config["symbol"]

            all_grid_orders = grid_config["buy_orders"] + grid_config["sell_orders"]
            for order in all_grid_orders:
                if order.status not in ["FILLED", "CANCELED", "EXPIRED", "REJECTED"]:
                    self.order_executor.cancel_order(symbol, order_id=order.order_id, client_order_id=order.client_order_id)

            del self.active_grids[grid_id]
            main_logger.info(f"Grid strategy {grid_id} for {symbol} cancelled and removed.")
            return True

    def run(self):
        """Continuously monitors all active grid strategies."""
        while self.is_active:
            if not self.active_grids:
                main_logger.debug("No active grids to monitor. Sleeping...")
                time.sleep(5) # Sleep if no grids are active
                continue

            for grid_id in list(self.active_grids.keys()): # Iterate over a copy to allow modification
                try:
                    self.monitor_grid(grid_id)
                except Exception as e:
                    errors_logger.error(f"Error monitoring grid {grid_id}: {e}")
            time.sleep(1) # Monitor every second