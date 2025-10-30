import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode
from typing import Dict, Any, Optional

from src.config.settings import settings
from src.config.constants import BINANCE_FUTURES_TESTNET_URL, RETRY_ATTEMPTS, RETRY_DELAY_SECONDS, MAX_RATE_LIMIT_RETRIES, RATE_LIMIT_WAIT_SECONDS
from src.utils.logger import api_requests_logger, errors_logger

class BinanceClient:
    def __init__(self):
        self.base_url = BINANCE_FUTURES_TESTNET_URL
        self.api_key = settings.BINANCE_API_KEY
        self.api_secret = settings.BINANCE_API_SECRET
        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": self.api_key})
        self.rate_limit_retries = 0

    def _sign_request(self, params: Dict[str, Any]) -> str:
        query_string = urlencode(params)
        signature = hmac.new(self.api_secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256).hexdigest()
        return signature

    def _send_request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, signed: bool = False) -> Dict[str, Any]:
        if params is None:
            params = {}

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            signature = self._sign_request(params)
            params["signature"] = signature

        url = f"{self.base_url}{path}"

        for attempt in range(RETRY_ATTEMPTS):
            try:
                api_requests_logger.debug(f"Sending {method} request to {url} with params: {params}")
                if method == "GET":
                    response = self.session.get(url, params=params, timeout=10)
                elif method == "POST":
                    response = self.session.post(url, data=params, timeout=10)
                elif method == "PUT":
                    response = self.session.put(url, data=params, timeout=10)
                elif method == "DELETE":
                    response = self.session.delete(url, data=params, timeout=10)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()
                api_requests_logger.debug(f"Received response: {response.json()}")
                return response.json()

            except requests.exceptions.HTTPError as http_err:
                error_code = http_err.response.status_code
                errors_logger.error(f"HTTP error occurred: {http_err} - Response: {http_err.response.text}")

                if error_code == 429:  # Rate limit exceeded
                    self.rate_limit_retries += 1
                    if self.rate_limit_retries > MAX_RATE_LIMIT_RETRIES:
                        errors_logger.critical("Max rate limit retries exceeded. Exiting.")
                        raise
                    retry_after = int(http_err.response.headers.get("Retry-After", RATE_LIMIT_WAIT_SECONDS))
                    errors_logger.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds...")
                    time.sleep(retry_after)
                    continue
                elif error_code == 401:  # Unauthorized (Invalid API credentials)
                    errors_logger.critical("Invalid API credentials. Please check your .env file.")
                    raise
                elif error_code >= 400 and error_code < 500: # Client error
                    errors_logger.error(f"Client error: {http_err.response.text}")
                    raise
                elif error_code >= 500: # Server error
                    errors_logger.error(f"Server error: {http_err.response.text}. Retrying...")
                    time.sleep(RETRY_DELAY_SECONDS * (2 ** attempt)) # Exponential backoff
                    continue

            except requests.exceptions.ConnectionError as conn_err:
                errors_logger.error(f"Connection error occurred: {conn_err}. Retrying...")
                time.sleep(RETRY_DELAY_SECONDS * (2 ** attempt)) # Exponential backoff
                continue
            except requests.exceptions.Timeout as timeout_err:
                errors_logger.error(f"Timeout error occurred: {timeout_err}. Retrying...")
                time.sleep(RETRY_DELAY_SECONDS * (2 ** attempt)) # Exponential backoff
                continue
            except requests.exceptions.RequestException as req_err:
                errors_logger.critical(f"An unexpected request error occurred: {req_err}")
                raise

        errors_logger.critical(f"Failed to send request after {RETRY_ATTEMPTS} attempts.")
        raise Exception(f"Failed to send request to {url}")

    # Public API methods
    def get_exchange_info(self) -> Dict[str, Any]:
        """Get current exchange trading rules and symbol information."""
        return self._send_request("GET", "/fapi/v1/exchangeInfo")

    def get_account_information(self) -> Dict[str, Any]:
        """Get current account information."""
        return self._send_request("GET", "/fapi/v2/account", signed=True)

    def get_balance(self) -> Dict[str, Any]:
        """Get account balance."""
        return self._send_request("GET", "/fapi/v2/balance", signed=True)

    def get_open_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get all open orders on a symbol or all symbols if not provided."""
        params = {"symbol": symbol} if symbol else {}
        return self._send_request("GET", "/fapi/v1/openOrders", params, signed=True)

    def get_all_orders(self, symbol: str, limit: int = 500) -> Dict[str, Any]:
        """Get all account orders; active, canceled, or filled."""
        params = {"symbol": symbol, "limit": limit}
        return self._send_request("GET", "/fapi/v1/allOrders", params, signed=True)

    def get_position_information(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get current position information."""
        params = {"symbol": symbol} if symbol else {}
        return self._send_request("GET", "/fapi/v2/positionRisk", params, signed=True)

    def place_order(self, symbol: str, side: str, order_type: str, quantity: float, price: Optional[float] = None, 
                    time_in_force: Optional[str] = None, stop_price: Optional[float] = None, 
                    close_position: Optional[bool] = False, **kwargs) -> Dict[str, Any]:
        """Place a new order."""
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }
        if price: params["price"] = price
        if time_in_force: params["timeInForce"] = time_in_force
        if stop_price: params["stopPrice"] = stop_price
        if close_position: params["closePosition"] = close_position
        params.update(kwargs)
        return self._send_request("POST", "/fapi/v1/order", params, signed=True)

    def cancel_order(self, symbol: str, order_id: Optional[int] = None, orig_client_order_id: Optional[str] = None) -> Dict[str, Any]:
        """Cancel an active order."""
        params = {"symbol": symbol}
        if order_id: params["orderId"] = order_id
        if orig_client_order_id: params["origClientOrderId"] = orig_client_order_id
        return self._send_request("DELETE", "/fapi/v1/order", params, signed=True)

    def cancel_all_open_orders(self, symbol: str) -> Dict[str, Any]:
        """Cancel all open orders on a symbol."""
        params = {"symbol": symbol}
        return self._send_request("DELETE", "/fapi/v1/allOpenOrders", params, signed=True)

    def change_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """Change user's initial leverage of the symbol."""
        params = {"symbol": symbol, "leverage": leverage}
        return self._send_request("POST", "/fapi/v1/leverage", params, signed=True)

    def change_margin_type(self, symbol: str, margin_type: str) -> Dict[str, Any]:
        """Change user's margin type of the symbol."""
        params = {"symbol": symbol, "marginType": margin_type}
        return self._send_request("POST", "/fapi/v1/marginType", params, signed=True)

    def get_klines(self, symbol: str, interval: str, limit: int = 500) -> Dict[str, Any]:
        """Get candlestick data for a symbol."""
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        return self._send_request("GET", "/fapi/v1/klines", params)

    def get_ticker_24hr(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get 24-hour rolling window price change statistics."""
        params = {"symbol": symbol} if symbol else {}
        return self._send_request("GET", "/fapi/v1/ticker/24hr", params)

    def get_mark_price(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get mark price and funding rate."""
        params = {"symbol": symbol} if symbol else {}
        return self._send_request("GET", "/fapi/v1/premiumIndex", params)

    def get_depth(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Get order book for a symbol."""
        params = {"symbol": symbol, "limit": limit}
        return self._send_request("GET", "/fapi/v1/depth", params)

    def get_server_time(self) -> int:
        """Get Binance server time."""
        response = self._send_request("GET", "/fapi/v1/time")
        return response["serverTime"]