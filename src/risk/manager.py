
from decimal import Decimal
from src.utils.logger import app_log, errors_log

class RiskManager:
    """
    Professional risk controls that prevent account blow-ups.
    """
    def __init__(self, client):
        self.client = client
        self.account_info = None
        self.current_prices = {}

        # --- Configurable Risk Parameters ---
        self.max_position_size_pct = Decimal('0.1')  # Max 10% of account per position
        self.max_leverage = 10
        self.max_daily_loss_pct = Decimal('-0.05') # Stop trading if down 5% today
        self.max_open_positions = 5

        # --- Live State ---
        self.daily_pnl = Decimal('0')
        self.open_positions = []

    async def update_state(self):
        """Updates account info, balances, and open positions."""
        try:
            self.account_info = await self.client.get_account_info()
            self.open_positions = [p for p in self.account_info['positions'] if Decimal(p['positionAmt']) != 0]
            # In a real scenario, you'd calculate daily PnL from trade history
        except Exception as e:
            errors_log.error(f"Failed to update risk manager state: {e}")

    async def get_current_price(self, symbol: str) -> Decimal | None:
        """Gets the last known price for a symbol from cache, or fetches it."""
        if symbol in self.current_prices:
            return self.current_prices[symbol]
        return await self._fetch_current_price(symbol)

    async def pre_trade_check(self, order_data: dict) -> bool:
        """Performs all pre-trade risk checks."""
        await self.update_state()

        if not self._check_leverage(order_data):
            return False
        if not self._check_daily_loss_limit():
            return False
        if not self._check_max_open_positions():
            return False
        if not await self._check_position_size(order_data):
            return False
        
        app_log.info("All pre-trade risk checks passed.")
        return True

    def _check_leverage(self, order_data: dict) -> bool:
        leverage = int(order_data.get('leverage', 1))
        if leverage > self.max_leverage:
            app_log.warning(f"Risk check failed: Requested leverage {leverage}x exceeds max of {self.max_leverage}x.")
            return False
        return True

    def _check_daily_loss_limit(self) -> bool:
        if self.daily_pnl <= self.account_total_balance * self.max_daily_loss_pct:
            app_log.warning(f"Risk check failed: Daily loss limit of {self.max_daily_loss_pct * 100}% hit.")
            # This should trigger a global trading halt for the day
            return False
        return True

    def _check_max_open_positions(self) -> bool:
        if len(self.open_positions) >= self.max_open_positions:
            app_log.warning(f"Risk check failed: Already at max open positions ({self.max_open_positions}).")
            return False
        return True

    async def _check_position_size(self, order_data: dict) -> bool:
        account_balance = self.account_total_balance
        if account_balance == 0:
            app_log.warning("Risk check failed: Account balance is zero.")
            return False

        price = Decimal(str(order_data.get('price'))) if 'price' in order_data else await self._fetch_current_price(order_data['symbol'])
        if not price:
            return False

        quantity = Decimal(str(order_data['quantity']))
        position_value = quantity * price
        position_size_pct = position_value / account_balance

        if position_size_pct > self.max_position_size_pct:
            max_allowed_value = account_balance * self.max_position_size_pct
            max_qty = max_allowed_value / price
            app_log.warning(f"Risk check failed: Position size {position_size_pct:.2%} exceeds max of {self.max_position_size_pct:.2%}.")
            app_log.warning(f"Suggested max quantity for {order_data['symbol']}: {max_qty:.4f}")
            return False
        return True

    async def _fetch_current_price(self, symbol: str) -> Decimal | None:
        try:
            ticker = await self.client.get_ticker(symbol)
            price = Decimal(ticker['lastPrice'])
            self.current_prices[symbol] = price # Cache the price
            return price
        except Exception as e:
            errors_log.error(f"Could not fetch current price for {symbol} during risk check: {e}")
            return None

    
