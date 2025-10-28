
import asyncio
from decimal import Decimal
from src.client.binance_client import BinanceClient
from src.orders.validator import OrderValidator
from src.utils.logger import app_log, orders_log, errors_log
from src.config.constants import OrderStatus

class OrderExecutor:
    """
    Handles all order placement with pre-execution validation, retry logic,
    and post-execution verification.
    """

    def __init__(self, client: BinanceClient, risk_manager):
        self.client = client
        self.validator = OrderValidator(client, risk_manager)
        self.risk_manager = risk_manager

    async def execute_order(self, order_data: dict, is_retry=False) -> dict:
        """
        Validates and places an order on the exchange.
        Includes logic for retries and handling partial fills.
        """
        try:
            # On retries, we might want to skip some checks or re-evaluate the situation
            if not is_retry:
                orders_log.info(f"Initiating new order: {order_data}")
                is_valid = await self.validator.validate_order(order_data)
                if not is_valid:
                    orders_log.warning(f"Order validation failed. Aborting: {order_data}")
                    return {"status": "REJECTED", "error": "Validation failed"}

            # Adjust quantity precision based on exchange info
            order_data['quantity'] = self._format_quantity(order_data['symbol'], order_data['quantity'])

            placed_order = await self.client.place_order(**order_data)
            orders_log.info(f"Order placed successfully: {placed_order}")

            # Post-execution verification
            verification_result = await self._verify_execution(placed_order)
            return verification_result

        except Exception as e:
            errors_log.error(f"Order execution failed for {order_data}: {e}")
            # Here you could implement more sophisticated retry logic
            # For now, we just log the error
            return {"status": "FAILED", "error": str(e)}

    def _format_quantity(self, symbol: str, quantity: Decimal) -> Decimal:
        """Formats the quantity to the correct precision for the symbol."""
        symbol_info = self.validator._get_symbol_filters(symbol)
        if 'LOT_SIZE' in symbol_info:
            step_size = Decimal(symbol_info['LOT_SIZE']['stepSize'])
            precision = -step_size.as_tuple().exponent
            return round(quantity, precision)
        return quantity

    async def _verify_execution(self, order: dict) -> dict:
        """
        Verifies the order status after placement and handles partial fills.
        """
        await asyncio.sleep(0.5) # Give the exchange a moment to process
        try:
            order_status = await self.client.get_order(symbol=order['symbol'], orderId=order['orderId'])
            orders_log.info(f"Post-execution verification for OrderID {order['orderId']}: Status is {order_status['status']}")

            if order_status['status'] == OrderStatus.PARTIALLY_FILLED.value:
                orders_log.warning(f"Order {order['orderId']} is partially filled. Filled: {order_status['executedQty']}/{order_status['origQty']}")
                # Further logic can be added here to monitor the rest of the fill

            elif order_status['status'] == OrderStatus.FILLED.value:
                fill_price = Decimal(order_status['avgPrice'])
                original_price = Decimal(order.get('price', fill_price))
                slippage = ((fill_price - original_price) / original_price) * 100
                orders_log.info(f"Order {order['orderId']} filled at avg price {fill_price:.4f}. Slippage: {slippage:.4f}%")

            return order_status
        except Exception as e:
            errors_log.error(f"Failed to verify order {order['orderId']}: {e}")
            return {"status": "VERIFICATION_FAILED", "error": str(e)}

    async def cancel_stale_orders(self):
        """Cancels all open orders that are older than a configured timeout."""
        # Implementation for this would require tracking order placement time
        # and is left as an extension.
        app_log.info("Scanning for stale orders... (Not yet implemented)")
        pass

    async def cancel_order(self, symbol: str, order_id: int):
        """Cancels a specific order by its ID."""
        try:
            result = await self.client.cancel_order(symbol=symbol, orderId=order_id)
            orders_log.info(f"Cancellation request for order {order_id} successful: {result}")
            return result
        except Exception as e:
            errors_log.error(f"Failed to cancel order {order_id}: {e}")
            return None
