"""
Logging configuration for the Pokemon Discord Bot.
"""
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Dict, Any

from .environment import Environment
from .config_manager import config


def configure_logging() -> logging.Logger:
    """Configure logging based on environment and configuration."""
    # Get logging configuration
    log_config = config.get_logging_config()
    log_level_str = log_config.get('level', Environment.get_log_level())
    log_format = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Convert string log level to logging constant
    try:
        log_level = getattr(logging, log_level_str.upper())
    except (AttributeError, TypeError):
        log_level = logging.INFO
        print(f"Invalid log level: {log_level_str}, using INFO")
    
    # Create logs directory if it doesn't exist
    logs_dir = Environment.get_logs_dir()
    log_file = logs_dir / log_config.get('file_path', 'pokemon_bot.log')
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add rotating file handler with UTF-8 encoding
    max_bytes = log_config.get('max_file_size', 10485760)  # 10MB
    backup_count = log_config.get('backup_count', 5)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(file_handler)
    
    # Add console handler with appropriate level
    console_level = log_level
    if Environment.is_production():
        # In production, only show warnings and above in console
        console_level = max(log_level, logging.WARNING)
    
    # Create console handler with UTF-8 encoding for Windows compatibility
    import io
    if sys.platform.startswith('win'):
        # On Windows, wrap stdout to handle Unicode properly
        console_stream = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    else:
        console_stream = sys.stdout
    
    console_handler = logging.StreamHandler(console_stream)
    console_handler.setLevel(console_level)
    
    # Create a formatter that replaces problematic Unicode characters
    class SafeFormatter(logging.Formatter):
        def format(self, record):
            # Replace emoji and special Unicode characters with safe alternatives
            formatted = super().format(record)
            if sys.platform.startswith('win'):
                # Replace common emoji with text equivalents
                replacements = {
                    '🚀': '[ROCKET]',
                    '📊': '[CHART]',
                    '🔍': '[SEARCH]',
                    '📦': '[PACKAGE]',
                    '✅': '[CHECK]',
                    '❌': '[X]',
                    '⚠️': '[WARNING]',
                    '🔄': '[REFRESH]',
                    '💰': '[MONEY]',
                    '📈': '[TRENDING_UP]',
                    '📉': '[TRENDING_DOWN]',
                    '🎯': '[TARGET]',
                    '⏰': '[CLOCK]',
                    '🔔': '[BELL]',
                    '🛒': '[CART]',
                    '💎': '[DIAMOND]',
                    '⭐': '[STAR]',
                    '🎮': '[GAME]',
                    '🃏': '[CARD]',
                    '🎲': '[DICE]'
                }
                for emoji, replacement in replacements.items():
                    formatted = formatted.replace(emoji, replacement)
            return formatted
    
    console_handler.setFormatter(SafeFormatter(log_format))
    root_logger.addHandler(console_handler)
    
    # Get application logger
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized at level {log_level_str}")
    
    # Log environment information
    logger.info(f"Environment: {Environment.get_env()}")
    logger.info(f"Data directory: {Environment.get_data_dir()}")
    logger.info(f"Logs directory: {Environment.get_logs_dir()}")
    logger.info(f"Config directory: {Environment.get_config_dir()}")
    
    return logger


def get_logging_config_dict() -> Dict[str, Any]:
    """Get logging configuration as a dictionary for logging.config.dictConfig."""
    log_config = config.get_logging_config()
    log_level = log_config.get('level', 'INFO').upper()
    log_format = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create logs directory if it doesn't exist
    logs_dir = Environment.get_logs_dir()
    log_file = logs_dir / log_config.get('file_path', 'pokemon_bot.log')
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure console level based on environment
    console_level = log_level
    if Environment.is_production():
        console_level = 'WARNING'
    
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': log_format
            },
        },
        'handlers': {
            'console': {
                'level': console_level,
                'formatter': 'standard',
                'class': 'logging.StreamHandler',
                'stream': 'ext://sys.stdout',
            },
            'file': {
                'level': log_level,
                'formatter': 'standard',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': str(log_file),
                'maxBytes': log_config.get('max_file_size', 10485760),
                'backupCount': log_config.get('backup_count', 5),
            },
        },
        'loggers': {
            '': {  # root logger
                'handlers': ['console', 'file'],
                'level': log_level,
                'propagate': True
            },
            'discord': {
                'handlers': ['console', 'file'],
                'level': log_level,
                'propagate': False
            },
            'aiohttp': {
                'handlers': ['console', 'file'],
                'level': 'WARNING',
                'propagate': False
            },
        }
    }