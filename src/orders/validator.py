
from decimal import Decimal, InvalidOperation
from src.utils.logger import app_log, errors_log

class OrderValidator:
    """Performs pre-execution validation of order parameters."""

    def __init__(self, binance_client, risk_manager):
        self.client = binance_client
        self.risk_manager = risk_manager
        self.exchange_info = None

    async def load_exchange_info(self):
        """Loads and caches exchange information."""
        app_log.info("Loading exchange information for validation...")
        self.exchange_info = await self.client.get_exchange_info()
        app_log.info("Exchange information loaded.")

    async def validate_order(self, order_data: dict) -> bool:
        """Runs all validation checks for a given order."""
        if not self.exchange_info:
            await self.load_exchange_info()

        checks = [
            self._validate_symbol,
            self._validate_price_and_quantity,
            self._validate_notional,
            self._validate_balance,
            self.risk_manager.pre_trade_check # This is an async method
        ]

        for check in checks:
            is_valid = await self._run_check(check, order_data)
            if not is_valid:
                return False
        
        return True

    async def _run_check(self, check_func, order_data):
        """Helper to run sync or async validation functions."""
        try:
            # Await if the check function is async (like risk manager)
            if asyncio.iscoroutinefunction(check_func):
                result = await check_func(order_data)
            else:
                result = check_func(order_data)
            
            if not result:
                errors_log.warning(f"Validation failed: {check_func.__name__}")
            return result
        except Exception as e:
            errors_log.error(f"Error during validation check {check_func.__name__}: {e}")
            return False

    def _validate_symbol(self, order_data: dict) -> bool:
        """Validates if the symbol exists and is tradeable."""
        symbol = order_data['symbol']
        symbols = {s['symbol'] for s in self.exchange_info['symbols']}
        if symbol not in symbols:
            app_log.warning(f"Validation failed: Symbol '{symbol}' not found.")
            return False
        return True

    def _get_symbol_filters(self, symbol: str) -> dict:
        """Retrieves the filters for a specific symbol."""
        for s in self.exchange_info['symbols']:
            if s['symbol'] == symbol:
                return {f['filterType']: f for f in s['filters']}
        return {}

    def _validate_price_and_quantity(self, order_data: dict) -> bool:
        """Validates price and quantity against symbol filters (tick size, step size)."""
        symbol = order_data['symbol']
        filters = self._get_symbol_filters(symbol)

        # Validate price for limit orders
        if 'price' in order_data:
            price = Decimal(str(order_data['price']))
            if 'PRICE_FILTER' in filters:
                tick_size = Decimal(filters['PRICE_FILTER']['tickSize'])
                if (price % tick_size) != 0:
                    app_log.warning(f"Validation failed: Price {price} does not match tick size {tick_size} for {symbol}.")
                    return False

        # Validate quantity
        quantity = Decimal(str(order_data['quantity']))
        if 'LOT_SIZE' in filters:
            step_size = Decimal(filters['LOT_SIZE']['stepSize'])
            if (quantity % step_size) != 0:
                app_log.warning(f"Validation failed: Quantity {quantity} does not match step size {step_size} for {symbol}.")
                return False
        return True

    def _validate_notional(self, order_data: dict) -> bool:
        """Validates if the order notional is above the minimum."""
        symbol = order_data['symbol']
        filters = self._get_symbol_filters(symbol)
        
        if 'MIN_NOTIONAL' in filters:
            min_notional = Decimal(filters['MIN_NOTIONAL']['notional'])
            price = Decimal(str(order_data.get('price'))) if 'price' in order_data else self.risk_manager.get_current_price(symbol)
            if not price:
                app_log.warning(f"Could not retrieve current price for {symbol} to validate notional.")
                return False # Or True, depending on strictness
            
            notional_value = Decimal(str(order_data['quantity'])) * price
            if notional_value < min_notional:
                app_log.warning(f"Validation failed: Notional value {notional_value} is below min notional {min_notional} for {symbol}.")
                return False
        return True

    async def _validate_balance(self, order_data: dict) -> bool:
        """Checks if there is sufficient balance for the order."""
        # This is a simplified check. A more robust check would calculate required margin.
        try:
            balance_data = await self.client.get_account_balance()
            usdt_balance = next((b for b in balance_data if b['asset'] == 'USDT'), None)
            
            if usdt_balance:
                available_balance = Decimal(usdt_balance['availableBalance'])
                # A rough estimation of cost
                price = None
                if 'price' in order_data and order_data['price'] > 0:
                    price = Decimal(str(order_data['price']))
                else:
                    price = await self.risk_manager.get_current_price(order_data['symbol'])
                
                if not price:
                    app_log.warning(f"Could not retrieve current price for {order_data['symbol']} to validate balance.")
                    return False

                estimated_cost = (Decimal(str(order_data['quantity'])) * price) / Decimal(str(order_data.get('leverage', 1)))

                if available_balance < estimated_cost:
                    app_log.warning(f"Validation failed: Insufficient available balance. Need ~{estimated_cost:.2f}, have {available_balance:.2f}.")
                    return False
            else:
                app_log.warning("Could not find USDT balance information.")
                return False
        except Exception as e:
            errors_log.error(f"Error validating balance: {e}")
            return False
        return True
import asyncio
