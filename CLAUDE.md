# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Commands

### Development Setup
```bash
pip install -r requirements.txt          # Install dependencies
python src/main.py --test-connection     # Test API connection
```

### Running the Bot
```bash
python src/main.py                       # Start interactive CLI bot
```

### Testing & Quality
```bash
pytest tests/ -v                         # Run all tests
pytest tests/ -v --cov=src               # Run with coverage report
pytest tests/test_orders.py -v           # Run single test file
pytest tests/test_orders.py::TestOrderValidator -v  # Run specific test class
```

### Debugging
- Check log files in `logs/` directory (created at runtime)
- `.env` file must contain `BINANCE_API_KEY`, `BINANCE_API_SECRET`, and `TESTNET=True`
- Set `TESTNET=False` only for mainnet (not recommended without extensive testing)

## Architecture Overview

This is a production-grade Binance Futures trading bot with layered architecture:

```
TradingBot (src/bot.py)
├── CLI Interface (src/main.py)
├── Client Layer
│   ├── BinanceClient (REST API)
│   └── WebSocketClient (real-time market data)
├── Order Management
│   ├── OrderValidator (input validation, symbol checks)
│   ├── OrderExecutor (placement with retry logic)
│   └── Order types (Market, Limit, Stop, OCO, etc.)
├── Risk Management
│   ├── RiskManager (pre-trade checks, daily loss limits)
│   └── RiskCalculator (P&L, margin, notional calculations)
├── Portfolio Tracking
│   ├── PortfolioTracker (positions, balances)
│   └── PortfolioAnalytics (performance metrics)
└── Strategies
    ├── TWAPStrategy (time-weighted average price execution)
    ├── GridStrategy (automated range trading)
    ├── OCOStrategy (stop-loss + take-profit)
    └── TrailingStopStrategy (dynamic stop-loss)
```

### Key Data Flow Patterns

1. **Order Placement Flow:**
   - User input → OrderValidator (symbol, quantity, price checks)
   → RiskManager (margin, leverage, position size checks)
   → OrderExecutor (API call with retry logic)
   → PortfolioTracker (position update)

2. **Real-time Monitoring:**
   - WebSocket streams feed into `_market_data_handler()`
   - Market data cached in `bot.market_data` dict
   - Strategies poll this cache for signal generation

3. **Risk Enforcement:**
   - Pre-trade: RiskManager.pre_trade_check() validates against limits
   - Runtime: Daily PnL tracking, position exposure limits
   - Constants in `src/config/constants.py` define limits (DEFAULT_MAX_POSITION_SIZE_PCT, etc.)

## Code Structure

### Core Modules

**src/client/** - Binance API integration
- `binance_client.py`: REST API wrapper (get_balance, place_order, get_positions, etc.)
- `websocket_client.py`: Real-time data streams (mark price, klines, depth)
- Uses `python-binance` library under the hood

**src/orders/** - Order management
- `types.py`: Order dataclass with symbol, side, type, quantity, price, etc.
- `validator.py`: Validates symbol existence, quantity precision, notional value
- `executor.py`: Places orders with 3-attempt retry logic (RETRY_ATTEMPTS constant)

**src/risk/** - Risk controls
- `manager.py`: Enforces max position size %, leverage, daily loss %, open positions limit
- `calculator.py`: Computes unrealized PnL, maintenance margin, notional value

**src/portfolio/** - State tracking
- `tracker.py`: Maintains open positions, account balances from API
- `analytics.py`: Computes win rate, Sharpe ratio, max drawdown

**src/strategies/** - Advanced execution strategies
- `base.py`: BaseStrategy interface with `start()`, `stop()`, `run()` pattern
- `twap.py`, `grid.py`, `oco.py`, `trailing_stop.py`: Concrete strategy implementations
- Strategies run in background threads via `threading.Thread(target=strategy.run, daemon=True)`

**src/config/** - Configuration
- `constants.py`: Enums (OrderSide, OrderType, KlineInterval) and defaults
- `settings.py`: Loads .env file (BINANCE_API_KEY, BINANCE_API_SECRET, TESTNET flag)

**src/utils/** - Utilities
- `logger.py`: Specialized loggers (main_logger, orders_logger, positions_logger, errors_logger, performance_logger)
- `formatters.py`: Rich UI formatting for tables and panels
- `validators.py`: Utility validation functions

### Important Design Patterns

1. **Strategy Pattern**: BaseStrategy base class with `start()`, `stop()`, `run()` lifecycle
   - Allows pluggable strategy implementations (TWAP, Grid, OCO, Trailing Stop)
   - Strategies can be swapped without changing core bot logic

2. **Decorator Pattern**: OrderValidator wraps OrderExecutor for pre-trade checks
   - Validation happens before API call

3. **Logger Isolation**: Separate loggers per domain (orders, positions, performance)
   - Logs written to `logs/` directory with timestamps
   - Easier to filter/analyze specific trading activities

4. **Testnet-First**: TESTNET flag in settings prevents accidental mainnet trades
   - Always set `TESTNET=True` unless explicitly testing on mainnet

## Testing Strategy

Tests are organized by domain:

- `test_client.py`: BinanceClient mock tests
- `test_orders.py`: OrderValidator and OrderExecutor tests
- `test_risk.py`: RiskManager and RiskCalculator tests
- `test_strategies.py`: Strategy execution tests

All tests use mocks to avoid real API calls. Run coverage with:
```bash
pytest tests/ -v --cov=src --cov-report=html
```

Current coverage target: 80%+

## Common Development Tasks

### Adding a New Order Type
1. Add enum to `src/config/constants.py` (OrderType class)
2. Implement validation in `src/orders/validator.py`
3. Handle execution in `src/orders/executor.py` (construct Binance params)
4. Add test cases in `tests/test_orders.py`

### Adding a New Strategy
1. Create file `src/strategies/my_strategy.py` inheriting from BaseStrategy
2. Implement `start()`, `stop()`, `run()` methods
3. Register in `TradingBot.__init__()` and add to `self.strategies` dict
4. Wire up in CLI menu in `src/main.py`
5. Add tests in `tests/test_strategies.py`

### Updating Risk Limits
- Modify defaults in `src/config/constants.py` (DEFAULT_MAX_POSITION_SIZE_PCT, etc.)
- Or allow runtime changes via CLI in `src/main.py` risk_management_settings_menu()
- RiskManager enforces at execution time in `pre_trade_check()`

### Adding Market Data Handler
- WebSocket streams are configured in `main()` function
- Add new stream type (e.g., "ethusdt@kline_5m") to the streams dict
- Implement handler in `TradingBot._market_data_handler()` to parse event and cache data
- Access cached data via `bot.market_data[symbol]`

## Key Dependencies

- **python-binance**: Binance API client (REST)
- **websocket-client**: Real-time WebSocket connections
- **rich**: Terminal UI (tables, panels, colors)
- **pandas/numpy**: Data analysis for analytics
- **pytest**: Testing framework
- **python-dotenv**: Environment variable loading

## Error Handling Patterns

- API errors (rate limits, invalid symbols) → logged to `errors.log`, retry with exponential backoff
- Validation errors (insufficient balance, invalid quantity) → logged, order rejected before API call
- Market data gaps → fallback to cached prices or API polling
- Network timeouts → RETRY_ATTEMPTS (3 by default) with RETRY_DELAY_SECONDS wait

## Important Notes

- Always use **relative imports** from `src/` (e.g., `from src.client.binance_client import BinanceClient`)
- Order dataclass is immutable after creation; use new Order() for modifications
- Position tracking updates via API call in `PortfolioTracker.update_open_positions()` - not real-time
- Strategies run in daemon threads; graceful shutdown requires calling `strategy.stop()`
- WebSocket connection is separate from REST client; both must be managed independently
- Risk checks use account equity, not just wallet balance (accounts for unrealized PnL)
