
from decimal import Decimal
import numpy as np

def calculate_sharpe_ratio(returns: list[float], risk_free_rate: float = 0.0) -> float:
    """Calculates the Sharpe ratio for a series of returns."""
    returns = np.array(returns)
    if returns.std() == 0:
        return 0.0
    return (returns.mean() - risk_free_rate) / returns.std() * np.sqrt(252) # Annualized

def calculate_max_drawdown(returns: list[float]) -> float:
    """Calculates the maximum drawdown from a series of cumulative returns."""
    cumulative_returns = np.cumprod(np.array(returns) + 1)
    peak = np.maximum.accumulate(cumulative_returns)
    drawdown = (cumulative_returns - peak) / peak
    return drawdown.min()

def calculate_pnl(entry_price: Decimal, close_price: Decimal, quantity: Decimal, side: str) -> Decimal:
    """Calculates the Profit and Loss for a trade."""
    if side.upper() == 'LONG':
        return (close_price - entry_price) * quantity
    elif side.upper() == 'SHORT':
        return (entry_price - close_price) * quantity
    return Decimal('0')
