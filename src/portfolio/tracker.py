from typing import List, Dict, Any, Optional
from datetime import datetime

from src.client.binance_client import BinanceClient
from src.orders.types import Position, AccountBalance
from src.utils.logger import main_logger, errors_logger, positions_logger

class PortfolioTracker:
    def __init__(self, binance_client: BinanceClient):
        self.binance_client = binance_client
        self.open_positions: Dict[str, Position] = {}
        self.account_balances: Dict[str, AccountBalance] = {}
        self.closed_positions_history: List[Position] = []

    def update_account_balances(self):
        """Fetches and updates the latest account balances."""
        try:
            balances_data = self.binance_client.get_balance()
            for item in balances_data:
                asset = item['asset']
                self.account_balances[asset] = AccountBalance(
                    asset=asset,
                    wallet_balance=float(item['walletBalance']),
                    cross_wallet_balance=float(item['crossWalletBalance']),
                    cross_unrealized_pnl=float(item['crossUnPnl']),
                    available_balance=float(item['availableBalance']),
                    update_time=datetime.utcnow()
                )
            main_logger.info("Account balances updated.")
        except Exception as e:
            errors_logger.error(f"Error updating account balances: {e}")

    def update_open_positions(self):
        """Fetches and updates the latest open positions."""
        try:
            positions_data = self.binance_client.get_position_information()
            current_open_positions = {}
            for item in positions_data:
                symbol = item['symbol']
                position_amt = float(item['positionAmt'])
                if position_amt != 0:
                    position = Position(
                        symbol=symbol,
                        entry_price=float(item['entryPrice']),
                        mark_price=float(item['markPrice']),
                        position_amt=position_amt,
                        unrealized_pnl=float(item['unRealizedProfit']),
                        leverage=int(item['leverage']),
                        margin_type=item['marginType'] if item['marginType'] else "UNKNOWN",
                        isolated_wallet=float(item['isolatedWallet']) if item['isolatedWallet'] else None,
                        position_side=item['positionSide'] if item['positionSide'] else "BOTH",
                        update_time=datetime.fromtimestamp(item['updateTime'] / 1000)
                    )
                    current_open_positions[symbol] = position
                    positions_logger.info(f"Open position: {symbol} | Size: {position.position_amt} | Entry: {position.entry_price} | PnL: {position.unrealized_pnl}")

            # Identify closed positions and move to history
            for symbol, position in list(self.open_positions.items()):
                if symbol not in current_open_positions:
                    positions_logger.info(f"Position closed: {symbol} | Final PnL: {position.unrealized_pnl}")
                    self.closed_positions_history.append(position)
            
            self.open_positions = current_open_positions
            main_logger.info("Open positions updated.")

        except Exception as e:
            errors_logger.error(f"Error updating open positions: {e}")

    def get_total_equity(self) -> float:
        """Calculates the total equity across all assets."""
        self.update_account_balances()
        total_equity = 0.0
        for asset, balance in self.account_balances.items():
            # For simplicity, assuming all assets are equivalent to USDT value or can be converted.
            # In a real scenario, you'd need conversion rates for non-USDT assets.
            if asset == "USDT":
                total_equity += balance.wallet_balance
            # Add logic for other assets if needed, e.g., BTC * current_btc_price
        return total_equity

    def get_open_positions_list(self) -> List[Position]:
        """Returns a list of all current open positions."""
        return list(self.open_positions.values())

    def get_position(self, symbol: str) -> Optional[Position]:
        """Returns a specific open position by symbol."""
        return self.open_positions.get(symbol)

    def get_asset_balance(self, asset: str) -> Optional[AccountBalance]:
        """Returns the balance for a specific asset."""
        return self.account_balances.get(asset)