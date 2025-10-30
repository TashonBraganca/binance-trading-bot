from enum import Enum

# Binance API Endpoints
BINANCE_FUTURES_TESTNET_URL = "https://testnet.binancefuture.com"
BINANCE_FUTURES_TESTNET_WEBSOCKET_URL = "wss://stream.binancefuture.com/ws"

# Order Sides
class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

# Order Types
class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    STOP_LIMIT = "STOP_LIMIT"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"
    OCO = "OCO"  # One-Cancels-Other
    TWAP = "TWAP"  # Time-Weighted Average Price
    GRID = "GRID"  # Grid Trading
    TRAILING_STOP_MARKET = "TRAILING_STOP_MARKET"

# Time In Force
class TimeInForce(str, Enum):
    GTC = "GTC"  # Good Till Cancelled
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill

# Position Modes
class PositionMode(str, Enum):
    BOTH_SIDE = "BOTH_SIDE"
    ONE_WAY = "ONE_WAY"

# Margin Types
class MarginType(str, Enum):
    ISOLATED = "ISOLATED"
    CROSSED = "CROSSED"

# Intervals for Kline/Candlestick Data
class KlineInterval(str, Enum):
    _1M = "1m"
    _3M = "3m"
    _5M = "5m"
    _15M = "15m"
    _30M = "30m"
    _1H = "1h"
    _2H = "2h"
    _4H = "4h"
    _6H = "6h"
    _8H = "8h"
    _12H = "12h"
    _1D = "1d"
    _3D = "3d"
    _1W = "1w"
    _1MONTH = "1M"

# Default Risk Management Settings
DEFAULT_MAX_POSITION_SIZE_PCT = 0.10  # 10% of account per position
DEFAULT_MAX_LEVERAGE = 10             # 10x leverage
DEFAULT_MAX_DAILY_LOSS_PCT = 0.05     # 5% daily loss limit
DEFAULT_MAX_OPEN_POSITIONS = 5        # Max 5 concurrent positions

# Other Constants
RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 1
MAX_RATE_LIMIT_RETRIES = 5
RATE_LIMIT_WAIT_SECONDS = 5 # Initial wait for rate limit
ORDER_STALE_MINUTES = 10 # Orders older than this are considered stale