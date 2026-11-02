"""
Logging configuration for the application.
"""

import logging
import sys
from pathlib import Path
from app.config import get_config


def setup_logging():
    """Configure application logging."""
    config = get_config()
    
    # Create logs directory
    config.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(config.LOG_LEVEL)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler
    file_handler = logging.FileHandler(config.LOG_FILE)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)
