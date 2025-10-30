from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from src.config.constants import OrderSide, OrderType, TimeInForce

@dataclass
class Order:
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    time_in_force: Optional[TimeInForce] = None
    stop_price: Optional[float] = None
    client_order_id: Optional[str] = None
    reduce_only: Optional[bool] = False
    new_client_order_id: Optional[str] = None
    stop_limit_price: Optional[float] = None
    activation_price: Optional[float] = None # Used for TRAILING_STOP_MARKET
    callback_rate: Optional[float] = None # Used for TRAILING_STOP_MARKET
    working_type: Optional[str] = None # Used for conditional orders
    position_side: Optional[str] = None # LONG, SHORT, BOTH
    close_position: Optional[bool] = False
    # Additional fields for tracking
    order_id: Optional[int] = None
    status: Optional[str] = None
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    raw_response: Dict[str, Any] = field(default_factory=dict)

@dataclass
class OCOOrder:
    symbol: str
    side: OrderSide
    quantity: float
    price: float  # Limit price for the main order
    stop_price: float  # Stop price for the stop-loss order
    take_profit_price: float  # Limit price for the take-profit order
    stop_limit_price: Optional[float] = None # Optional stop-limit price
    client_order_id: Optional[str] = None
    stop_client_order_id: Optional[str] = None
    limit_client_order_id: Optional[str] = None
    list_client_order_id: Optional[str] = None
    status: Optional[str] = None
    orders: list[Order] = field(default_factory=list)
    raw_response: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Position:
    symbol: str
    entry_price: float
    mark_price: float
    position_amt: float
    unrealized_pnl: float
    leverage: int
    margin_type: str
    position_side: str # LONG, SHORT, BOTH
    isolated_wallet: Optional[float] = None
    update_time: datetime = field(default_factory=datetime.utcnow)

@dataclass
class AccountBalance:
    asset: str
    wallet_balance: float
    cross_wallet_balance: float
    cross_unrealized_pnl: float
    available_balance: float
    update_time: datetime = field(default_factory=datetime.utcnow)