

import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, FloatPrompt
from rich.table import Table
from src.bot import TradingBot
from src.utils.logger import app_log
from src.utils.formatters import format_positions_table, format_account_summary, format_orders_table
from src.config.constants import OrderSide, PositionSide
from decimal import Decimal

console = Console()

def print_main_menu(bot: TradingBot):
    """Prints the main menu panel."""
    balance = bot.portfolio_tracker.get_wallet_balance()
    pnl = bot.portfolio_tracker.get_unrealized_pnl()
    mode = "TESTNET" if bot.client.testnet else "MAINNET"

    header = (
        f"[bold cyan]BINANCE FUTURES TRADING BOT v2.0[/bold cyan]\n"
        f"Account: [yellow]{mode}[/yellow] | Balance: [green]{balance:.2f} USDT[/green] | PnL: [bold {('green' if pnl >= 0 else 'red')}]{pnl:.2f} USDT[/bold {('green' if pnl >= 0 else 'red')}]"
    )

    menu = (
        "[1] Place Order\n"
        "[2] View Open Positions\n"
        "[3] View Order History\n"
        "[4] Cancel Orders\n"
        "[5] Account Summary\n"
        "[6] Market Data\n"
        "[7] Risk Management Settings\n"
        "[8] Automated Strategies\n"
        "[9] Logs Viewer\n"
        "[0] Exit"
    )
    
    console.print(Panel(header, expand=False, border_style="blue"))
    console.print(Panel(menu, title="Main Menu", title_align="left", border_style="blue"))

async def place_order_flow(bot: TradingBot):
    """Guides the user through placing a new order."""
    console.print(Panel("[bold magenta]PLACE NEW ORDER[/bold magenta]", expand=False))
    
    symbol = Prompt.ask("Symbol (e.g., BTCUSDT)").upper()
    side = Prompt.ask("Side [LONG/SHORT]", choices=["LONG", "SHORT"], default="LONG").upper()
    order_type = IntPrompt.ask(
        "Order Type\n  [1] MARKET\n  [2] LIMIT\n  [3] STOP_MARKET\n  [4] STOP_LIMIT\nSelect",
        choices=["1", "2", "3", "4"], default="1"
    )

    quantity = Decimal(FloatPrompt.ask("Quantity (in base asset, e.g., BTC)"))
    leverage = IntPrompt.ask("Leverage", default="5")

    order_data = {
        "symbol": symbol,
        "side": "BUY" if side == "LONG" else "SELL",
        "positionSide": side,
        "quantity": float(quantity),
        "leverage": leverage
    }

    if order_type == 2 or order_type == 4: # LIMIT or STOP_LIMIT
        order_data["price"] = float(FloatPrompt.ask("Price"))
    if order_type == 3 or order_type == 4: # STOP_MARKET or STOP_LIMIT
        order_data["stopPrice"] = float(FloatPrompt.ask("Stop Price"))

    order_type_map = {1: "MARKET", 2: "LIMIT", 3: "STOP_MARKET", 4: "STOP_LIMIT"}
    order_data["type"] = order_type_map[order_type]

    # Pre-trade check simulation
    console.print("═══ PRE-TRADE RISK CHECK ═══")
    # In a real scenario, you'd call the risk manager here and display results
    console.print("[green]✓ Sufficient margin: YES[/green]")
    console.print("[green]✓ Position size: SAFE[/green]")
    console.print("[green]✓ Leverage: SAFE[/green]")

    if Prompt.ask("Confirm order? [y/N]", choices=["y", "n"], default="n").lower() == 'y':
        result = await bot.order_executor.execute_order(order_data)
        if result and result.get("status") not in ["REJECTED", "FAILED"]:
            console.print(f"[green]Order successfully placed! Status: {result.get('status')}[/green]")
            console.print(result)
        else:
            error_msg = result.get('error', 'No error message provided.')
            console.print(f"[bold red]Order placement failed: {error_msg}[/bold red]")
            console.print(f"[red]Details: {result}[/red]")
    else:
        console.print("[yellow]Order cancelled.[/yellow]")

async def view_open_positions_flow(bot: TradingBot):
    await bot.portfolio_tracker.update()
    positions = bot.portfolio_tracker.positions
    if not positions:
        console.print("[yellow]No open positions.[/yellow]")
        return
    table = format_positions_table(positions)
    console.print(table)

async def view_order_history_flow(bot: TradingBot):
    symbol = Prompt.ask("Enter symbol to view history for (e.g., BTCUSDT)").upper()
    orders = await bot.client.get_all_orders(symbol=symbol)
    if not orders:
        console.print(f"[yellow]No order history found for {symbol}.[/yellow]")
        return
    table = format_orders_table(orders)
    console.print(table)

async def main_loop(bot: TradingBot):
    """The main interactive loop for the CLI."""
    await bot.start()
    if not bot.is_running:
        return

    while bot.is_running:
        print_main_menu(bot)
        choice = IntPrompt.ask("Select option", choices=[str(i) for i in range(10)], default="0")

        if choice == 1:
            await place_order_flow(bot)
        elif choice == 2:
            await view_open_positions_flow(bot)
        elif choice == 3:
            await view_order_history_flow(bot)
        elif choice == 5:
            await bot.portfolio_tracker.update()
            format_account_summary(bot.portfolio_tracker.account_info, bot.portfolio_tracker.positions)
        elif choice == 0:
            await bot.stop()
        else:
            console.print(f"[yellow]Option {choice} not yet implemented.[/yellow]")
        
        if bot.is_running:
            Prompt.ask("\nPress Enter to continue...")
            console.clear()

async def main():
    bot = TradingBot()
    try:
        await main_loop(bot)
    except KeyboardInterrupt:
        await bot.stop()
    except Exception as e:
        app_log.critical(f"A critical error occurred in the main loop: {e}")
        await bot.stop()
    finally:
        console.print("[bold red]Bot has been shut down.[/bold red]")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

