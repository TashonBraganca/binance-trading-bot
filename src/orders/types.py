
from dataclasses import dataclass
from decimal import Decimal
from src.config.constants import OrderSide, OrderType, PositionSide

@dataclass
class BaseOrder:
    symbol: str
    side: OrderSide
    quantity: Decimal

@dataclass
class MarketOrder(BaseOrder):
    order_type: OrderType = OrderType.MARKET

@dataclass
class LimitOrder(BaseOrder):
    price: Decimal
    order_type: OrderType = OrderType.LIMIT

@dataclass
class StopLossOrder:
    symbol: str
    side: OrderSide
    stop_price: Decimal
    quantity: Decimal
    order_type: OrderType = OrderType.STOP_MARKET

@dataclass
class TakeProfitOrder:
    symbol: str
    side: OrderSide
    stop_price: Decimal
    quantity: Decimal
    order_type: OrderType = OrderType.TAKE_PROFIT_MARKET

@dataclass
class OCOOrder:
    """One-Cancels-the-Other Order. Not a native Binance order type, 
       so it will be managed by the bot logic."""
    symbol: str
    side: OrderSide
    quantity: Decimal
    profit_price: Decimal
    stop_price: Decimal
    position_side: PositionSide

@dataclass
class TrailingStopOrder:
    symbol: str
    side: OrderSide
    quantity: Decimal
    activation_price: Decimal
    callback_rate: Decimal
    order_type: OrderType = OrderType.TRAILING_STOP_MARKET
