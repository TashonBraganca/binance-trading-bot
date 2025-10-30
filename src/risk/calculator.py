from typing import List
from src.orders.types import Position

class RiskCalculator:
    def __init__(self):
        pass

    def calculate_unrealized_pnl(self, position: Position, current_price: float) -> float:
        """Calculates the unrealized PnL for a given position."""
        if position.position_amt == 0:
            return 0.0
        
        if position.position_amt > 0:  # Long position
            diff = current_price - position.entry_price
            amt = position.position_amt
            pnl = diff * amt
        else:  # Short position
            diff = position.entry_price - current_price
            amt = abs(position.position_amt)
            pnl = diff * amt
        print(f"DEBUG: PnL calculation - symbol: {position.symbol}, entry: {position.entry_price}, current: {current_price}, amt: {position.position_amt}, diff: {diff}, pnl: {pnl}")
        return pnl

    def calculate_total_unrealized_pnl(self, open_positions: List[Position], current_prices: dict) -> float:
        """Calculates the total unrealized PnL across all open positions."""
        total_pnl = 0.0
        for position in open_positions:
            if position.symbol in current_prices:
                total_pnl += self.calculate_unrealized_pnl(position, current_prices[position.symbol])
        return total_pnl

    def calculate_position_value(self, position: Position, current_price: float) -> float:
        """Calculates the current market value of a position."""
        return abs(position.position_amt) * current_price

    def calculate_account_exposure(self, open_positions: List[Position], current_prices: dict, total_balance: float) -> float:
        """Calculates the total account exposure as a percentage of total balance."""
        total_exposure_value = 0.0
        for position in open_positions:
            if position.symbol in current_prices:
                total_exposure_value += self.calculate_position_value(position, current_prices[position.symbol])
        
        if total_balance > 0:
            return (total_exposure_value / total_balance) * 100
        return 0.0

    def calculate_risk_reward_ratio(self, entry_price: float, stop_loss_price: float, take_profit_price: float, is_long: bool) -> float:
        """Calculates the risk/reward ratio for a potential trade."""
        if is_long:
            risk = entry_price - stop_loss_price
            reward = take_profit_price - entry_price
        else:
            risk = stop_loss_price - entry_price
            reward = entry_price - take_profit_price
        
        if risk <= 0:
            return float('inf') # Infinite reward for no risk or negative risk
        return reward / risk