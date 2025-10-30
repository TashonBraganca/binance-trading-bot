from typing import List, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from src.orders.types import Position
from src.utils.logger import performance_logger

class PortfolioAnalytics:
    def __init__(self):
        self.trade_history: List[Dict[str, Any]] = [] # Stores details of closed trades
        self.daily_pnl: Dict[datetime, float] = {}

    def record_closed_position(self, position: Position, close_price: float, close_time: datetime):
        """Records a closed position for analytics."""
        pnl = (close_price - position.entry_price) * position.position_amt if position.position_amt > 0 else \
              (position.entry_price - close_price) * abs(position.position_amt)
        
        trade_data = {
            "symbol": position.symbol,
            "side": "LONG" if position.position_amt > 0 else "SHORT",
            "entry_price": position.entry_price,
            "close_price": close_price,
            "quantity": abs(position.position_amt),
            "pnl": pnl,
            "entry_time": position.update_time, # Assuming update_time is entry_time for simplicity
            "close_time": close_time,
            "duration_seconds": (close_time - position.update_time).total_seconds()
        }
        self.trade_history.append(trade_data)
        performance_logger.info(f"Closed position recorded: {position.symbol} PnL: {pnl:.2f}")

    def calculate_total_pnl(self) -> float:
        """Calculates the total realized PnL from all closed trades."""
        return sum(trade["pnl"] for trade in self.trade_history)

    def calculate_win_rate(self) -> float:
        """Calculates the win rate (percentage of profitable trades)."""
        if not self.trade_history:
            return 0.0
        winning_trades = sum(1 for trade in self.trade_history if trade["pnl"] > 0)
        return (winning_trades / len(self.trade_history)) * 100

    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.0) -> float:
        """Calculates the Sharpe Ratio based on daily PnL. Requires sufficient data."""
        if len(self.daily_pnl) < 2:
            return 0.0 # Not enough data
        
        pnl_series = pd.Series(self.daily_pnl.values()).sort_index()
        returns = pnl_series.pct_change().dropna()
        
        if returns.empty or returns.std() == 0:
            return 0.0

        # Annualize returns and standard deviation (assuming daily data)
        annualized_return = returns.mean() * np.sqrt(252) # 252 trading days in a year
        annualized_std = returns.std() * np.sqrt(252)

        return (annualized_return - risk_free_rate) / annualized_std

    def calculate_max_drawdown(self) -> float:
        """Calculates the maximum drawdown from daily PnL."""
        if not self.daily_pnl:
            return 0.0
        
        pnl_series = pd.Series(self.daily_pnl.values()).sort_index()
        cumulative_returns = (1 + pnl_series).cumprod()
        
        if cumulative_returns.empty:
            return 0.0

        peak = cumulative_returns.expanding(min_periods=1).max()
        drawdown = (cumulative_returns - peak) / peak
        return drawdown.min() * 100 # Return as percentage

    def update_daily_pnl(self, date: datetime, pnl: float):
        """Updates the daily PnL for a given date."""
        self.daily_pnl[date.replace(hour=0, minute=0, second=0, microsecond=0)] = pnl
        performance_logger.debug(f"Daily PnL updated for {date.date()}: {pnl:.2f}")

    def get_performance_summary(self) -> Dict[str, Any]:
        """Returns a summary of key performance metrics."""
        total_pnl = self.calculate_total_pnl()
        win_rate = self.calculate_win_rate()
        sharpe_ratio = self.calculate_sharpe_ratio()
        max_drawdown = self.calculate_max_drawdown()

        return {
            "total_pnl": total_pnl,
            "win_rate": win_rate,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "total_trades": len(self.trade_history)
        }