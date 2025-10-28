
import numpy as np
from decimal import Decimal
from src.risk.calculator import calculate_sharpe_ratio, calculate_max_drawdown

class PortfolioAnalytics:
    """
    Calculates and tracks performance metrics like PnL, win rate, and Sharpe ratio.
    """

    def __init__(self, portfolio_tracker):
        self.tracker = portfolio_tracker

    def calculate_performance_metrics(self) -> dict:
        """
        Calculates a dictionary of performance metrics from the trade history.
        """
        trade_history = self.tracker.trade_history
        if not trade_history:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "sharpe_ratio": 0,
                "max_drawdown": 0,
            }

        pnls = [Decimal(trade.get('pnl', '0')) for trade in trade_history]
        wins = [pnl for pnl in pnls if pnl > 0]
        
        total_trades = len(trade_history)
        win_rate = len(wins) / total_trades if total_trades > 0 else 0
        total_pnl = sum(pnls)

        # For Sharpe Ratio and Max Drawdown, we need a series of returns
        # This is a simplified example. A real implementation would use daily portfolio values.
        returns = [float(pnl / Decimal('10000')) for pnl in pnls] # Assuming 10k initial capital
        
        sharpe = calculate_sharpe_ratio(returns)
        max_dd = calculate_max_drawdown(returns)

        return {
            "total_trades": total_trades,
            "win_rate": f"{win_rate:.2%}",
            "total_pnl": f"{total_pnl:.2f} USDT",
            "sharpe_ratio": f"{sharpe:.2f}",
            "max_drawdown": f"{max_dd:.2%}",
        }
