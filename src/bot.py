
import asyncio
from src.client.binance_client import BinanceClient
from src.client.websocket_client import WebsocketClient
from src.orders.executor import OrderExecutor
from src.risk.manager import RiskManager
from src.portfolio.tracker import PortfolioTracker
from src.portfolio.analytics import PortfolioAnalytics
from src.utils.logger import app_log
from src.strategies.twap import TWAPStrategy
from src.strategies.grid import GridStrategy
from src.strategies.oco import OCOStrategy
from src.strategies.trailing_stop import TrailingStopStrategy

class TradingBot:
    """
    The main trading bot class that orchestrates all components.
    """

    def __init__(self):
        app_log.info("Initializing Trading Bot...")
        self.client = BinanceClient()
        self.risk_manager = RiskManager(self.client)
        self.order_executor = OrderExecutor(self.client, self.risk_manager)
        self.portfolio_tracker = PortfolioTracker(self.client)
        self.portfolio_analytics = PortfolioAnalytics(self.portfolio_tracker)
        self.ws_client = WebsocketClient(self.handle_ws_message)
        
        self.strategies = {
            "twap": TWAPStrategy(self),
            "grid": GridStrategy(self),
            "oco": OCOStrategy(self),
            "trailing_stop": TrailingStopStrategy(self),
        }
        self.is_running = False

    async def start(self):
        """Starts the bot and all its components."""
        self.is_running = True
        if not await self.client.initialize():
            self.is_running = False
            return

        await self.portfolio_tracker.update()
        await self.risk_manager.update_state()
        
        # Start WebSocket client in the background
        asyncio.create_task(self.ws_client.start())
        
        app_log.info("Trading Bot started successfully.")
        # The bot is now running, waiting for commands from the CLI

    async def stop(self):
        """Stops the bot and cleans up resources."""
        app_log.info("Stopping Trading Bot...")
        self.is_running = False
        await self.ws_client.stop()
        await self.client.close()
        app_log.info("Trading Bot stopped.")

    async def handle_ws_message(self, message):
        """
        Handler for incoming WebSocket messages.
        This is where real-time data would be processed.
        """
        # Example: Update current prices for risk management
        if 's' in message and 'p' in message:
            symbol = message['s']
            price = message['p']
            self.risk_manager.current_prices[symbol] = price
            # app_log.debug(f"Updated price for {symbol}: {price}")
        
        # In a full implementation, this would be much more complex:
        # - Update order book
        # - Check for filled grid/OCO orders
        # - Feed data to strategies
        pass

    async def run_strategy(self, strategy_name: str, **kwargs):
        """Runs a specified automated strategy."""
        if strategy_name not in self.strategies:
            app_log.error(f"Strategy '{strategy_name}' not found.")
            return
        
        strategy = self.strategies[strategy_name]
        app_log.info(f"Executing strategy: {strategy.name}")
        # Run the strategy in the background
        asyncio.create_task(strategy.run(**kwargs))
