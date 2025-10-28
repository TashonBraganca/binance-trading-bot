
import re

def is_valid_symbol(symbol: str) -> bool:
    """Check if a symbol is in the valid format (e.g., BTCUSDT)."""
    return re.match(r'^[A-Z]{3,}[A-Z]{3,}$', symbol) is not None

def is_positive_float(value: str) -> bool:
    """Check if a string can be converted to a positive float."""
    try:
        return float(value) > 0
    except (ValueError, TypeError):
        return False

def is_positive_integer(value: str) -> bool:
    """Check if a string can be converted to a positive integer."""
    try:
        return int(value) > 0
    except (ValueError, TypeError):
        return False
