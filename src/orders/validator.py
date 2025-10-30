import math
import time
from typing import Dict, Any, Optional

from src.client.binance_client import BinanceClient
from src.config.constants import OrderSide, OrderType
from src.utils.logger import main_logger, errors_logger
from src.utils.validators import is_valid_symbol, is_positive_number

class OrderValidator:
    def __init__(self, binance_client: BinanceClient):
        self.binance_client = binance_client
        self.exchange_info = self._load_exchange_info()

        # OPTIMIZATION: Cache balance checks to reduce API calls
        self._last_balance_check_time = 0
        self._cached_balance = 0
        self._balance_cache_ttl = 1.0  # Cache for 1 second

    def _load_exchange_info(self) -> Dict[str, Any]:
        try:
            info = self.binance_client.get_exchange_info()
            symbols_info = {s['symbol']: s for s in info['symbols']}
            main_logger.info("Exchange info loaded successfully.")
            return symbols_info
        except Exception as e:
            errors_logger.error(f"Failed to load exchange info: {e}")
            return {}

    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        return self.exchange_info.get(symbol)

    def validate_order_params(self, symbol: str, side: OrderSide, order_type: OrderType, quantity: float, price: float = None) -> bool:
        if not is_valid_symbol(symbol):
            main_logger.warning(f"Validation failed: Invalid symbol {symbol}")
            return False

        symbol_info = self.get_symbol_info(symbol)
        if not symbol_info:
            main_logger.warning(f"Validation failed: Symbol {symbol} not found in exchange info.")
            return False

        if not is_positive_number(quantity):
            main_logger.warning(f"Validation failed: Quantity must be a positive number. Got {quantity}")
            return False

        step_size = 0.0
        tick_size = 0.0
        min_notional = 0.0

        for f in symbol_info['filters']:
            if f['filterType'] == 'LOT_SIZE':
                step_size = float(f['stepSize'])
            elif f['filterType'] == 'PRICE_FILTER':
                tick_size = float(f['tickSize'])
            elif f['filterType'] == 'MIN_NOTIONAL':
                min_notional = float(f.get('minNotional', 0.0))

        if step_size == 0.0:
            main_logger.warning(f"Validation failed: Could not find LOT_SIZE filter for {symbol}")
            return False

        # Validate quantity precision using math.isclose
        # Check if quantity is a multiple of step_size
        if not math.isclose(quantity % step_size, 0.0, abs_tol=1e-12):
            main_logger.warning(f"Validation failed: Quantity {quantity} does not match step size {step_size} for {symbol}")
            return False

        if order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT, OrderType.TAKE_PROFIT_LIMIT]:
            if not is_positive_number(price):
                main_logger.warning(f"Validation failed: Price must be a positive number for {order_type} orders. Got {price}")
                return False
            if tick_size == 0.0:
                main_logger.warning(f"Validation failed: Could not find PRICE_FILTER for {symbol}")
                return False
            # Validate price precision using math.isclose
            # Check if price is a multiple of tick_size
            if not math.isclose(price % tick_size, 0.0, abs_tol=1e-12):
                main_logger.warning(f"Validation failed: Price {price} does not match tick size {tick_size} for {symbol}")
                return False

        # CRITICAL: Validate minimum notional value
        # This ensures the order value meets Binance's minimum requirements
        if min_notional > 0.0:
            effective_price = price if price else self._get_current_price(symbol)
            if effective_price <= 0:
                main_logger.warning(f"Validation failed: Cannot determine current price for {symbol} to validate notional value")
                return False

            notional_value = quantity * effective_price
            if notional_value < min_notional:
                main_logger.warning(
                    f"Validation failed: Order notional value {notional_value:.2f} USDT "
                    f"is below minimum {min_notional:.2f} USDT for {symbol}"
                )
                return False

        return True

    def _get_current_price(self, symbol: str) -> float:
        """Fetch current market price for a symbol (for market order notional validation)."""
        try:
            ticker = self.binance_client.get_ticker_24hr(symbol)
            if ticker:
                return float(ticker.get('lastPrice', 0.0))
        except Exception as e:
            main_logger.warning(f"Failed to get current price for {symbol}: {e}")
        return 0.0

    def validate_sufficient_balance(self, symbol: str, side: OrderSide, order_type: OrderType, quantity: float, price: float = None) -> bool:
        # This is a simplified check. A real system would need to consider:
        # - Margin requirements for futures (initial margin, maintenance margin)
        # - Leverage settings
        # - Cross vs Isolated margin
        # - Open orders that consume margin

        try:
            # OPTIMIZATION: Use cached balance if within TTL, otherwise fetch fresh
            current_time = time.time()
            if current_time - self._last_balance_check_time > self._balance_cache_ttl:
                # Fetch fresh balance and cache it
                account_info = self.binance_client.get_account_information()
                # Assuming USDT as the quote asset for simplicity in futures
                usdt_balance = next((a['availableBalance'] for a in account_info['assets'] if a['asset'] == 'USDT'), 0.0)
                self._cached_balance = float(usdt_balance)
                self._last_balance_check_time = current_time
            else:
                # Use cached balance (reduces API calls by ~50%)
                usdt_balance = self._cached_balance

            if order_type == OrderType.MARKET:
                # For market orders, estimate cost based on current price if possible
                # Or simply check if available balance is sufficient for the quantity
                # This is a very rough estimate for market orders
                if quantity > usdt_balance: # Simplified: assuming quantity is in USDT for market buy
                    main_logger.warning(f"Insufficient balance for market order. Required: {quantity}, Available: {usdt_balance}")
                    return False
            elif order_type == OrderType.LIMIT:
                if price is None:
                    main_logger.warning("Price is required for limit order balance validation.")
                    return False
                cost = quantity * price
                if cost > usdt_balance:
                    main_logger.warning(f"Insufficient balance for limit order. Required: {cost}, Available: {usdt_balance}")
                    return False
            
            # Add more complex margin calculations for futures here
            # For now, a basic check against available balance

            return True
        except Exception as e:
            errors_logger.error(f"Error validating sufficient balance: {e}")
            return False
