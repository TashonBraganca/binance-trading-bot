import time
import threading
from typing import Dict, Any, Optional

from src.client.binance_client import BinanceClient
from src.orders.types import Order, OrderType, OrderSide, TimeInForce
from src.orders.validator import OrderValidator
from src.config.constants import RETRY_ATTEMPTS, RETRY_DELAY_SECONDS, ORDER_STALE_MINUTES
from src.utils.logger import orders_logger, errors_logger, main_logger

class OrderExecutor:
    def __init__(self, binance_client: BinanceClient, order_validator: OrderValidator):
        self.binance_client = binance_client
        self.order_validator = order_validator
        self._order_placement_lock = threading.RLock()  # Serialize order placement to prevent margin conflicts

    def place_order(self, order: Order) -> Optional[Order]:
        """Places an order with pre-execution validation and retry logic.

        CRITICAL: Order placement is serialized using a lock to prevent:
        - Race conditions where multiple threads check balance simultaneously
        - Margin violations from concurrent orders
        - Check-then-act anti-patterns
        """
        with self._order_placement_lock:
            # ATOMIC BLOCK: Balance check + order placement must be atomic
            if not self.order_validator.validate_order_params(
                order.symbol, order.side, order.order_type, order.quantity, order.price
            ):
                main_logger.warning(f"Order validation failed for {order.symbol} {order.order_type} {order.side} {order.quantity}")
                return None

            # Balance check must be atomic with placement to prevent overselling margin
            if not self.order_validator.validate_sufficient_balance(
                order.symbol, order.side, order.order_type, order.quantity, order.price
            ):
                main_logger.warning(f"Insufficient balance for order {order.symbol} {order.order_type} {order.side} {order.quantity}")
                return None

            for attempt in range(RETRY_ATTEMPTS):
                try:
                    orders_logger.info(f"Attempt {attempt + 1}: Placing {order.order_type} order for {order.quantity} {order.symbol} at {order.price if order.price else 'market'}")

                    # Construct params for Binance API
                    params = {
                        "symbol": order.symbol,
                        "side": order.side.value,
                        "type": order.order_type.value,
                        "quantity": order.quantity,
                    }
                    if order.price: params["price"] = order.price
                    if order.time_in_force: params["timeInForce"] = order.time_in_force.value
                    if order.stop_price: params["stopPrice"] = order.stop_price
                    if order.client_order_id: params["newClientOrderId"] = order.client_order_id
                    if order.reduce_only: params["reduceOnly"] = order.reduce_only
                    if order.close_position: params["closePosition"] = order.close_position
                    if order.activation_price: params["activationPrice"] = order.activation_price
                    if order.callback_rate: params["callbackRate"] = order.callback_rate
                    if order.working_type: params["workingType"] = order.working_type
                    if order.position_side: params["positionSide"] = order.position_side

                    response = self.binance_client.place_order(**params)
                    order.order_id = response.get("orderId")
                    order.client_order_id = response.get("clientOrderId")
                    order.status = response.get("status")
                    order.filled_quantity = float(response.get("executedQty", 0.0))
                    order.avg_fill_price = float(response.get("avgPrice", 0.0))
                    order.raw_response = response
                    orders_logger.info(f"Order placed successfully: {order.symbol} {order.side.value} {order.order_type.value} ID: {order.order_id} Status: {order.status}")
                    return order
                except Exception as e:
                    errors_logger.error(f"Error placing order (attempt {attempt + 1}/{RETRY_ATTEMPTS}): {e}")
                    if attempt < RETRY_ATTEMPTS - 1:
                        time.sleep(RETRY_DELAY_SECONDS * (2 ** attempt))  # Exponential backoff

            errors_logger.critical(f"Failed to place order after {RETRY_ATTEMPTS} attempts: {order.symbol} {order.side.value} {order.quantity}")
            return None

    def cancel_order(self, symbol: str, order_id: Optional[int] = None, client_order_id: Optional[str] = None) -> bool:
        """Cancels an order by orderId or clientOrderId."""
        try:
            response = self.binance_client.cancel_order(symbol=symbol, order_id=order_id, orig_client_order_id=client_order_id)
            orders_logger.info(f"Order cancelled successfully: {symbol} ID: {order_id if order_id else client_order_id}")
            return True
        except Exception as e:
            errors_logger.error(f"Error cancelling order {symbol} ID: {order_id if order_id else client_order_id}: {e}")
            return False

    def cancel_stale_orders(self, symbol: str) -> int:
        """Cancels all open orders for a symbol that are older than ORDER_STALE_MINUTES."""
        try:
            open_orders = self.binance_client.get_open_orders(symbol)
            cancelled_count = 0
            current_time_ms = int(time.time() * 1000)
            for order_data in open_orders:
                order_time_ms = order_data.get("time", 0)
                if (current_time_ms - order_time_ms) > (ORDER_STALE_MINUTES * 60 * 1000):
                    if self.cancel_order(symbol=symbol, order_id=order_data["orderId"]):
                        cancelled_count += 1
                        orders_logger.info(f"Cancelled stale order: {symbol} ID: {order_data['orderId']}")
            if cancelled_count > 0:
                main_logger.info(f"Cancelled {cancelled_count} stale orders for {symbol}.")
            return cancelled_count
        except Exception as e:
            errors_logger.error(f"Error cancelling stale orders for {symbol}: {e}")
            return 0

    def get_order_status(self, symbol: str, order_id: Optional[int] = None, client_order_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieves the status of an order."""
        try:
            # Binance API does not have a direct get_order_status for futures
            # We need to fetch all orders and filter or fetch open orders
            if order_id or client_order_id:
                all_orders = self.binance_client.get_all_orders(symbol)
                for order_data in all_orders:
                    if (order_id and order_data.get("orderId") == order_id) or \
                       (client_order_id and order_data.get("clientOrderId") == client_order_id):
                        return order_data
            return None
        except Exception as e:
            errors_logger.error(f"Error getting order status for {symbol} ID: {order_id if order_id else client_order_id}: {e}")
            return None

    def verify_order_fill(self, order: Order, timeout: int = 30) -> bool:
        """Verifies if an order has been filled within a timeout period."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.get_order_status(order.symbol, order.order_id, order.client_order_id)
            if status and status.get("status") == "FILLED":
                order.status = "FILLED"
                order.filled_quantity = float(status.get("executedQty", 0.0))
                order.avg_fill_price = float(status.get("avgPrice", 0.0))
                orders_logger.info(f"Order {order.order_id} for {order.symbol} fully FILLED at avg price {order.avg_fill_price}")
                return True
            elif status and status.get("status") in ["CANCELED", "EXPIRED", "REJECTED"]:
                order.status = status.get("status")
                orders_logger.warning(f"Order {order.order_id} for {order.symbol} was {order.status}")
                return False
            time.sleep(1) # Check every second
        orders_logger.warning(f"Order {order.order_id} for {order.symbol} not filled within {timeout} seconds. Current status: {order.status}")
        order.status = "EXPIRED" # Set status to EXPIRED on timeout
        return False