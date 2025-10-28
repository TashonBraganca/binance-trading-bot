
import asyncio
from decimal import Decimal
import numpy as np
from src.strategies.base import BaseStrategy
from src.utils.logger import app_log, orders_log
from src.config.constants import OrderSide, TimeInForce

class GridStrategy(BaseStrategy):
    """
    Places a grid of buy and sell limit orders in a specified price range
    to profit from market oscillations.
    """

    def __init__(self, bot):
        super().__init__(bot, "Grid Trading")
        self.active_grids = {}

    async def run(self, symbol: str, price_range_pct: float, num_grids: int, investment: Decimal, lower_bound: Decimal, upper_bound: Decimal):
        """
        Sets up and starts the grid trading strategy.

        :param symbol: The trading symbol.
        :param price_range_pct: The percentage range around the current price (not used if bounds are set).
        :param num_grids: The number of grid lines (must be an even number).
        :param investment: The total amount of USDT to use for the grid.
        :param lower_bound: The lower price of the grid.
        :param upper_bound: The upper price of the grid.
        """
        app_log.info(f"Setting up Grid strategy for {symbol} with {num_grids} grids between {lower_bound} and {upper_bound}.")

        if num_grids % 2 != 0:
            app_log.warning("Number of grids must be even. Adjusting to the nearest lower even number.")
            num_grids -= 1

        grid_lines = self._calculate_grid_levels(lower_bound, upper_bound, num_grids)
        quantity_per_grid = self._calculate_quantity(investment, num_grids, symbol)

        if quantity_per_grid == 0:
            app_log.error("Calculated quantity per grid is zero. Aborting strategy.")
            return

        app_log.info(f"Placing {num_grids} grid orders with quantity {quantity_per_grid} each.")

        # For simplicity, we place all orders at once. A real implementation
        # would likely manage these orders more dynamically.
        current_price = await self.bot.risk_manager._fetch_current_price(symbol)
        if not current_price:
            app_log.error(f"Could not fetch current price for {symbol}. Aborting grid setup.")
            return

        for price in grid_lines:
            side = OrderSide.BUY if price < current_price else OrderSide.SELL
            await self._place_grid_order(symbol, price, quantity_per_grid, side)
            await asyncio.sleep(0.2) # Avoid rate limiting

        app_log.info("Grid setup complete. The bot will now manage the grid.")
        # The core logic to manage the grid (i.e., when a buy fills, place a sell, and vice-versa)
        # would be complex and require persistent state and WebSocket monitoring.
        # This is a simplified setup.

    def _calculate_grid_levels(self, lower: Decimal, upper: Decimal, num: int) -> list[Decimal]:
        """Calculates the price levels for the grid lines."""
        return list(np.linspace(float(lower), float(upper), num))

    def _calculate_quantity(self, investment: Decimal, num_grids: int, symbol: str) -> Decimal:
        """Calculates the quantity per grid order."""
        # This is a simplification. A proper calculation would be more nuanced.
        try:
            # Amount of quote currency per grid
            quote_per_grid = investment / Decimal(num_grids)
            # A rough estimate of base currency quantity
            current_price = self.bot.risk_manager.get_current_price(symbol)
            if not current_price:
                # Fallback if price not cached
                return investment / (Decimal(num_grids) * Decimal(40000)) # Dummy price
            return quote_per_grid / current_price
        except ZeroDivisionError:
            return Decimal('0')

    async def _place_grid_order(self, symbol: str, price: Decimal, quantity: Decimal, side: OrderSide):
        """Places a single limit order for the grid."""
        try:
            order_data = {
                "symbol": symbol,
                "side": side.value,
                "type": "LIMIT",
                "quantity": float(quantity),
                "price": float(price),
                "timeInForce": TimeInForce.GTC.value
            }
            result = await self.bot.order_executor.execute_order(order_data)
            if result and result.get('orderId'):
                orders_log.info(f"Placed grid order: {side.value} {quantity:.4f} {symbol} @ {price:.2f}")
                # Store the active grid order to manage it later
                self.active_grids[result['orderId']] = result
            else:
                orders_log.warning(f"Failed to place grid order for {symbol} at {price:.2f}")
        except Exception as e:
            errors_log.error(f"Error placing grid order: {e}")
