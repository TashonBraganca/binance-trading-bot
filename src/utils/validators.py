import re

def is_valid_symbol(symbol: str) -> bool:
    """Validates if a string is a valid Binance symbol format (e.g., BTCUSDT)."""
    return bool(re.fullmatch(r"^[A-Z0-9]{5,15}$", symbol))

def is_positive_number(value) -> bool:
    """Checks if a value is a positive number."""
    try:
        return float(value) > 0
    except (ValueError, TypeError):
        return False

def is_valid_price(price) -> bool:
    """Checks if a price is a positive number."""
    return is_positive_number(price)

def is_valid_quantity(quantity) -> bool:
    """Checks if a quantity is a positive number."""
    return is_positive_number(quantity)

def is_valid_leverage(leverage: int) -> bool:
    """Checks if leverage is within a reasonable range (e.g., 1 to 125)."""
    return 1 <= leverage <= 125

def is_valid_percentage(percentage: float) -> bool:
    """Checks if a value is a valid percentage (0 to 100)."""
    return 0 <= percentage <= 100