
import asyncio
from decimal import Decimal
from src.strategies.base import BaseStrategy
from src.utils.logger import app_log, orders_log
from src.config.constants import OrderSide

class TWAPStrategy(BaseStrategy):
    """
    Splits a large order into smaller chunks executed over a specified time period
    to minimize market impact.
    """

    def __init__(self, bot):
        super().__init__(bot, "TWAP")

    async def run(self, symbol: str, total_quantity: Decimal, duration_minutes: int, side: OrderSide):
        """
        Executes the TWAP strategy.

        :param symbol: The trading symbol (e.g., 'BTCUSDT').
        :param total_quantity: The total amount of the asset to buy or sell.
        :param duration_minutes: The total duration over which to execute the order.
        :param side: The order side (OrderSide.BUY or OrderSide.SELL).
        """
        app_log.info(f"Starting TWAP strategy for {side.value} {total_quantity} {symbol} over {duration_minutes} minutes.")

        # For simplicity, we'll use a fixed number of chunks. A more advanced
        # implementation could make this dynamic.
        num_chunks = 10
        if duration_minutes < 1:
            num_chunks = 1 # Execute in a single order if duration is very short
        
        chunk_quantity = total_quantity / Decimal(num_chunks)
        interval_seconds = (duration_minutes * 60) / num_chunks

        app_log.info(f"TWAP plan: {num_chunks} chunks of {chunk_quantity:.4f} {symbol} every {interval_seconds:.2f} seconds.")

        executed_quantity = Decimal('0')
        for i in range(num_chunks):
            try:
                order_data = {
                    "symbol": symbol,
                    "side": side.value,
                    "type": "MARKET",
                    "quantity": float(chunk_quantity), # python-binance requires float for quantity
                }
                
                order_result = await self.bot.order_executor.execute_order(order_data)
                
                if order_result and order_result.get('status') in ['FILLED', 'PARTIALLY_FILLED']:
                    filled_qty = Decimal(order_result.get('executedQty', '0'))
                    executed_quantity += filled_qty
                    orders_log.info(f"TWAP chunk {i+1}/{num_chunks} filled for {filled_qty} {symbol}. Total filled: {executed_quantity}")
                else:
                    orders_log.warning(f"TWAP chunk {i+1}/{num_chunks} failed or was not filled: {order_result}")

            except Exception as e:
                orders_log.error(f"Error executing TWAP chunk {i+1}/{num_chunks}: {e}")

            if i < num_chunks - 1: # Don't wait after the last chunk
                await asyncio.sleep(interval_seconds)
        
        app_log.info(f"TWAP strategy finished. Total executed quantity: {executed_quantity}/{total_quantity}")
        # Here you could add reporting on execution quality vs. benchmark (e.g., VWAP)
