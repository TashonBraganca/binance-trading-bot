"""
Real-time Trading Dashboard with Live Price Updates
Displays positions, P&L, and price movements with 15-second refresh
"""
import time
import threading
from typing import Dict, List, Any, Optional
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from src.client.binance_client import BinanceClient
from src.portfolio.tracker import PortfolioTracker
from src.utils.logger import main_logger

class TradingDashboard:
    def __init__(self, binance_client: BinanceClient, portfolio_tracker: PortfolioTracker):
        self.binance_client = binance_client
        self.portfolio_tracker = portfolio_tracker
        self.console = Console()

        # Cache prices with 15-second TTL
        self._price_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 15  # 15 seconds

        # Dashboard state
        self.is_running = False
        self.last_update = 0
        self.update_interval = 15  # 15 seconds

    def get_current_price(self, symbol: str) -> float:
        """Get cached price or fetch fresh one."""
        current_time = time.time()

        # Check cache
        if symbol in self._price_cache:
            cached = self._price_cache[symbol]
            if current_time - cached["timestamp"] < self._cache_ttl:
                return cached["price"]

        # Fetch fresh price
        try:
            ticker = self.binance_client.get_ticker_24hr(symbol)
            price = float(ticker.get("lastPrice", 0.0))

            # Cache it
            if price > 0:
                self._price_cache[symbol] = {"price": price, "timestamp": current_time}

            return price
        except Exception as e:
            main_logger.warning(f"Could not fetch price for {symbol}: {e}")
            return 0.0

    def calculate_pnl(self, position: Dict[str, Any], current_price: float) -> tuple:
        """Calculate profit/loss for a position.

        Returns:
            (pnl_amount, pnl_percent, status_color)
        """
        entry_price = float(position.get("entry_price", 0.0))
        quantity = float(position.get("quantity", 0.0))
        side = position.get("side", "BUY")

        if entry_price == 0 or quantity == 0:
            return 0.0, 0.0, "white"

        if side == "BUY":
            pnl_amount = (current_price - entry_price) * quantity
        else:  # SELL
            pnl_amount = (entry_price - current_price) * quantity

        pnl_percent = (pnl_amount / (entry_price * quantity)) * 100 if entry_price != 0 else 0

        # Color based on P&L
        if pnl_percent > 0:
            status_color = "green"
        elif pnl_percent < 0:
            status_color = "red"
        else:
            status_color = "yellow"

        return pnl_amount, pnl_percent, status_color

    def build_positions_table(self) -> Table:
        """Build Rich table showing all open positions."""
        table = Table(title="📊 Live Trading Positions", show_header=True, header_style="bold cyan")

        table.add_column("Symbol", style="cyan")
        table.add_column("Side", style="magenta")
        table.add_column("Qty", justify="right")
        table.add_column("Entry Price", justify="right", style="yellow")
        table.add_column("Current Price", justify="right", style="cyan")
        table.add_column("P&L $", justify="right")
        table.add_column("P&L %", justify="right")
        table.add_column("Stop Loss", justify="right")
        table.add_column("Take Profit", justify="right")
        table.add_column("Status", justify="center")

        positions = self.portfolio_tracker.get_open_positions_list()

        if not positions:
            table.add_row("—", "—", "—", "—", "—", "—", "—", "—", "—", "No open positions")
            return table

        total_pnl = 0.0
        total_pnl_percent = 0.0

        for pos in positions:
            symbol = pos.get("symbol", "N/A")
            side = pos.get("side", "N/A")
            qty = float(pos.get("quantity", 0.0))
            entry_price = float(pos.get("entry_price", 0.0))
            stop_loss = float(pos.get("stop_loss", 0.0))
            take_profit = float(pos.get("take_profit", 0.0))

            # Get current price
            current_price = self.get_current_price(symbol)

            # Calculate P&L
            pnl_amount, pnl_percent, pnl_color = self.calculate_pnl(pos, current_price)
            total_pnl += pnl_amount
            total_pnl_percent += pnl_percent

            # Format values
            qty_str = f"{qty:.8f}".rstrip('0').rstrip('.')
            entry_str = f"${entry_price:.2f}"
            current_str = f"${current_price:.2f}"
            pnl_str = f"${pnl_amount:+.2f}"
            pnl_pct_str = f"{pnl_percent:+.2f}%"
            stop_str = f"${stop_loss:.2f}" if stop_loss > 0 else "—"
            tp_str = f"${take_profit:.2f}" if take_profit > 0 else "—"

            # Status indicator
            if pnl_percent > 5:
                status = "🟢 Strong"
            elif pnl_percent > 0:
                status = "🟢 Up"
            elif pnl_percent < -5:
                status = "🔴 Risk"
            elif pnl_percent < 0:
                status = "🔴 Down"
            else:
                status = "🟡 Flat"

            table.add_row(
                symbol,
                side,
                qty_str,
                entry_str,
                current_str,
                Text(pnl_str, style=pnl_color),
                Text(pnl_pct_str, style=pnl_color),
                stop_str,
                tp_str,
                status
            )

        return table

    def build_stats_panel(self) -> Panel:
        """Build summary statistics panel."""
        positions = self.portfolio_tracker.get_open_positions_list()

        total_pnl = 0.0
        total_positions = len(positions)
        winning_positions = 0
        losing_positions = 0

        for pos in positions:
            current_price = self.get_current_price(pos.get("symbol", ""))
            pnl_amount, pnl_percent, _ = self.calculate_pnl(pos, current_price)
            total_pnl += pnl_amount

            if pnl_percent > 0:
                winning_positions += 1
            elif pnl_percent < 0:
                losing_positions += 1

        # Color total P&L
        pnl_color = "green" if total_pnl > 0 else "red" if total_pnl < 0 else "yellow"

        stats_text = f"""
[bold cyan]Portfolio Summary[/bold cyan]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Positions:     {total_positions}
Winning:             {winning_positions}
Losing:              {losing_positions}
Total P&L:           [{pnl_color}]${total_pnl:+.2f}[/{pnl_color}]
Last Update:         {datetime.now().strftime('%H:%M:%S')}
Cache TTL:           {self._cache_ttl}s
"""

        return Panel(stats_text, border_style="cyan", expand=False)

    def display(self) -> None:
        """Display the live dashboard."""
        self.console.clear()
        self.console.print(Panel(
            "[bold magenta]🤖 Binance Trading Bot - Real-Time Dashboard[/bold magenta]",
            border_style="magenta"
        ))

        # Show positions table
        positions_table = self.build_positions_table()
        self.console.print(positions_table)

        # Show stats
        stats_panel = self.build_stats_panel()
        self.console.print(stats_panel)

        # Update timestamp
        self.last_update = time.time()

    def should_update(self) -> bool:
        """Check if enough time has passed for update."""
        return time.time() - self.last_update >= self.update_interval

    def run_interactive(self, duration: int = None) -> None:
        """Run dashboard for specified duration (or until interrupted)."""
        self.is_running = True
        start_time = time.time()

        try:
            while self.is_running:
                self.display()

                # Check for exit condition
                if duration and (time.time() - start_time) > duration:
                    break

                # Wait for next update
                time.sleep(self.update_interval)
        except KeyboardInterrupt:
            self.console.print("[yellow]Dashboard stopped by user[/yellow]")
        finally:
            self.is_running = False

    def stop(self) -> None:
        """Stop the dashboard."""
        self.is_running = False
