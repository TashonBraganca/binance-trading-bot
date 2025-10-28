
import asyncio
import time
from binance import AsyncClient
from binance.exceptions import BinanceAPIException, BinanceRequestException
from src.config.settings import settings
from src.utils.logger import app_log, api_log, errors_log

class BinanceClient:
    """A wrapper for the python-binance library to handle API interactions."""

    def __init__(self):
        self.api_key = settings.BINANCE_API_KEY
        self.api_secret = settings.BINANCE_API_SECRET
        self.testnet = settings.TESTNET
        self.client = None

    async def initialize(self):
        """Initializes the asynchronous client."""
        app_log.info("Initializing Binance client...")
        try:
            self.client = await AsyncClient.create(
                self.api_key, 
                self.api_secret, 
                testnet=self.testnet
            )
            # Sync server time
            await self.client.get_server_time()
            app_log.info("Binance client initialized and server time synced.")
            return True
        except (BinanceAPIException, BinanceRequestException) as e:
            errors_log.critical(f"Failed to initialize Binance client: {e}")
            app_log.critical("API credentials may be invalid or network issues present. Exiting.")
            return False
        except Exception as e:
            errors_log.critical(f"An unexpected error occurred during client initialization: {e}")
            return False

    async def close(self):
        """Closes the client connection."""
        if self.client:
            await self.client.close_connection()
            app_log.info("Binance client connection closed.")

    async def _execute_request(self, method, *args, **kwargs):
        """Executes a request with retry logic and error handling."""
        for attempt in range(settings.RETRY_ATTEMPTS):
            try:
                api_log.debug(f"Executing: {method.__name__} with args: {args} and kwargs: {kwargs}")
                return await method(*args, **kwargs)
            except BinanceAPIException as e:
                errors_log.error(f"API Error on attempt {attempt + 1}: {e}")
                if e.code == -1021: # Timestamp for this request is outside of the recvWindow
                    app_log.warning("Timestamp error. Resyncing time with server.")
                    await self.client.get_server_time()
                elif e.code == 429 or e.code == -1003: # Rate limit exceeded
                    app_log.warning("Rate limit exceeded. Waiting before retry...")
                    await asyncio.sleep(settings.RETRY_DELAY_SECONDS * (2 ** attempt))
                else:
                    # For other API errors, we might not want to retry
                    raise e
            except BinanceRequestException as e:
                errors_log.error(f"Request Error on attempt {attempt + 1}: {e}")
                await asyncio.sleep(settings.RETRY_DELAY_SECONDS * (2 ** attempt))
            except Exception as e:
                errors_log.error(f"An unexpected error occurred: {e}")
                raise e
        raise Exception(f"Failed to execute {method.__name__} after {settings.RETRY_ATTEMPTS} attempts.")

    # --- Account Endpoints ---
    async def get_account_info(self):
        return await self._execute_request(self.client.futures_account)

    async def get_account_balance(self):
        return await self._execute_request(self.client.futures_account_balance)

    async def get_position_information(self):
        return await self._execute_request(self.client.futures_position_information)

    # --- Market Data Endpoints ---
    async def get_exchange_info(self):
        return await self._execute_request(self.client.futures_exchange_info)

    async def get_ticker(self, symbol: str):
        return await self._execute_request(self.client.futures_ticker, symbol=symbol)

    async def get_klines(self, symbol: str, interval: str, limit: int = 500):
        return await self._execute_request(self.client.futures_klines, symbol=symbol, interval=interval, limit=limit)

    # --- Order Endpoints ---
    async def place_order(self, **kwargs):
        return await self._execute_request(self.client.futures_create_order, **kwargs)

    async def cancel_order(self, symbol: str, orderId: int):
        return await self._execute_request(self.client.futures_cancel_order, symbol=symbol, orderId=orderId)

    async def get_open_orders(self, symbol: str = None):
        return await self._execute_request(self.client.futures_get_open_orders, symbol=symbol)

    async def get_all_orders(self, symbol: str):
        return await self._execute_request(self.client.futures_get_all_orders, symbol=symbol)

    async def get_order(self, symbol: str, orderId: int):
        return await self._execute_request(self.client.futures_get_order, symbol=symbol, orderId=orderId)

    # --- Position Management ---
    async def change_leverage(self, symbol: str, leverage: int):
        return await self._execute_request(self.client.futures_change_leverage, symbol=symbol, leverage=leverage)

    async def change_margin_type(self, symbol: str, margin_type: str):
        return await self._execute_request(self.client.futures_change_margin_type, symbol=symbol, marginType=margin_type)
