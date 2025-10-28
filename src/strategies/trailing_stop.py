
import asyncio
from decimal import Decimal
from src.strategies.base import BaseStrategy
from src.utils.logger import app_log, orders_log, errors_log
from src.config.constants import OrderSide, PositionSide

class TrailingStopStrategy(BaseStrategy):
    """
    Manages a client-side trailing stop-loss. This strategy monitors the price
    of an open position and triggers a market sell/buy if the price retraces
    by a specified percentage from its peak.
    """

    def __init__(self, bot):
        super().__init__(bot, "Trailing Stop")

    async def run(self, symbol: str, callback_rate: float, quantity: Decimal, side: PositionSide):
        """
        Starts monitoring a position for a trailing stop.

        :param symbol: The symbol of the position to trail.
        :param callback_rate: The percentage of retracement that triggers the stop (e.g., 0.02 for 2%).
        :param quantity: The quantity of the position to close.
        :param side: The side of the position (LONG or SHORT).
        """
        app_log.info(f"Starting Trailing Stop for {side.value} {quantity} {symbol} with a {callback_rate:.2%} callback rate.")

        # Get the initial entry price from the position
        position = self.bot.portfolio_tracker.get_position(symbol)
        if not position:
            app_log.warning(f"No open position found for {symbol}. Cannot start trailing stop.")
            return

        trailing_price = Decimal(position['entryPrice'])
        stop_price = self._calculate_stop_price(trailing_price, callback_rate, side)

        app_log.info(f"Initial trailing price: {trailing_price:.4f}. Initial stop price: {stop_price:.4f}")

        while True:
            try:
                current_price = await self.bot.risk_manager._fetch_current_price(symbol)
                if not current_price:
                    await asyncio.sleep(10) # Wait before retrying price fetch
                    continue

                if side == PositionSide.LONG:
                    # If price moves up, update the trailing price to the new high
                    if current_price > trailing_price:
                        trailing_price = current_price
                        stop_price = self._calculate_stop_price(trailing_price, callback_rate, side)
                        app_log.debug(f"New high for {symbol}: {trailing_price:.4f}. Trailing stop adjusted to {stop_price:.4f}")
                    
                    # If price drops to or below the stop price, trigger the stop-loss
                    if current_price <= stop_price:
                        app_log.info(f"Trailing stop triggered for LONG {symbol} at {current_price:.4f} (Stop price: {stop_price:.4f}).")
                        await self._execute_stop_order(symbol, quantity, OrderSide.SELL)
                        break

                elif side == PositionSide.SHORT:
                    # If price moves down, update the trailing price to the new low
                    if current_price < trailing_price:
                        trailing_price = current_price
                        stop_price = self._calculate_stop_price(trailing_price, callback_rate, side)
                        app_log.debug(f"New low for {symbol}: {trailing_price:.4f}. Trailing stop adjusted to {stop_price:.4f}")

                    # If price rises to or above the stop price, trigger the stop-loss
                    if current_price >= stop_price:
                        app_log.info(f"Trailing stop triggered for SHORT {symbol} at {current_price:.4f} (Stop price: {stop_price:.4f}).")
                        await self._execute_stop_order(symbol, quantity, OrderSide.BUY)
                        break
                
                # Check if position still exists
                if not self.bot.portfolio_tracker.get_position(symbol):
                    app_log.info(f"Position for {symbol} seems to be closed. Stopping trailing stop monitor.")
                    break

            except Exception as e:
                errors_log.error(f"Error in trailing stop monitor for {symbol}: {e}")
                break

            await asyncio.sleep(3) # Check price every 3 seconds

    def _calculate_stop_price(self, price: Decimal, rate: float, side: PositionSide) -> Decimal:
        """Calculates the stop price based on the trailing price and callback rate."""
        if side == PositionSide.LONG:
            return price * (Decimal(1) - Decimal(rate))
        else: # SHORT
            return price * (Decimal(1) + Decimal(rate))

    async def _execute_stop_order(self, symbol: str, quantity: Decimal, side: OrderSide):
        """Executes a market order to close the position."""
        try:
            order_data = {
                "symbol": symbol,
                "side": side.value,
                "type": "MARKET",
                "quantity": float(quantity),
            }
            result = await self.bot.order_executor.execute_order(order_data)
            if result and result.get('status') == 'FILLED':
                orders_log.info(f"Trailing stop market order for {symbol} filled.")
            else:
                orders_log.warning(f"Trailing stop market order for {symbol} failed or status unknown: {result}")
        except Exception as e:
            errors_log.error(f"Failed to execute trailing stop order for {symbol}: {e}")
