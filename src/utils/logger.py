
import logging
import os
from logging.handlers import RotatingFileHandler
import colorlog
from src.config.settings import settings

def setup_logging():
    """Sets up the logging configuration for the application."""
    if not os.path.exists(settings.LOGS_DIR):
        os.makedirs(settings.LOGS_DIR)

    # General application logger
    app_logger = logging.getLogger("trading_bot")
    app_logger.setLevel(logging.DEBUG)
    app_handler = RotatingFileHandler(
        settings.APP_LOG_FILE,
        maxBytes=settings.LOG_ROTATION_MAX_BYTES,
        backupCount=settings.LOG_ROTATION_BACKUP_COUNT
    )
    app_formatter = logging.Formatter(settings.LOG_FORMAT)
    app_handler.setFormatter(app_formatter)
    app_logger.addHandler(app_handler)

    # Console logger with colors
    console_handler = colorlog.StreamHandler()
    console_handler.setFormatter(colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
    ))
    console_handler.setLevel(logging.INFO)
    app_logger.addHandler(console_handler)

    # Specific loggers
    loggers = {
        "orders": settings.ORDERS_LOG_FILE,
        "positions": settings.POSITIONS_LOG_FILE,
        "errors": settings.ERRORS_LOG_FILE,
        "api_requests": settings.API_REQUESTS_LOG_FILE,
        "performance": settings.PERFORMANCE_LOG_FILE,
    }

    for name, log_file in loggers.items():
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        if name == 'api_requests':
            logger.setLevel(logging.DEBUG)
        elif name == 'errors':
            logger.setLevel(logging.ERROR)
        
        handler = RotatingFileHandler(
            log_file,
            maxBytes=settings.LOG_ROTATION_MAX_BYTES,
            backupCount=settings.LOG_ROTATION_BACKUP_COUNT
        )
        formatter = logging.Formatter(settings.LOG_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False # Prevent duplication to app_logger

# Initialize logging
setup_logging()

# Get specific loggers
app_log = logging.getLogger("trading_bot")
orders_log = logging.getLogger("orders")
positions_log = logging.getLogger("positions")
errors_log = logging.getLogger("errors")
api_log = logging.getLogger("api_requests")
performance_log = logging.getLogger("performance")
