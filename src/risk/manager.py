from typing import List, Dict, Any
from datetime import datetime, timedelta

from src.client.binance_client import BinanceClient
from src.orders.types import Order, Position, AccountBalance
from src.config.constants import (
    DEFAULT_MAX_POSITION_SIZE_PCT,
    DEFAULT_MAX_LEVERAGE,
    DEFAULT_MAX_DAILY_LOSS_PCT,
    DEFAULT_MAX_OPEN_POSITIONS,
    OrderSide
)
from src.utils.logger import main_logger, errors_logger, performance_logger
from src.risk.calculator import RiskCalculator

class RiskManager:
    def __init__(self, binance_client: BinanceClient, risk_calculator: RiskCalculator):
        self.binance_client = binance_client
        self.risk_calculator = risk_calculator

        self.max_position_size_pct = DEFAULT_MAX_POSITION_SIZE_PCT
        self.max_leverage = DEFAULT_MAX_LEVERAGE
        self.max_daily_loss_pct = DEFAULT_MAX_DAILY_LOSS_PCT
        self.max_open_positions = DEFAULT_MAX_OPEN_POSITIONS
        self.exposure_limits: Dict[str, float] = {}

        self.daily_pnl_start_balance = self._get_current_total_balance() # Snapshot at start of day
        self.last_daily_pnl_check = datetime.utcnow()

    def _get_current_total_balance(self) -> float:
        try:
            balances = self.binance_client.get_balance()
            # Assuming USDT as the primary asset for balance tracking
            total_balance = float(next((b['walletBalance'] for b in balances if b['asset'] == 'USDT'), 0.0))
            return total_balance
        except Exception as e:
            errors_logger.error(f"Error getting current total balance: {e}")
            return 0.0

    def update_daily_pnl_start_balance(self):
        """Updates the daily PnL start balance, typically at the start of a new trading day."""
        self.daily_pnl_start_balance = self._get_current_total_balance()
        self.last_daily_pnl_check = datetime.utcnow()
        performance_logger.info(f"Daily PnL start balance updated to: {self.daily_pnl_start_balance:.2f} USDT")

    def check_daily_loss_limit(self) -> bool:
        """Checks if the daily loss limit has been hit."""
        if (datetime.utcnow() - self.last_daily_pnl_check).days >= 1:
            self.update_daily_pnl_start_balance()

        current_balance = self._get_current_total_balance()
        if self.daily_pnl_start_balance == 0:
            return False # Avoid division by zero, or if balance not initialized

        loss_pct = (self.daily_pnl_start_balance - current_balance) / self.daily_pnl_start_balance
        if loss_pct > self.max_daily_loss_pct:
            main_logger.critical(f"DAILY LOSS LIMIT HIT! Current loss: {loss_pct:.2%}, Max allowed: {self.max_daily_loss_pct:.2%}. Trading halted.")
            return True
        return False

    def check_position_size_limit(self, symbol: str, quantity: float, current_price: float, is_long: bool) -> bool:
        """Checks if a new order would violate the maximum position size limit."""
        total_balance = self._get_current_total_balance()
        if total_balance == 0:
            main_logger.warning("Cannot check position size: total balance is zero.")
            return False

        max_position_value = total_balance * self.max_position_size_pct
        order_value = quantity * current_price

        # Get current position for the symbol
        current_positions = self.binance_client.get_position_information(symbol)
        current_position_amt = 0.0
        for pos in current_positions:
            if pos['symbol'] == symbol:
                current_position_amt = float(pos['positionAmt'])
                break

        # Calculate new total position value if this order goes through
        if is_long:
            new_position_amt = current_position_amt + quantity
        else:
            new_position_amt = current_position_amt - quantity
        
        new_position_value = abs(new_position_amt) * current_price

        if new_position_value > max_position_value:
            main_logger.warning(f"Position size limit exceeded for {symbol}. Requested value: {new_position_value:.2f}, Max allowed: {max_position_value:.2f}")
            return False
        return True

    def check_leverage_limit(self, requested_leverage: int) -> bool:
        """Checks if the requested leverage exceeds the maximum allowed leverage."""
        if requested_leverage > self.max_leverage:
            main_logger.warning(f"Leverage limit exceeded. Requested: {requested_leverage}x, Max allowed: {self.max_leverage}x")
            return False
        return True

    def check_max_open_positions(self, open_positions: List[Position]) -> bool:
        """Checks if placing a new order would exceed the maximum number of open positions."""
        if len(open_positions) >= self.max_open_positions:
            main_logger.warning(f"Maximum open positions limit reached. Current: {len(open_positions)}, Max allowed: {self.max_open_positions}")
            return False
        return True

    def check_exposure_limit_per_symbol(self, symbol: str, quantity: float, current_price: float) -> bool:
        """Checks if a new order would violate the exposure limit for a specific symbol."""
        if symbol not in self.exposure_limits:
            return True # No specific limit set for this symbol
        
        limit = self.exposure_limits[symbol]
        total_balance = self._get_current_total_balance()
        if total_balance == 0:
            main_logger.warning("Cannot check exposure limit: total balance is zero.")
            return False

        max_exposure_value = total_balance * limit
        order_value = quantity * current_price

        # Get current position for the symbol
        current_positions = self.binance_client.get_position_information(symbol)
        current_position_amt = 0.0
        for pos in current_positions:
            if pos['symbol'] == symbol:
                current_position_amt = float(pos['positionAmt'])
                break
        
        new_position_value = abs(current_position_amt + quantity) * current_price # Simplified, assumes adding to position

        if new_position_value > max_exposure_value:
            main_logger.warning(f"Exposure limit for {symbol} exceeded. Requested value: {new_position_value:.2f}, Max allowed: {max_exposure_value:.2f}")
            return False
        return True

    def pre_trade_check(self, order: Order, current_price: float, requested_leverage: int, open_positions: List[Position]) -> bool:
        """Performs all pre-trade risk checks."""
        if self.check_daily_loss_limit():
            main_logger.warning("Pre-trade check failed: Daily loss limit hit.")
            return False

        if not self.check_leverage_limit(requested_leverage):
            main_logger.warning("Pre-trade check failed: Leverage limit exceeded.")
            return False

        if not self.check_position_size_limit(order.symbol, order.quantity, current_price, order.side == OrderSide.BUY):
            main_logger.warning("Pre-trade check failed: Position size limit exceeded.")
            return False

        if not self.check_max_open_positions(open_positions):
            main_logger.warning("Pre-trade check failed: Maximum open positions reached.")
            return False
        
        if not self.check_exposure_limit_per_symbol(order.symbol, order.quantity, current_price):
            main_logger.warning("Pre-trade check failed: Symbol exposure limit exceeded.")
            return False

        main_logger.info("Pre-trade risk checks passed.")
        return True

    def set_risk_parameters(self, max_pos_size_pct: float = None, max_leverage: int = None, 
                            max_daily_loss_pct: float = None, max_open_positions: int = None,
                            exposure_limits: Dict[str, float] = None):
        """Sets or updates risk management parameters."""
        if max_pos_size_pct is not None: self.max_position_size_pct = max_pos_size_pct
        if max_leverage is not None: self.max_leverage = max_leverage
        if max_daily_loss_pct is not None: self.max_daily_loss_pct = max_daily_loss_pct
        if max_open_positions is not None: self.max_open_positions = max_open_positions
        if exposure_limits is not None: self.exposure_limits.update(exposure_limits)
        main_logger.info("Risk parameters updated.")