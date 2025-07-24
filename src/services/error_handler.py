"""
Comprehensive error handling and logging system for the Pokemon Discord Bot.

This module provides centralized error handling with categorized error processing,
structured error reporting, and recovery mechanisms for various types of failures.
"""
import logging
import traceback
import json
import asyncio
import time
import socket
import sqlite3
import aiohttp
from typing import Dict, Any, Optional, List, Tuple, Callable, Awaitable
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum

from ..models.interfaces import IErrorHandler
from ..models.product_data import Notification
from ..config.config_manager import config
from ..config.environment import Environment
from ..database.connection import db


class ErrorCategory(Enum):
    """Error categories for classification and handling."""
    NETWORK = "network"
    DISCORD = "discord"
    DATABASE = "database"
    PARSING = "parsing"
    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    VALIDATION = "validation"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Error severity levels for prioritization."""
    CRITICAL = "critical"  # System cannot function, requires immediate attention
    HIGH = "high"          # Major feature broken, requires urgent attention
    MEDIUM = "medium"      # Feature degraded but working, needs attention soon
    LOW = "low"            # Minor issue, can be addressed later
    INFO = "info"          # Informational only, no action required


class ErrorHandler(IErrorHandler):
    """Centralized error handling and recovery system."""
    
    def __init__(self):
        """Initialize error handler."""
        self.logger = self._setup_logger()
        self._error_counts: Dict[str, int] = {}
        self._last_errors: Dict[str, Dict[str, Any]] = {}
        self._recovery_in_progress: Dict[str, bool] = {}
        self._error_callbacks: Dict[ErrorCategory, List[Callable]] = {}
        self._setup_error_callbacks()
        
        # Health check status
        self._health_status = {
            "status": "healthy",
            "last_check": datetime.utcnow().isoformat(),
            "components": {
                "network": {"status": "healthy", "last_error": None},
                "discord": {"status": "healthy", "last_error": None},
                "database": {"status": "healthy", "last_error": None},
                "monitoring": {"status": "healthy", "last_error": None}
            }
        }
    
    def _setup_logger(self) -> logging.Logger:
        """Set up structured logging."""
        logger = logging.getLogger("error_handler")
        
        # Get logging configuration
        log_config = config.get_logging_config()
        log_level = getattr(logging, log_config.get('level', 'INFO'))
        log_format = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        log_file = log_config.get('file_path', 'logs/pokemon_bot.log')
        max_size = log_config.get('max_file_size', 10485760)  # 10MB
        backup_count = log_config.get('backup_count', 5)
        
        # Create logs directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Configure logger
        logger.setLevel(log_level)
        
        # Add file handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_size, backupCount=backup_count
        )
        file_formatter = logging.Formatter(log_format)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Add console handler
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(log_format)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    def _setup_error_callbacks(self) -> None:
        """Set up error callbacks for different categories."""
        # Initialize empty callback lists for each category
        for category in ErrorCategory:
            self._error_callbacks[category] = []
    
    def register_error_callback(self, category: ErrorCategory, 
                               callback: Callable[[Exception, Dict[str, Any]], Awaitable[None]]) -> None:
        """Register a callback for a specific error category."""
        if category in self._error_callbacks:
            self._error_callbacks[category].append(callback)
    
    async def _execute_callbacks(self, category: ErrorCategory, 
                               error: Exception, context: Dict[str, Any]) -> None:
        """Execute all registered callbacks for an error category."""
        if category in self._error_callbacks:
            for callback in self._error_callbacks[category]:
                try:
                    await callback(error, context)
                except Exception as callback_error:
                    self.logger.error(
                        f"Error in callback for {category.value}: {callback_error}"
                    )
    
    def _categorize_error(self, error: Exception) -> Tuple[ErrorCategory, ErrorSeverity]:
        """Categorize an error by type and determine severity."""
        # Network errors
        if isinstance(error, (aiohttp.ClientError, socket.error, ConnectionError, 
                             TimeoutError, asyncio.TimeoutError)):
            return ErrorCategory.NETWORK, ErrorSeverity.MEDIUM
        
        # Discord API errors
        if str(error.__class__.__module__).startswith('discord'):
            return ErrorCategory.DISCORD, ErrorSeverity.MEDIUM
        
        # Database errors
        if isinstance(error, sqlite3.Error):
            return ErrorCategory.DATABASE, ErrorSeverity.HIGH
        
        # Parsing errors
        if isinstance(error, (ValueError, TypeError)) and "parse" in str(error).lower():
            return ErrorCategory.PARSING, ErrorSeverity.MEDIUM
        
        # Configuration errors
        if isinstance(error, (KeyError, AttributeError)) and "config" in str(error).lower():
            return ErrorCategory.CONFIGURATION, ErrorSeverity.HIGH
        
        # Authentication errors
        if "auth" in str(error).lower() or "token" in str(error).lower():
            return ErrorCategory.AUTHENTICATION, ErrorSeverity.CRITICAL
        
        # Permission errors
        if "permission" in str(error).lower() or "access" in str(error).lower():
            return ErrorCategory.PERMISSION, ErrorSeverity.HIGH
        
        # Validation errors
        if "valid" in str(error).lower():
            return ErrorCategory.VALIDATION, ErrorSeverity.LOW
        
        # Default to unknown
        return ErrorCategory.UNKNOWN, ErrorSeverity.MEDIUM
    
    def _format_error_context(self, error: Exception, context: Dict[str, Any],
                             category: ErrorCategory, severity: ErrorSeverity) -> Dict[str, Any]:
        """Format error context for structured logging."""
        error_id = f"{int(time.time())}-{hash(str(error)) % 10000}"
        
        error_data = {
            "error_id": error_id,
            "timestamp": datetime.utcnow().isoformat(),
            "category": category.value,
            "severity": severity.value,
            "error_type": error.__class__.__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": {k: str(v) for k, v in context.items()},
            "environment": Environment.get_env()
        }
        
        return error_data
    
    async def _log_error(self, error: Exception, context: Dict[str, Any],
                       category: ErrorCategory, severity: ErrorSeverity) -> Dict[str, Any]:
        """Log error with structured data."""
        error_data = self._format_error_context(error, context, category, severity)
        
        # Update error counts
        error_key = f"{category.value}:{error.__class__.__name__}"
        self._error_counts[error_key] = self._error_counts.get(error_key, 0) + 1
        
        # Store last error for this category
        self._last_errors[category.value] = error_data
        
        # Update health status
        component = self._map_category_to_component(category)
        if component in self._health_status["components"]:
            self._health_status["components"][component] = {
                "status": "degraded" if severity in (ErrorSeverity.HIGH, ErrorSeverity.CRITICAL) else "warning",
                "last_error": error_data["timestamp"]
            }
        
        # Log based on severity
        log_message = (
            f"[{error_data['error_id']}] {category.value.upper()} ERROR: {error}"
        )
        
        if severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message, extra=error_data)
        elif severity == ErrorSeverity.HIGH:
            self.logger.error(log_message, extra=error_data)
        elif severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message, extra=error_data)
        else:
            self.logger.info(log_message, extra=error_data)
        
        # Log to database if possible
        await self._log_to_database(error_data)
        
        return error_data
    
    def _map_category_to_component(self, category: ErrorCategory) -> str:
        """Map error category to health check component."""
        mapping = {
            ErrorCategory.NETWORK: "network",
            ErrorCategory.DISCORD: "discord",
            ErrorCategory.DATABASE: "database",
            ErrorCategory.PARSING: "monitoring",
            ErrorCategory.CONFIGURATION: "monitoring",
            ErrorCategory.AUTHENTICATION: "discord",
            ErrorCategory.PERMISSION: "discord",
            ErrorCategory.VALIDATION: "monitoring",
            ErrorCategory.INTERNAL: "monitoring",
            ErrorCategory.UNKNOWN: "monitoring"
        }
        return mapping.get(category, "monitoring")
    
    async def _log_to_database(self, error_data: Dict[str, Any]) -> None:
        """Log error to database for historical tracking."""
        try:
            # Create error_logs table if it doesn't exist
            db.execute('''
                CREATE TABLE IF NOT EXISTS error_logs (
                    id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    traceback TEXT,
                    context TEXT,
                    environment TEXT NOT NULL
                )
            ''')
            db.commit()
            
            # Insert error log
            db.execute(
                '''
                INSERT INTO error_logs 
                (id, timestamp, category, severity, error_type, error_message, traceback, context, environment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    error_data["error_id"],
                    error_data["timestamp"],
                    error_data["category"],
                    error_data["severity"],
                    error_data["error_type"],
                    error_data["error_message"],
                    error_data["traceback"],
                    json.dumps(error_data["context"]),
                    error_data["environment"]
                )
            )
            db.commit()
        except Exception as db_error:
            # Don't recursively call error handler
            self.logger.error(f"Failed to log error to database: {db_error}")
    
    async def handle_network_error(self, error: Exception, product_id: str) -> None:
        """Handle network-related errors."""
        context = {"product_id": product_id}
        category, severity = self._categorize_error(error)
        
        # Override category if it's not already NETWORK
        if category != ErrorCategory.NETWORK:
            category = ErrorCategory.NETWORK
        
        error_data = await self._log_error(error, context, category, severity)
        
        # Implement exponential backoff for retries
        retry_count = self._error_counts.get(f"network:{product_id}", 0)
        if retry_count < 3:  # Max 3 retries
            backoff_seconds = min(2 ** retry_count, 30)  # 1s, 2s, 4s, 8s, max 30s
            self.logger.info(
                f"Scheduling retry for product {product_id} in {backoff_seconds} seconds "
                f"(attempt {retry_count + 1}/3)"
            )
            
            # Track retry count for this specific product
            self._error_counts[f"network:{product_id}"] = retry_count + 1
        else:
            self.logger.warning(
                f"Maximum retry attempts reached for product {product_id}. "
                "Monitoring will continue for other products."
            )
            # Reset retry count after max attempts
            self._error_counts[f"network:{product_id}"] = 0
        
        # Execute registered callbacks
        await self._execute_callbacks(category, error, context)
    
    async def handle_discord_error(self, error: Exception, notification: Notification) -> None:
        """Handle Discord API errors."""
        context = {
            "product_id": notification.product_id,
            "channel_id": notification.channel_id,
            "retry_count": notification.retry_count
        }
        category, severity = self._categorize_error(error)
        
        # Override category if it's not already DISCORD
        if category != ErrorCategory.DISCORD:
            category = ErrorCategory.DISCORD
        
        error_data = await self._log_error(error, context, category, severity)
        
        # Queue notification for retry if under max retries
        if notification.retry_count < notification.max_retries:
            # Exponential backoff for Discord API rate limits
            backoff_seconds = min(2 ** notification.retry_count, 60)
            self.logger.info(
                f"Scheduling notification retry in {backoff_seconds} seconds "
                f"(attempt {notification.retry_count + 1}/{notification.max_retries})"
            )
            
            # The notification service should handle the actual retry
            # This just logs the error and provides guidance
        else:
            self.logger.warning(
                f"Maximum notification retry attempts reached for product {notification.product_id}. "
                "Notification will be dropped."
            )
        
        # Execute registered callbacks
        await self._execute_callbacks(category, error, context)
    
    async def handle_database_error(self, error: Exception, operation: str) -> None:
        """Handle database errors."""
        context = {"operation": operation}
        category, severity = self._categorize_error(error)
        
        # Override category if it's not already DATABASE
        if category != ErrorCategory.DATABASE:
            category = ErrorCategory.DATABASE
        
        error_data = await self._log_error(error, context, category, severity)
        
        # Attempt database recovery if not already in progress
        if not self._recovery_in_progress.get("database", False):
            self._recovery_in_progress["database"] = True
            
            try:
                self.logger.info("Attempting database recovery...")
                
                # Close existing connection if any
                db.close()
                
                # Wait a moment before reconnecting
                await asyncio.sleep(1)
                
                # Attempt to reconnect and validate connection
                db.connect()
                db.execute("SELECT 1")
                
                self.logger.info("Database connection recovered successfully")
                
                # Update health status
                self._health_status["components"]["database"] = {
                    "status": "healthy",
                    "last_error": error_data["timestamp"],
                    "recovery": datetime.utcnow().isoformat()
                }
            except Exception as recovery_error:
                self.logger.error(f"Database recovery failed: {recovery_error}")
                
                # Update health status to critical
                self._health_status["components"]["database"] = {
                    "status": "critical",
                    "last_error": error_data["timestamp"]
                }
                
                # Overall system status is critical if database is down
                self._health_status["status"] = "critical"
            finally:
                self._recovery_in_progress["database"] = False
        
        # Execute registered callbacks
        await self._execute_callbacks(category, error, context)
    
    async def handle_parsing_error(self, error: Exception, html_content: str) -> None:
        """Handle HTML parsing errors."""
        # Truncate HTML content for logging
        truncated_html = html_content[:500] + "..." if len(html_content) > 500 else html_content
        
        context = {"html_sample": truncated_html}
        category, severity = self._categorize_error(error)
        
        # Override category if it's not already PARSING
        if category != ErrorCategory.PARSING:
            category = ErrorCategory.PARSING
        
        error_data = await self._log_error(error, context, category, severity)
        
        # Store sample of problematic HTML for analysis
        try:
            logs_dir = Environment.get_logs_dir()
            sample_path = logs_dir / f"parsing_error_{error_data['error_id']}.html"
            
            with open(sample_path, "w", encoding="utf-8") as f:
                f.write(html_content)
                
            self.logger.info(f"Saved HTML sample to {sample_path}")
        except Exception as save_error:
            self.logger.error(f"Failed to save HTML sample: {save_error}")
        
        # Execute registered callbacks
        await self._execute_callbacks(category, error, context)
    
    async def handle_error(self, error: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generic error handler for uncategorized errors."""
        if context is None:
            context = {}
            
        category, severity = self._categorize_error(error)
        error_data = await self._log_error(error, context, category, severity)
        
        # Execute registered callbacks
        await self._execute_callbacks(category, error, context)
        
        return error_data
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of recent errors."""
        return {
            "counts": self._error_counts,
            "last_errors": self._last_errors,
            "total_errors": sum(self._error_counts.values())
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get system health status."""
        # Update timestamp
        self._health_status["last_check"] = datetime.utcnow().isoformat()
        
        # Determine overall status based on components
        component_statuses = [c["status"] for c in self._health_status["components"].values()]
        
        if "critical" in component_statuses:
            self._health_status["status"] = "critical"
        elif "degraded" in component_statuses:
            self._health_status["status"] = "degraded"
        elif "warning" in component_statuses:
            self._health_status["status"] = "warning"
        else:
            self._health_status["status"] = "healthy"
            
        return self._health_status
    
    async def run_health_check(self) -> Dict[str, Any]:
        """Run comprehensive health check on all system components."""
        health_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "components": {}
        }
        
        # Check database connection
        try:
            db.execute("SELECT 1")
            health_data["components"]["database"] = {"status": "healthy"}
        except Exception as e:
            health_data["components"]["database"] = {
                "status": "critical",
                "error": str(e)
            }
        
        # Check network connectivity (to bol.com)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://www.bol.com", timeout=5) as response:
                    if response.status == 200:
                        health_data["components"]["network"] = {"status": "healthy"}
                    else:
                        health_data["components"]["network"] = {
                            "status": "warning",
                            "status_code": response.status
                        }
        except Exception as e:
            health_data["components"]["network"] = {
                "status": "critical",
                "error": str(e)
            }
        
        # Update overall health status
        self._health_status["last_check"] = health_data["timestamp"]
        for component, status in health_data["components"].items():
            if component in self._health_status["components"]:
                self._health_status["components"][component]["status"] = status["status"]
                if "error" in status:
                    self._health_status["components"][component]["last_error"] = health_data["timestamp"]
        
        # Determine overall status
        component_statuses = [c["status"] for c in health_data["components"].values()]
        if "critical" in component_statuses:
            health_data["status"] = "critical"
        elif "degraded" in component_statuses:
            health_data["status"] = "degraded"
        elif "warning" in component_statuses:
            health_data["status"] = "warning"
        else:
            health_data["status"] = "healthy"
        
        self._health_status["status"] = health_data["status"]
        
        return health_data
    
    def reset_error_counts(self) -> None:
        """Reset error counters."""
        self._error_counts = {}


# Global error handler instance
error_handler = ErrorHandler()