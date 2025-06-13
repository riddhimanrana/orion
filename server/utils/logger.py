import logging
import logging.config
import sys
from pathlib import Path
from typing import Optional

import structlog
from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install as install_rich_traceback
from pythonjsonlogger import jsonlogger

from config import settings

# Install rich traceback handler
install_rich_traceback()

# Create console instance
console = Console()

def setup_logger(
    level: str = "INFO",
    log_file: Optional[str] = None,
    json_format: bool = False
) -> None:
    """
    Setup application logging with rich formatting and structured logging support.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path to write logs to
        json_format: Whether to output logs in JSON format (useful for log aggregation)
    """
    # Create logs directory if needed
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure structlog
    structlog.configure(
        processors=[
            # Add log level to event dict
            structlog.stdlib.add_log_level,
            # Add logger name
            structlog.stdlib.add_logger_name,
            # Add timestamps
            structlog.processors.TimeStamper(fmt="iso"),
            # Add stack info for errors
            structlog.processors.StackInfoRenderer(),
            # Format exceptions
            structlog.processors.format_exc_info,
            # Handle any bytes/unicode issues
            structlog.processors.UnicodeDecoder(),
            # Prepare for formatting
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        # Use standard library's logger
        logger_factory=structlog.stdlib.LoggerFactory(),
        # Wrapper class for logger instances
        wrapper_class=structlog.stdlib.BoundLogger,
        # Cache logger on first use
        cache_logger_on_first_use=True,
    )
    
    # Setup logging config
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            # "rich" formatter is not needed when using RichHandler directly,
            # as RichHandler handles its own formatting.
            # If a standard formatter were to be used with RichHandler (uncommon),
            # it would be a standard Python logging formatter.
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "fmt": "%(asctime)s %(name)s %(levelname)s %(message)s",
            }
        },
        "handlers": {
            # Define console handler based on json_format
        },
        "root": {
            "level": level,
            "handlers": [], # Will be populated based on conditions
        }
    }

    if json_format:
        logging_config["handlers"]["console"] = {
            "class": "logging.StreamHandler", # Use standard StreamHandler for JSON
            "formatter": "json",
            "level": level,
            "stream": "ext://sys.stdout" # Explicitly to stdout
        }
    else:
        logging_config["handlers"]["console"] = {
            "class": "rich.logging.RichHandler",
            "rich_tracebacks": True,
            "tracebacks_show_locals": True,
            "markup": True,
            "level": level,
            "show_time": True, # RichHandler specific
            "show_path": True   # RichHandler specific
            # No 'formatter' key needed for RichHandler
        }
    logging_config["root"]["handlers"].append("console")
    
    # Add file handler if log file specified
    if log_file:
        file_formatter = "json" if json_format else "standard" # Let's add a standard formatter for non-JSON file logs
        if "standard" not in logging_config["formatters"]:
             logging_config["formatters"]["standard"] = {
                 "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
             }

        logging_config["handlers"]["file"] = {
            "class": "logging.FileHandler",
            "filename": log_file,
            "formatter": file_formatter,
            "level": level,
        }
        logging_config["root"]["handlers"].append("file")
    
    # Apply logging configuration
    logging.config.dictConfig(logging_config)
    
    # Create logger instance
    logger = structlog.get_logger(__name__)
    
    # Log startup message
    logger.info(
        "Logger initialized",
        level=level,
        log_file=log_file,
        json_format=json_format,
        settings={
            "LOG_LEVEL": settings.LOG_LEVEL,
            "DEBUG": settings.DEBUG
        }
    )

def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (usually __name__ of the module)
        
    Returns:
        A structured logger instance
    """
    return structlog.get_logger(name)

# Default logger for direct imports
logger = get_logger(__name__)

# Configure default exception hook
def handle_exception(exc_type, exc_value, exc_traceback):
    """Custom exception handler that ensures exceptions are properly logged."""
    if issubclass(exc_type, KeyboardInterrupt):
        # Call default handler for KeyboardInterrupt
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
        
    logger.error(
        "Uncaught exception",
        exc_info=(exc_type, exc_value, exc_traceback)
    )

# Install exception handler
sys.excepthook = handle_exception