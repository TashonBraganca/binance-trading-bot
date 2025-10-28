
from decimal import Decimal
from src.utils.logger import app_log, positions_log, errors_log

class PortfolioTracker:
    """
    Monitors real-time account balance, open positions, and closed positions history.
    """

    def __init__(self, client):
        self.client = client
        self.account_info = None
        self.positions = []
        self.closed_positions = [] # This would ideally be stored in a database
        self.trade_history = []

    async def update(self):
        """Fetches and updates the current state of the portfolio."""
        try:
            self.account_info = await self.client.get_account_info()
            # Filter for positions with a non-zero amount
            self.positions = [
                p for p in self.account_info['positions'] 
                if Decimal(p.get('positionAmt', '0')) != 0
            ]
            app_log.info(f"Portfolio updated. Open positions: {len(self.positions)}")
        except Exception as e:
            errors_log.error(f"Failed to update portfolio: {e}")

    def get_position(self, symbol: str):
        """Retrieves a specific position by symbol."""
        for pos in self.positions:
            if pos['symbol'] == symbol:
                return pos
        return None

    def log_trade(self, trade_data: dict):
        """Logs a completed trade and updates history."""
        positions_log.info(f"Trade completed: {trade_data}")
        self.trade_history.append(trade_data)
        # Here you would also update closed_positions

    def get_unrealized_pnl(self) -> Decimal:
        """Calculates the total unrealized PnL across all positions."""
        if not self.account_info:
            return Decimal('0')
        return Decimal(self.account_info.get('totalUnrealizedProfit', '0'))

    def get_wallet_balance(self) -> Decimal:
        """Returns the total wallet balance."""
        if not self.account_info:
            return Decimal('0')
        return Decimal(self.account_info.get('totalWalletBalance', '0'))
