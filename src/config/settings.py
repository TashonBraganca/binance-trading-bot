
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    """
    Application-wide settings loaded from environment variables.
    """
    # Binance API Credentials
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

    # Trading Mode
    # Set to "True" for testnet, "False" for mainnet
    TESTNET = os.getenv("TESTNET", "True").lower() in ("true", "1", "t")

    # Binance API URLs
    BASE_URL_MAINNET = "https://fapi.binance.com"
    BASE_URL_TESTNET = "https://testnet.binancefuture.com"
    
    WEBSOCKET_URL_MAINNET = "wss://fstream.binance.com"
    WEBSOCKET_URL_TESTNET = "wss://stream.binancefuture.com"

    @property
    def base_url(self):
        return self.BASE_URL_TESTNET if self.TESTNET else self.BASE_URL_MAINNET

    @property
    def websocket_url(self):
        return self.WEBSOCKET_URL_TESTNET if self.TESTNET else self.WEBSOCKET_URL_MAINNET

    # Logging Configuration
    LOGS_DIR = "logs"
    APP_LOG_FILE = os.path.join(LOGS_DIR, "trading_bot.log")
    ORDERS_LOG_FILE = os.path.join(LOGS_DIR, "orders.log")
    POSITIONS_LOG_FILE = os.path.join(LOGS_DIR, "positions.log")
    ERRORS_LOG_FILE = os.path.join(LOGS_DIR, "errors.log")
    API_REQUESTS_LOG_FILE = os.path.join(LOGS_DIR, "api_requests.log")
    PERFORMANCE_LOG_FILE = os.path.join(LOGS_DIR, "performance.log")
    LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    LOG_ROTATION_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
    LOG_ROTATION_BACKUP_COUNT = 5

    # Rate Limiting
    # Binance Futures API rate limits: 2400 requests per minute
    # We'll be conservative and aim for a bit less
    REQUEST_LIMIT_PER_MINUTE = 2000

    # Other constants
    ORDER_CANCEL_TIMEOUT_MINUTES = 60  # Cancel orders older than 60 minutes
    RETRY_ATTEMPTS = 3
    RETRY_DELAY_SECONDS = 2  # Initial delay for exponential backoff

settings = Settings()
