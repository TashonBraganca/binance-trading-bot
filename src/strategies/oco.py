import time
from typing import Optional

from src.strategies.base import BaseStrategy
from src.orders.types import Order, OCOOrder, OrderSide, OrderType, TimeInForce
from src.utils.logger import main_logger, orders_logger, errors_logger

class OCOStrategy(BaseStrategy):
    def __init__(self, binance_client, order_executor, risk_manager, portfolio_tracker):
        super().__init__(binance_client, order_executor, risk_manager, portfolio_tracker)
        self.strategy_name = "OCO"

    def place_oco_order(self, symbol: str, side: OrderSide, quantity: float, 
                        price: float, stop_price: float, take_profit_price: float,
                        leverage: int = 1) -> Optional[OCOOrder]:
        """
        Places an OCO (One-Cancels-Other) order.
        This involves placing a limit order, a stop-market order, and a take-profit-market order.
        Binance Futures API does not have a native OCO order type like spot.
        We simulate it by placing a limit order and then two conditional orders (stop-market, take-profit-market)
        that are linked to the position opened by the limit order.
        
        For simplicity in this implementation, we will place a LIMIT order, and then
        a STOP_MARKET and TAKE_PROFIT_MARKET order with CLOSE_POSITION=True.
        These will act as OCO for the position opened by the LIMIT order.
        """
        if not self.is_active:
            main_logger.warning(f"{self.strategy_name} strategy is not active. Start it first.")
            return None

        main_logger.info(f"Placing OCO order for {symbol} {side.value} {quantity} at {price} with SL: {stop_price}, TP: {take_profit_price}")

        # 1. Place the main LIMIT order
        limit_order = Order(
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=price,
            time_in_force=TimeInForce.GTC,
            client_order_id=f"OCO_LIMIT_{symbol}_{int(time.time())}"
        )
        current_price = self.get_current_price(symbol)
        if not self.risk_manager.pre_trade_check(limit_order, current_price, leverage, self.portfolio_tracker.get_open_positions_list()):
            main_logger.warning(f"OCO LIMIT order for {symbol} rejected by risk manager.")
            return None

        executed_limit_order = self.order_executor.place_order(limit_order)
        # Check if order was successfully placed (may not be FILLED immediately for limit orders)
        # Orders can be in NEW, PARTIALLY_FILLED, or FILLED status - all are acceptable as long as they weren't rejected
        if not executed_limit_order or executed_limit_order.status in ["REJECTED", "CANCELED", "EXPIRED"]:
            errors_logger.error(f"Failed to place main LIMIT order for OCO: {symbol}. Status: {executed_limit_order.status if executed_limit_order else 'None'}")
            return None

        main_logger.info(f"OCO LIMIT order placed successfully for {symbol}. Status: {executed_limit_order.status}")

        # 2. Place the STOP_MARKET order (Stop Loss)
        stop_loss_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
        stop_loss_order = Order(
            symbol=symbol,
            side=stop_loss_side,
            order_type=OrderType.STOP_MARKET,
            quantity=quantity,
            stop_price=stop_price,
            close_position=True, # Important for futures to close existing position
            client_order_id=f"OCO_SL_{symbol}_{int(time.time())}"
        )
        # Risk check for SL/TP orders is usually done on the main order
        executed_sl_order = self.order_executor.place_order(stop_loss_order)
        if not executed_sl_order:
            errors_logger.error(f"Failed to place STOP_MARKET order for OCO: {symbol}. Attempting to cancel main order.")
            self.order_executor.cancel_order(symbol, order_id=executed_limit_order.order_id)
            return None

        # 3. Place the TAKE_PROFIT_MARKET order
        take_profit_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
        take_profit_order = Order(
            symbol=symbol,
            side=take_profit_side,
            order_type=OrderType.TAKE_PROFIT_MARKET,
            quantity=quantity,
            stop_price=take_profit_price, # For take profit market, stopPrice is the trigger
            close_position=True, # Important for futures to close existing position
            client_order_id=f"OCO_TP_{symbol}_{int(time.time())}"
        )
        executed_tp_order = self.order_executor.place_order(take_profit_order)
        if not executed_tp_order:
            errors_logger.error(f"Failed to place TAKE_PROFIT_MARKET order for OCO: {symbol}. Attempting to cancel main order and SL.")
            self.order_executor.cancel_order(symbol, order_id=executed_limit_order.order_id)
            self.order_executor.cancel_order(symbol, order_id=executed_sl_order.order_id)
            return None

        oco_order = OCOOrder(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            take_profit_price=take_profit_price,
            orders=[executed_limit_order, executed_sl_order, executed_tp_order],
            status="ACTIVE"
        )
        main_logger.info(f"OCO order for {symbol} placed successfully. Limit ID: {executed_limit_order.order_id}, SL ID: {executed_sl_order.order_id}, TP ID: {executed_tp_order.order_id}")
        return oco_order

    def run(self):
        """OCO strategy is executed via the `place_oco_order` method, not a continuous run loop."""
        main_logger.warning("OCO strategy does not have a continuous run loop. Use .place_oco_order() method.")