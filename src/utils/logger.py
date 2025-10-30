import logging
from logging.handlers import RotatingFileHandler
import os
from rich.console import Console
from rich.logging import RichHandler

# Ensure logs directory exists
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Console for rich logging
console = Console()

def setup_logging():
    # Base logger configuration
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            RichHandler(console=console, show_time=True, show_level=True, show_path=False, enable_link_path=False)
        ]
    )

    # Create specific loggers
    main_logger = logging.getLogger("trading_bot")
    orders_logger = logging.getLogger("orders")
    positions_logger = logging.getLogger("positions")
    errors_logger = logging.getLogger("errors")
    api_requests_logger = logging.getLogger("api_requests")
    performance_logger = logging.getLogger("performance")

    # Set levels for specific loggers (can be overridden by handlers)
    main_logger.setLevel(logging.INFO)
    orders_logger.setLevel(logging.INFO)
    positions_logger.setLevel(logging.INFO)
    errors_logger.setLevel(logging.ERROR)
    api_requests_logger.setLevel(logging.DEBUG)
    performance_logger.setLevel(logging.INFO)

    # Define a common formatter for file handlers
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Add rotating file handlers for each specific log file
    def add_rotating_file_handler(logger, filename, level=logging.INFO):
        file_handler = RotatingFileHandler(
            os.path.join(LOG_DIR, filename),
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

    add_rotating_file_handler(main_logger, "trading_bot.log", logging.INFO)
    add_rotating_file_handler(orders_logger, "orders.log", logging.INFO)
    add_rotating_file_handler(positions_logger, "positions.log", logging.INFO)
    add_rotating_file_handler(errors_logger, "errors.log", logging.ERROR)
    add_rotating_file_handler(api_requests_logger, "api_requests.log", logging.DEBUG)
    add_rotating_file_handler(performance_logger, "performance.log", logging.INFO)

    # Prevent log messages from being propagated to the root logger multiple times
    main_logger.propagate = False
    orders_logger.propagate = False
    positions_logger.propagate = False
    errors_logger.propagate = False
    api_requests_logger.propagate = False
    performance_logger.propagate = False

# Call setup_logging once to configure all loggers
setup_logging()

# Export specific loggers for use throughout the application
main_logger = logging.getLogger("trading_bot")
orders_logger = logging.getLogger("orders")
positions_logger = logging.getLogger("positions")
errors_logger = logging.getLogger("errors")
api_requests_logger = logging.getLogger("api_requests")
performance_logger = logging.getLogger("performance")