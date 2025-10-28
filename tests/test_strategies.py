
import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
from src.bot import TradingBot
from src.strategies.twap import TWAPStrategy
from src.strategies.grid import GridStrategy
from src.config.constants import OrderSide

@pytest.fixture
def mock_bot():
    """Fixture to create a mock TradingBot with necessary components."""
    bot = MagicMock(spec=TradingBot)
    bot.order_executor = AsyncMock()
    bot.risk_manager = AsyncMock()
    bot.risk_manager._fetch_current_price = AsyncMock(return_value=Decimal('2000'))
    return bot

@pytest.mark.asyncio
async def test_twap_strategy_run(mock_bot):
    """Test the TWAP strategy's execution logic."""
    twap_strategy = TWAPStrategy(mock_bot)
    
    symbol = "ETHUSDT"
    total_quantity = Decimal("10")
    duration_minutes = 10
    side = OrderSide.BUY

    # Mock the sleep function to speed up the test
    with unittest.mock.patch('asyncio.sleep', new_callable=AsyncMock):
        await twap_strategy.run(symbol, total_quantity, duration_minutes, side)

    # Expect 10 chunks (as per default in the strategy)
    assert mock_bot.order_executor.execute_order.call_count == 10

    # Check the details of the first call
    first_call_args = mock_bot.order_executor.execute_order.call_args_list[0].args[0]
    assert first_call_args['symbol'] == symbol
    assert first_call_args['side'] == side.value
    assert first_call_args['type'] == "MARKET"
    assert first_call_args['quantity'] == 1.0 # 10 total / 10 chunks

@pytest.mark.asyncio
async def test_grid_strategy_setup(mock_bot):
    """Test the Grid strategy's setup logic."""
    grid_strategy = GridStrategy(mock_bot)

    symbol = "ETHUSDT"
    num_grids = 10
    lower_bound = Decimal("1800")
    upper_bound = Decimal("2200")

    # Mock the sleep function
    with unittest.mock.patch('asyncio.sleep', new_callable=AsyncMock):
        await grid_strategy.run(
            symbol=symbol,
            price_range_pct=0.1,
            num_grids=num_grids,
            investment=Decimal("10000"),
            lower_bound=lower_bound,
            upper_bound=upper_bound
        )

    # The strategy should place `num_grids` orders
    assert mock_bot.order_executor.execute_order.call_count == num_grids

    # Check that both BUY and SELL orders are placed
    sides = {call.args[0]['side'] for call in mock_bot.order_executor.execute_order.call_args_list}
    assert OrderSide.BUY.value in sides
    assert OrderSide.SELL.value in sides

    # Check a sample order
    sample_call_args = mock_bot.order_executor.execute_order.call_args_list[0].args[0]
    assert sample_call_args['symbol'] == symbol
    assert sample_call_args['type'] == "LIMIT"
    assert sample_call_args['timeInForce'] == "GTC"

import unittest.mock
