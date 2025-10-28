
from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    """Abstract base class for all trading strategies."""

    def __init__(self, bot, strategy_name):
        self.bot = bot
        self.name = strategy_name

    @abstractmethod
    async def run(self, **kwargs):
        """The main execution method for the strategy."""
        pass

    async def generate_signals(self, market_data):
        """Generates trading signals based on market data. Optional."""
        pass

    async def execute(self, signal):
        """Executes trades based on a generated signal. Optional."""
        pass
