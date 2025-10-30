from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()

def print_panel(title: str, content: str, style: str = "blue"):
    """Prints content within a rich Panel."""
    console.print(Panel(content, title=title, border_style=style))

def print_table(title: str, columns: list, rows: list, style: str = "blue"):
    """Prints data in a rich Table format."""
    table = Table(title=title, style=style, header_style=style)
    for col in columns:
        table.add_column(col, justify="left", style="cyan", no_wrap=True)
    for row in rows:
        table.add_row(*[str(item) for item in row])
    console.print(table)

def format_pnl(pnl: float) -> Text:
    """Formats PnL with color based on positive/negative value."""
    if pnl > 0:
        return Text(f"+{pnl:.2f} USDT", style="green")
    elif pnl < 0:
        return Text(f"{pnl:.2f} USDT", style="red")
    else:
        return Text(f"{pnl:.2f} USDT", style="white")

def format_percentage(value: float) -> Text:
    """Formats a percentage with color based on positive/negative value."""
    if value > 0:
        return Text(f"+{value:.2f}%", style="green")
    elif value < 0:
        return Text(f"{value:.2f}%", style="red")
    else:
        return Text(f"{value:.2f}%", style="white")

def format_currency(value: float, currency: str = "USDT") -> str:
    """Formats a float as a currency string."""
    return f"{value:,.2f} {currency}"