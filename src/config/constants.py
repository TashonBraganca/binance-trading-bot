
from enum import Enum

class OrderType(Enum):
    LIMIT = 'LIMIT'
    MARKET = 'MARKET'
    STOP_MARKET = 'STOP_MARKET'
    STOP_LIMIT = 'STOP_LIMIT'
    TAKE_PROFIT_MARKET = 'TAKE_PROFIT_MARKET'
    TAKE_PROFIT_LIMIT = 'TAKE_PROFIT_LIMIT'
    TRAILING_STOP_MARKET = 'TRAILING_STOP_MARKET'

class OrderSide(Enum):
    BUY = 'BUY'
    SELL = 'SELL'

class PositionSide(Enum):
    LONG = 'LONG'
    SHORT = 'SHORT'
    BOTH = 'BOTH'

class MarginType(Enum):
    ISOLATED = 'ISOLATED'
    CROSSED = 'CROSSED'

class TimeInForce(Enum):
    GTC = 'GTC'  # Good 'Til Canceled
    IOC = 'IOC'  # Immediate or Cancel
    FOK = 'FOK'  # Fill or Kill
    GTX = 'GTX'  # Good 'Til Crossing (Post Only)

class ContractType(Enum):
    PERPETUAL = 'PERPETUAL'
    CURRENT_MONTH = 'CURRENT_MONTH'
    NEXT_MONTH = 'NEXT_MONTH'
    CURRENT_QUARTER = 'CURRENT_QUARTER'
    NEXT_QUARTER = 'NEXT_QUARTER'

class OrderStatus(Enum):
    NEW = 'NEW'
    PARTIALLY_FILLED = 'PARTIALLY_FILLED'
    FILLED = 'FILLED'
    CANCELED = 'CANCELED'
    REJECTED = 'REJECTED'
    EXPIRED = 'EXPIRED'
