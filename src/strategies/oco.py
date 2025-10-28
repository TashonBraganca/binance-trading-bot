
import asyncio
from decimal import Decimal
from src.strategies.base import BaseStrategy
from src.utils.logger import app_log, orders_log, errors_log
from src.config.constants import OrderSide, PositionSide, OrderType, TimeInForce

class OCOStrategy(BaseStrategy):
    """
    Simulates an OCO (One-Cancels-Other) order by placing two separate orders
    (a stop-loss and a take-profit) and monitoring them. When one is filled,
    the other is automatically cancelled.
    
    This is a bot-managed implementation, not a native exchange OCO order.
    """

    def __init__(self, bot):
        super().__init__(bot, "OCO")

    async def run(self, symbol: str, quantity: Decimal, profit_price: Decimal, stop_price: Decimal, side: PositionSide):
        """
        Places the OCO orders and starts monitoring.

        :param symbol: The trading symbol.
        :param quantity: The quantity for the orders.
        :param profit_price: The take-profit price.
        :param stop_price: The stop-loss price.
        :param side: The position side (LONG or SHORT).
        """
        app_log.info(f"Initiating OCO order for {side.value} {quantity} {symbol}. TP: {profit_price}, SL: {stop_price}")

        order_side = OrderSide.SELL if side == PositionSide.LONG else OrderSide.BUY

        # 1. Place Take-Profit Order (Limit Order)
        tp_order_id = await self._place_order(
            symbol=symbol, 
            side=order_side, 
            order_type=OrderType.TAKE_PROFIT_LIMIT, 
            quantity=quantity, 
            price=profit_price,
            stop_price=profit_price, # For TAKE_PROFIT_LIMIT, price and stopPrice are often the same
            time_in_force=TimeInForce.GTC
        )

        # 2. Place Stop-Loss Order (Stop Market Order)
        sl_order_id = await self._place_order(
            symbol=symbol, 
            side=order_side, 
            order_type=OrderType.STOP_MARKET, 
            quantity=quantity, 
            stop_price=stop_price
        )

        if not (tp_order_id and sl_order_id):
            errors_log.error("Failed to place one or both OCO orders. Cancelling any that were placed.")
            if tp_order_id: await self.bot.order_executor.cancel_order(symbol, tp_order_id)
            if sl_order_id: await self.bot.order_executor.cancel_order(symbol, sl_order_id)
            return

        app_log.info(f"OCO orders placed. TP Order ID: {tp_order_id}, SL Order ID: {sl_order_id}. Monitoring..." )

        # 3. Monitor the orders
        await self._monitor_oco(symbol, tp_order_id, sl_order_id)

    async def _place_order(self, **kwargs) -> int | None:
        """Helper to place an order and return its ID."""
        # Must convert enums to string values for the API call
        api_kwargs = {k: v.value if isinstance(v, (OrderSide, OrderType, TimeInForce)) else v for k, v in kwargs.items()}
        
        try:
            order = await self.bot.client.place_order(**api_kwargs)
            orders_log.info(f"Placed OCO component order: {order}")
            return order['orderId']
        except Exception as e:
            errors_log.error(f"Failed to place OCO component order with params {kwargs}: {e}")
            return None

    async def _monitor_oco(self, symbol: str, tp_order_id: int, sl_order_id: int):
        """
        Continuously checks the status of the two OCO orders.
        """
        while True:
            try:
                tp_status = await self.bot.client.get_order(symbol, tp_order_id)
                sl_status = await self.bot.client.get_order(symbol, sl_order_id)

                if tp_status['status'] == 'FILLED':
                    app_log.info(f"Take-Profit order {tp_order_id} filled. Cancelling Stop-Loss order {sl_order_id}.")
                    await self.bot.order_executor.cancel_order(symbol, sl_order_id)
                    break
                
                if sl_status['status'] == 'FILLED':
                    app_log.info(f"Stop-Loss order {sl_order_id} filled. Cancelling Take-Profit order {tp_order_id}.")
                    await self.bot.order_executor.cancel_order(symbol, tp_order_id)
                    break

                # If one gets cancelled manually, cancel the other
                if tp_status['status'] in ['CANCELED', 'EXPIRED']:
                    app_log.info(f"Take-Profit order {tp_order_id} is {tp_status['status']}. Cancelling counterpart {sl_order_id}.")
                    await self.bot.order_executor.cancel_order(symbol, sl_order_id)
                    break
                
                if sl_status['status'] in ['CANCELED', 'EXPIRED']:
                    app_log.info(f"Stop-Loss order {sl_order_id} is {sl_status['status']}. Cancelling counterpart {tp_order_id}.")
                    await self.bot.order_executor.cancel_order(symbol, tp_order_id)
                    break

            except Exception as e:
                errors_log.error(f"Error monitoring OCO orders ({tp_order_id}, {sl_order_id}): {e}")
                # Decide on a retry strategy or break
                break
            
            await asyncio.sleep(5) # Check every 5 seconds
