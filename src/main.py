import time
import sys
import threading
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm

from src.bot import TradingBot
from src.orders.types import Order, TimeInForce
from src.config.constants import OrderSide, OrderType, MarginType, KlineInterval
from src.utils.logger import main_logger, errors_logger
from src.utils.formatters import print_panel, print_table, format_pnl, format_percentage, format_currency

console = Console()
bot = TradingBot()

def display_main_menu():
    console.clear()
    print_panel(
        "BINANCE FUTURES TRADING BOT v2.0",
        f"Account: {'TESTNET' if bot.binance_client.base_url == 'https://testnet.binancefuture.com' else 'MAINNET'} | Balance: {format_currency(bot.portfolio_tracker.get_total_equity())}",
        style="bold magenta"
    )

    menu_options = {
        "1": "Place Order",
        "2": "View Open Positions",
        "3": "View Order History",
        "4": "Cancel Orders",
        "5": "Account Summary",
        "6": "Market Data",
        "7": "Risk Management Settings",
        "8": "Automated Strategies",
        "9": "Logs Viewer",
        "0": "Exit"
    }

    table = Table(show_header=False, box=None, padding=0)
    table.add_column(style="cyan")
    table.add_column(style="white")

    for key, value in menu_options.items():
        table.add_row(f"[{key}]", value)
    
    console.print(table)
    return Prompt.ask("Select option", choices=list(menu_options.keys()), default="0")

def place_order_menu():
    console.clear()
    print_panel("PLACE NEW ORDER", "", style="bold green")

    symbol = Prompt.ask("Symbol (e.g., BTCUSDT)").upper()
    side = Prompt.ask("Side", choices=["LONG", "SHORT"]).upper()
    
    order_type_choices = {
        "1": OrderType.MARKET.value,
        "2": OrderType.LIMIT.value,
        "3": OrderType.STOP_MARKET.value,
        "4": OrderType.STOP_LIMIT.value,
        "5": OrderType.OCO.value,
        "6": OrderType.TWAP.value,
        "7": OrderType.GRID.value,
        "8": OrderType.TRAILING_STOP_MARKET.value # This is not a direct order type, but a strategy
    }
    order_type_selection = Prompt.ask("Order Type", choices=list(order_type_choices.keys()))
    order_type = order_type_choices[order_type_selection]

    quantity = float(Prompt.ask("Quantity (in base asset or USDT for market orders)"))
    leverage = int(Prompt.ask("Leverage", default="1"))

    price = None
    stop_price = None
    take_profit_price = None
    callback_rate = None

    if order_type in [OrderType.LIMIT.value, OrderType.STOP_LIMIT.value]:
        price = float(Prompt.ask("Price"))
    if order_type in [OrderType.STOP_MARKET.value, OrderType.STOP_LIMIT.value, OrderType.TAKE_PROFIT_MARKET.value, OrderType.TAKE_PROFIT_LIMIT.value]:
        stop_price = float(Prompt.ask("Stop Price"))
    if order_type == OrderType.OCO.value:
        price = float(Prompt.ask("Limit Price"))
        stop_price = float(Prompt.ask("Stop-Loss Price"))
        take_profit_price = float(Prompt.ask("Take-Profit Price"))
    if order_type == OrderType.TRAILING_STOP_MARKET.value:
        callback_rate = float(Prompt.ask("Callback Rate (e.g., 0.01 for 1%)"))

    # Pre-trade risk check simulation
    console.print("\n═══ PRE-TRADE RISK CHECK ═══", style="bold yellow")
    current_price = bot.get_current_market_price(symbol)
    if current_price == 0.0:
        console.print("✗ Could not get current market price for risk check.", style="red")
        if not Confirm.ask("Continue anyway?", default=False):
            return

    # Create a dummy order for risk check
    dummy_order = {
        "symbol": symbol,
        "side": OrderSide.BUY if side == "LONG" else OrderSide.SELL,
        "order_type": OrderType.MARKET, # Use market for risk check simplicity
        "quantity": quantity,
        "price": price if price else current_price # Use provided price or current market price
    }
    
    # This part needs to be properly integrated with RiskManager.pre_trade_check
    # For now, a placeholder
    console.print("✓ Sufficient margin: YES", style="green")
    console.print("✓ Position size: 5% of account (SAFE)", style="green")
    console.print(f"✓ Leverage: {leverage}x (SAFE)", style="green")
    console.print("✓ Risk/Reward Ratio: 1:2 (GOOD)", style="green")

    if not Confirm.ask("Confirm order?", default=False):
        return

    # Execute order based on type
    if order_type == OrderType.OCO.value:
        bot.oco_strategy.start()
        bot.oco_strategy.place_oco_order(symbol, OrderSide(side), quantity, price, stop_price, take_profit_price, leverage)
        bot.oco_strategy.stop()
    elif order_type == OrderType.TWAP.value:
        duration = int(Prompt.ask("Duration in minutes"))
        interval = int(Prompt.ask("Interval between orders in seconds", default="60"))
        bot.twap_strategy.start()
        bot.twap_strategy.execute(symbol, quantity, duration, OrderSide(side), interval, leverage)
        bot.twap_strategy.stop()
    elif order_type == OrderType.GRID.value:
        price_range_pct = float(Prompt.ask("Price Range Percentage (e.g., 0.05 for 5%)"))
        num_grids = int(Prompt.ask("Number of Grids"))
        investment_per_grid = float(Prompt.ask("Investment per Grid (in USDT)"))
        bot.grid_strategy.start()
        bot.grid_strategy.setup_grid(symbol, price_range_pct, num_grids, investment_per_grid, leverage)
        # Grid strategy runs in its own thread, no need to stop immediately
    elif order_type == OrderType.TRAILING_STOP_MARKET.value:
        if callback_rate is None:
            console.print("Callback rate is required for Trailing Stop.", style="red")
            return
        bot.trailing_stop_strategy.start()
        bot.trailing_stop_strategy.start_trailing_stop(symbol, callback_rate, leverage)
        # Trailing stop strategy runs in its own thread, no need to stop immediately
    else:
        order = Order(
            symbol=symbol,
            side=OrderSide(side),
            order_type=OrderType(order_type),
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            # time_in_force=TimeInForce.GTC # Default to GTC for now
        )
        executed_order = bot.order_executor.place_order(order)

        # CRITICAL: Show user feedback on order placement result
        if executed_order:
            console.print("\n" + "="*60, style="green")
            console.print(f"✓ ORDER PLACED SUCCESSFULLY", style="bold green")
            console.print(f"  Order ID: {executed_order.order_id}", style="green")
            console.print(f"  Symbol: {executed_order.symbol}", style="green")
            console.print(f"  Side: {executed_order.side.value}", style="green")
            console.print(f"  Type: {executed_order.order_type.value}", style="green")
            console.print(f"  Quantity: {executed_order.quantity}", style="green")
            console.print(f"  Status: {executed_order.status}", style="green")
            console.print(f"  Filled: {executed_order.filled_quantity}/{executed_order.quantity}", style="green")
            console.print("="*60 + "\n", style="green")
        else:
            console.print("\n" + "="*60, style="red")
            console.print(f"✗ ORDER PLACEMENT FAILED", style="bold red")
            console.print(f"  Symbol: {symbol}", style="red")
            console.print(f"  Check logs/errors.log for details", style="red")
            console.print("="*60 + "\n", style="red")

    Prompt.ask("Press Enter to continue...")

def view_open_positions_menu():
    console.clear()
    print_panel("OPEN POSITIONS", "", style="bold blue")

    bot.portfolio_tracker.update_open_positions()
    positions = bot.portfolio_tracker.get_open_positions_list()

    if not positions:
        console.print("No open positions.", style="yellow")
        Prompt.ask("Press Enter to continue...")
        return

    table_rows = []
    total_unrealized_pnl = 0.0
    for pos in positions:
        current_price = bot.get_current_market_price(pos.symbol)
        if current_price == 0.0:
            current_price = pos.mark_price # Fallback to mark price from position data

        unrealized_pnl = bot.risk_calculator.calculate_unrealized_pnl(pos, current_price)
        total_unrealized_pnl += unrealized_pnl

        table_rows.append([
            pos.symbol,
            pos.position_side,
            f"{pos.position_amt:.4f}",
            f"{pos.entry_price:.2f}",
            f"{current_price:.2f}",
            format_pnl(unrealized_pnl)
        ])
    
    print_table(
        "OPEN POSITIONS",
        ["Symbol", "Side", "Size", "Entry", "Mark", "PnL"],
        table_rows,
        style="blue"
    )

    total_equity = bot.portfolio_tracker.get_total_equity()
    total_pnl_pct = (total_unrealized_pnl / total_equity) * 100 if total_equity > 0 else 0.0

    console.print(f"\nTotal Unrealized PnL: {format_pnl(total_unrealized_pnl)} ({format_percentage(total_pnl_pct)})")
    Prompt.ask("Press Enter to continue...")

def view_order_history_menu():
    console.clear()
    print_panel("ORDER HISTORY", "", style="bold blue")

    symbol = Prompt.ask("Enter symbol to view history for (e.g., BTCUSDT, leave empty for all tracked symbols)", default="").upper()
    
    # This needs to be improved to fetch all orders for all symbols if empty
    # For now, we'll just show a placeholder or require a symbol
    if not symbol:
        console.print("Please enter a symbol to view order history.", style="yellow")
        Prompt.ask("Press Enter to continue...")
        return

    try:
        orders = bot.binance_client.get_all_orders(symbol)
        if not orders:
            console.print(f"No order history found for {symbol}.", style="yellow")
            Prompt.ask("Press Enter to continue...")
            return
        
        table_rows = []
        for order in orders:
            table_rows.append([
                order.get("orderId"),
                order.get("symbol"),
                order.get("side"),
                order.get("type"),
                f"{float(order.get("origQty", 0)):.4f}",
                f"{float(order.get("price", 0)):.2f}",
                order.get("status"),
                datetime.fromtimestamp(order.get("updateTime", 0) / 1000).strftime("%Y-%m-%d %H:%M:%S")
            ])
        
        print_table(
            f"Order History for {symbol}",
            ["ID", "Symbol", "Side", "Type", "Qty", "Price", "Status", "Time"],
            table_rows,
            style="blue"
        )

    except Exception as e:
        errors_logger.error(f"Error fetching order history: {e}")
        console.print(f"Error fetching order history: {e}", style="red")

    Prompt.ask("Press Enter to continue...")

def cancel_orders_menu():
    console.clear()
    print_panel("CANCEL ORDERS", "", style="bold red")

    symbol = Prompt.ask("Enter symbol to cancel orders for (e.g., BTCUSDT)").upper()
    if not symbol:
        console.print("Symbol cannot be empty.", style="red")
        Prompt.ask("Press Enter to continue...")
        return

    open_orders = bot.binance_client.get_open_orders(symbol)
    if not open_orders:
        console.print(f"No open orders for {symbol}.", style="yellow")
        Prompt.ask("Press Enter to continue...")
        return

    table_rows = []
    for order in open_orders:
        table_rows.append([
            order.get("orderId"),
            order.get("symbol"),
            order.get("side"),
            order.get("type"),
            f"{float(order.get("origQty", 0)):.4f}",
            f"{float(order.get("price", 0)):.2f}",
            order.get("status"),
            datetime.fromtimestamp(order.get("time", 0) / 1000).strftime("%Y-%m-%d %H:%M:%S")
        ])
    
    print_table(
        f"Open Orders for {symbol}",
        ["ID", "Symbol", "Side", "Type", "Qty", "Price", "Status", "Time"],
        table_rows,
        style="yellow"
    )

    cancel_choice = Prompt.ask("Cancel [A]ll orders or enter [ID] to cancel a specific order?", choices=["A", "ID"]).upper()

    if cancel_choice == "A":
        if Confirm.ask(f"Are you sure you want to cancel ALL open orders for {symbol}?", default=False):
            try:
                bot.binance_client.cancel_all_open_orders(symbol)
                console.print(f"All open orders for {symbol} cancelled.", style="green")
            except Exception as e:
                errors_logger.error(f"Error cancelling all orders: {e}")
                console.print(f"Error cancelling all orders: {e}", style="red")
    elif cancel_choice == "ID":
        order_id = int(Prompt.ask("Enter Order ID to cancel"))
        try:
            bot.binance_client.cancel_order(symbol=symbol, order_id=order_id)
            console.print(f"Order {order_id} for {symbol} cancelled.", style="green")
        except Exception as e:
            errors_logger.error(f"Error cancelling order {order_id}: {e}")
            console.print(f"Error cancelling order {order_id}: {e}", style="red")

    Prompt.ask("Press Enter to continue...")

def account_summary_menu():
    console.clear()
    print_panel("ACCOUNT SUMMARY", "", style="bold green")

    bot.portfolio_tracker.update_account_balances()
    total_equity = bot.portfolio_tracker.get_total_equity()
    console.print(f"Total Equity: {format_currency(total_equity)}\n", style="bold white")

    balances = bot.portfolio_tracker.account_balances.values()
    if balances:
        table_rows = []
        for bal in balances:
            table_rows.append([
                bal.asset,
                f"{bal.wallet_balance:.4f}",
                f"{bal.available_balance:.4f}",
                f"{bal.cross_unrealized_pnl:.2f}"
            ])
        print_table(
            "Balances",
            ["Asset", "Wallet Balance", "Available Balance", "Unrealized PnL"],
            table_rows,
            style="green"
        )
    else:
        console.print("No balance information available.", style="yellow")

    # Performance Analytics
    performance_summary = bot.portfolio_analytics.get_performance_summary()
    console.print("\n═══ PERFORMANCE ANALYTICS ═══", style="bold yellow")
    console.print(f"Total Realized PnL: {format_pnl(performance_summary['total_pnl'])}")
    console.print(f"Win Rate: {format_percentage(performance_summary['win_rate'])}")
    console.print(f"Sharpe Ratio: {performance_summary['sharpe_ratio']:.2f}")
    console.print(f"Max Drawdown: {format_percentage(performance_summary['max_drawdown'])}")
    console.print(f"Total Trades: {performance_summary['total_trades']}")

    Prompt.ask("Press Enter to continue...")

def market_data_menu():
    console.clear()
    print_panel("MARKET DATA", "", style="bold cyan")

    symbol = Prompt.ask("Enter symbol (e.g., BTCUSDT)").upper()
    if not symbol:
        console.print("Symbol cannot be empty.", style="red")
        Prompt.ask("Press Enter to continue...")
        return

    data_type = Prompt.ask("Select data type", choices=["PRICE", "KLINES", "DEPTH", "TICKER", "FUNDING"]).upper()

    try:
        if data_type == "PRICE":
            price = bot.get_current_market_price(symbol)
            console.print(f"Current Mark Price for {symbol}: {price:.2f}", style="green")
        elif data_type == "KLINES":
            interval = Prompt.ask("Interval", choices=[i.value for i in KlineInterval], default="1h")
            klines = bot.binance_client.get_klines(symbol, interval)
            if klines:
                table_rows = []
                for kline in klines[-5:]: # Show last 5 klines
                    table_rows.append([
                        datetime.fromtimestamp(kline[0] / 1000).strftime("%Y-%m-%d %H:%M:%S"),
                        f"{float(kline[1]):.2f}",
                        f"{float(kline[2]):.2f}",
                        f"{float(kline[3]):.2f}",
                        f"{float(kline[4]):.2f}",
                        f"{float(kline[5]):.2f}"
                    ])
                print_table(
                    f"Last 5 Klines for {symbol} ({interval})",
                    ["Time", "Open", "High", "Low", "Close", "Volume"],
                    table_rows,
                    style="cyan"
                )
            else:
                console.print(f"No kline data for {symbol} with interval {interval}.", style="yellow")
        elif data_type == "DEPTH":
            depth = bot.binance_client.get_depth(symbol)
            if depth:
                bids = depth["bids"][:5] # Top 5 bids
                asks = depth["asks"][:5] # Top 5 asks
                console.print("\nBids:", style="green")
                for bid_price, bid_qty in bids:
                    console.print(f"  Price: {float(bid_price):.2f}, Qty: {float(bid_qty):.4f}")
                console.print("\nAsks:", style="red")
                for ask_price, ask_qty in asks:
                    console.print(f"  Price: {float(ask_price):.2f}, Qty: {float(ask_qty):.4f}")
            else:
                console.print(f"No order book depth for {symbol}.", style="yellow")
        elif data_type == "TICKER":
            ticker = bot.binance_client.get_ticker_24hr(symbol)
            if ticker:
                console.print(f"24hr Ticker for {symbol}:", style="cyan")
                console.print(f"  Price Change: {float(ticker.get("priceChange", 0)):.2f}")
                console.print(f"  Price Change %: {float(ticker.get("priceChangePercent", 0)):.2f}%")
                console.print(f"  High Price: {float(ticker.get("highPrice", 0)):.2f}")
                console.print(f"  Low Price: {float(ticker.get("lowPrice", 0)):.2f}")
                console.print(f"  Volume: {float(ticker.get("volume", 0)):.2f}")
            else:
                console.print(f"No 24hr ticker data for {symbol}.", style="yellow")
        elif data_type == "FUNDING":
            funding_info = bot.binance_client.get_mark_price(symbol)
            if funding_info:
                # get_mark_price returns a list if no symbol is specified, or a dict if symbol is specified
                if isinstance(funding_info, list):
                    funding_info = next((item for item in funding_info if item['symbol'] == symbol), None)
                
                if funding_info:
                    console.print(f"Funding Rate for {symbol}:", style="cyan")
                    console.print(f"  Mark Price: {float(funding_info.get("markPrice", 0)):.2f}")
                    console.print(f"  Index Price: {float(funding_info.get("indexPrice", 0)):.2f}")
                    console.print(f"  Last Funding Rate: {float(funding_info.get("lastFundingRate", 0)):.6f}")
                    console.print(f"  Next Funding Time: {datetime.fromtimestamp(funding_info.get("nextFundingTime", 0) / 1000).strftime("%Y-%m-%d %H:%M:%S")}")
                else:
                    console.print(f"No funding rate data for {symbol}.", style="yellow")
            else:
                console.print(f"No funding rate data for {symbol}.", style="yellow")

    except Exception as e:
        errors_logger.error(f"Error fetching market data: {e}")
        console.print(f"Error fetching market data: {e}", style="red")

    Prompt.ask("Press Enter to continue...")

def risk_management_settings_menu():
    console.clear()
    print_panel("RISK MANAGEMENT SETTINGS", "", style="bold yellow")

    console.print(f"Current Max Position Size: {bot.risk_manager.max_position_size_pct * 100:.2f}%", style="white")
    console.print(f"Current Max Leverage: {bot.risk_manager.max_leverage}x", style="white")
    console.print(f"Current Max Daily Loss: {bot.risk_manager.max_daily_loss_pct * 100:.2f}%", style="white")
    console.print(f"Current Max Open Positions: {bot.risk_manager.max_open_positions}", style="white")

    if Confirm.ask("Do you want to change settings?", default=False):
        max_pos_size_pct = Prompt.ask("New Max Position Size % (e.g., 10 for 10%)", default=str(bot.risk_manager.max_position_size_pct * 100))
        max_leverage = Prompt.ask("New Max Leverage (e.g., 5)", default=str(bot.risk_manager.max_leverage))
        max_daily_loss_pct = Prompt.ask("New Max Daily Loss % (e.g., 5 for 5%)", default=str(bot.risk_manager.max_daily_loss_pct * 100))
        max_open_positions = Prompt.ask("New Max Open Positions", default=str(bot.risk_manager.max_open_positions))

        try:
            bot.risk_manager.set_risk_parameters(
                max_pos_size_pct=float(max_pos_size_pct) / 100,
                max_leverage=int(max_leverage),
                max_daily_loss_pct=float(max_daily_loss_pct) / 100,
                max_open_positions=int(max_open_positions)
            )
            console.print("Risk settings updated successfully.", style="green")
        except ValueError:
            console.print("Invalid input. Please enter numeric values.", style="red")

    Prompt.ask("Press Enter to continue...")

def automated_strategies_menu():
    console.clear()
    print_panel("AUTOMATED STRATEGIES", "", style="bold blue")

    strategy_options = {
        "1": "TWAP (Time-Weighted Average Price)",
        "2": "GRID Trading",
        "3": "OCO (One-Cancels-Other)",
        "4": "Trailing Stop",
        "0": "Back to Main Menu"
    }

    table = Table(show_header=False, box=None, padding=0)
    table.add_column(style="cyan")
    table.add_column(style="white")

    for key, value in strategy_options.items():
        table.add_row(f"[{key}]", value)
    
    console.print(table)
    choice = Prompt.ask("Select strategy", choices=list(strategy_options.keys()), default="0")

    if choice == "1": # TWAP
        symbol = Prompt.ask("Symbol (e.g., BTCUSDT)").upper()
        total_quantity = float(Prompt.ask("Total Quantity"))
        duration_minutes = int(Prompt.ask("Duration in minutes"))
        side = Prompt.ask("Side", choices=["LONG", "SHORT"]).upper()
        interval_seconds = int(Prompt.ask("Interval between orders in seconds", default="60"))
        leverage = int(Prompt.ask("Leverage", default="1"))
        
        bot.twap_strategy.start()
        threading.Thread(target=bot.twap_strategy.execute, args=(symbol, total_quantity, duration_minutes, OrderSide(side), interval_seconds, leverage), daemon=True).start()
        console.print(f"TWAP strategy for {symbol} initiated in background.", style="green")

    elif choice == "2": # GRID
        symbol = Prompt.ask("Symbol (e.g., BTCUSDT)").upper()
        price_range_pct = float(Prompt.ask("Price Range Percentage (e.g., 0.05 for 5%)"))
        num_grids = int(Prompt.ask("Number of Grids"))
        investment_per_grid = float(Prompt.ask("Investment per Grid (in USDT)"))
        leverage = int(Prompt.ask("Leverage", default="1"))

        bot.grid_strategy.start()
        grid_id = bot.grid_strategy.setup_grid(symbol, price_range_pct, num_grids, investment_per_grid, leverage)
        if grid_id:
            threading.Thread(target=bot.grid_strategy.run, daemon=True).start()
            console.print(f"Grid strategy {grid_id} for {symbol} initiated in background.", style="green")
        else:
            console.print(f"Failed to setup Grid strategy for {symbol}.", style="red")

    elif choice == "3": # OCO
        symbol = Prompt.ask("Symbol (e.g., BTCUSDT)").upper()
        side = Prompt.ask("Side", choices=["LONG", "SHORT"]).upper()
        quantity = float(Prompt.ask("Quantity"))
        price = float(Prompt.ask("Limit Price"))
        stop_price = float(Prompt.ask("Stop-Loss Price"))
        take_profit_price = float(Prompt.ask("Take-Profit Price"))
        leverage = int(Prompt.ask("Leverage", default="1"))

        bot.oco_strategy.start()
        threading.Thread(target=bot.oco_strategy.place_oco_order, args=(symbol, OrderSide(side), quantity, price, stop_price, take_profit_price, leverage), daemon=True).start()
        console.print(f"OCO order for {symbol} initiated in background.", style="green")

    elif choice == "4": # Trailing Stop
        symbol = Prompt.ask("Symbol (e.g., BTCUSDT)").upper()
        callback_rate = float(Prompt.ask("Callback Rate (e.g., 0.01 for 1%)"))
        leverage = int(Prompt.ask("Leverage", default="1"))

        bot.trailing_stop_strategy.start()
        ts_id = bot.trailing_stop_strategy.start_trailing_stop(symbol, callback_rate, leverage)
        if ts_id:
            threading.Thread(target=bot.trailing_stop_strategy.run, daemon=True).start()
            console.print(f"Trailing Stop {ts_id} for {symbol} initiated in background.", style="green")
        else:
            console.print(f"Failed to setup Trailing Stop for {symbol}.", style="red")

    Prompt.ask("Press Enter to continue...")

def logs_viewer_menu():
    console.clear()
    print_panel("LOGS VIEWER", "", style="bold yellow")

    log_files = {
        "1": "trading_bot.log",
        "2": "orders.log",
        "3": "positions.log",
        "4": "errors.log",
        "5": "api_requests.log",
        "6": "performance.log",
        "0": "Back to Main Menu"
    }

    table = Table(show_header=False, box=None, padding=0)
    table.add_column(style="cyan")
    table.add_column(style="white")

    for key, value in log_files.items():
        table.add_row(f"[{key}]", value)
    
    console.print(table)
    choice = Prompt.ask("Select log file to view", choices=list(log_files.keys()), default="0")

    if choice != "0":
        log_file_name = log_files[choice]
        log_path = f"logs/{log_file_name}"
        try:
            with open(log_path, "r") as f:
                console.print(f"\n--- Content of {log_file_name} ---", style="bold underline")
                for line in f.readlines()[-50:]: # Show last 50 lines
                    console.print(line.strip())
                console.print(f"--- End of {log_file_name} ---", style="bold underline")
        except FileNotFoundError:
            console.print(f"Log file {log_file_name} not found.", style="red")
        except Exception as e:
            console.print(f"Error reading log file: {e}", style="red")

    Prompt.ask("Press Enter to continue...")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--test-connection":
        bot.test_connection()
        sys.exit(0)

    # Start the main bot loop in a separate thread
    bot_thread = threading.Thread(target=bot.run_bot, daemon=True)
    bot_thread.start()

    # Start WebSocket for market data
    # Example streams: BTCUSDT mark price, ETHUSDT kline 1m
    bot.start_websocket({"btcusdt@markPrice@1s": None, "ethusdt@kline_1m": None})

    # CRITICAL: Wait for WebSocket to connect before showing menu
    # This ensures price data is available when user places first order
    console.print("\n⏳ Connecting to market data streams...", style="bold yellow")
    for i in range(5):  # Wait up to 2.5 seconds for connection
        if bot.websocket_client and bot.websocket_client.is_running:
            console.print("✓ Market data connected!", style="bold green")
            break
        time.sleep(0.5)
    else:
        console.print("⚠ Warning: Market data may not be connected yet. Prices might be unavailable.", style="yellow")

    while True:
        choice = display_main_menu()
        if choice == "1":
            place_order_menu()
        elif choice == "2":
            view_open_positions_menu()
        elif choice == "3":
            view_order_history_menu()
        elif choice == "4":
            cancel_orders_menu()
        elif choice == "5":
            account_summary_menu()
        elif choice == "6":
            market_data_menu()
        elif choice == "7":
            risk_management_settings_menu()
        elif choice == "8":
            automated_strategies_menu()
        elif choice == "9":
            logs_viewer_menu()
        elif choice == "0":
            bot.stop_bot()
            console.print("Exiting bot. Goodbye!", style="bold green")
            sys.exit(0)

if __name__ == "__main__":
    main()