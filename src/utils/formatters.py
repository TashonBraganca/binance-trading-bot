
from rich.table import Table
from rich.console import Console
from rich.panel import Panel
import pandas as pd

console = Console()

def format_positions_table(positions: list[dict]) -> Table:
    """Formats a list of position dictionaries into a Rich table."""
    table = Table(title="Open Positions", show_header=True, header_style="bold magenta")
    table.add_column("Symbol", style="cyan", no_wrap=True)
    table.add_column("Side", style="green")
    table.add_column("Size")
    table.add_column("Entry Price", justify="right", style="yellow")
    table.add_column("Mark Price", justify="right", style="yellow")
    table.add_column("Unrealized PnL", justify="right")
    table.add_column("Leverage", justify="right")
    table.add_column("Margin Type", justify="right")

    total_pnl = 0
    for pos in positions:
        pnl = float(pos.get('unRealizedProfit', 0))
        total_pnl += pnl
        pnl_style = "green" if pnl >= 0 else "red"
        table.add_row(
            pos.get('symbol'),
            pos.get('positionSide'),
            pos.get('positionAmt'),
            f"{float(pos.get('entryPrice', 0)):.4f}",
            f"{float(pos.get('markPrice', 0)):.4f}",
            f"[{pnl_style}]{pnl:.2f} USDT[/{pnl_style}]",
            f"{pos.get('leverage')}x",
            pos.get('marginType').capitalize(),
        )
    
    pnl_style = "green" if total_pnl >= 0 else "red"
    console.print(Panel(f"Total Unrealized PnL: [{pnl_style}]{total_pnl:.2f} USDT[/{pnl_style}]", expand=False))
    return table

def format_account_summary(account_info: dict, positions: list[dict]):
    """Formats the account summary into a Rich panel."""
    balance = float(account_info.get('totalWalletBalance', 0))
    pnl = float(account_info.get('totalUnrealizedProfit', 0))
    
    summary = (
        f"[bold]Wallet Balance:[/] {balance:.2f} USDT\n"
        f"[bold]Unrealized PNL:[/] {pnl:.2f} USDT\n"
        f"[bold]Total Equity:[/] {(balance + pnl):.2f} USDT\n"
        f"[bold]Available Balance:[/] {float(account_info.get('availableBalance', 0)):.2f} USDT\n"
        f"[bold]Open Positions:[/] {len(positions)}"
    )
    
    console.print(Panel(summary, title="Account Summary", border_style="green"))

def format_orders_table(orders: list[dict]) -> Table:
    """Formats a list of order dictionaries into a Rich table."""
    table = Table(title="Order History", show_header=True, header_style="bold magenta")
    table.add_column("Symbol", style="cyan")
    table.add_column("Order ID")
    table.add_column("Side")
    table.add_column("Type")
    table.add_column("Quantity", justify="right")
    table.add_column("Price", justify="right")
    table.add_column("Status")
    table.add_column("Time", style="dim")

    for order in orders:
        table.add_row(
            order.get('symbol'),
            str(order.get('orderId')),
            order.get('side'),
            order.get('type'),
            f"{float(order.get('origQty', 0)):.4f}",
            f"{float(order.get('price', 0)):.2f}",
            order.get('status'),
            pd.to_datetime(order.get('time'), unit='ms').strftime('%Y-%m-%d %H:%M:%S')
        )
    return table
