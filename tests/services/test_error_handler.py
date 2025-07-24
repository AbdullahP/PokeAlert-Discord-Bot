"""
Tests for the error handling and logging system.
"""
import pytest
import asyncio
import logging
import sqlite3
import aiohttp
import json
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
from datetime import datetime

from src.services.error_handler import ErrorHandler, ErrorCategory, ErrorSeverity
from src.models.product_data import Notification


@pytest.fixture
def error_handler():
    """Create an error handler instance for testing."""
    with patch('src.services.error_handler.logging'):
        handler = ErrorHandler()
        # Mock the _log_to_database method to avoid actual DB operations
        handler._log_to_database = AsyncMock()
        return handler


class TestErrorHandler:
    """Test suite for ErrorHandler class."""
    
    @pytest.mark.asyncio
    async def test_categorize_error(self, error_handler):
        """Test error categorization logic."""
        # Network errors
        category, severity = error_handler._categorize_error(aiohttp.ClientConnectionError())
        assert category == ErrorCategory.NETWORK
        assert severity == ErrorSeverity.MEDIUM
        
        # Database errors
        category, severity = error_handler._categorize_error(sqlite3.Error())
        assert category == ErrorCategory.DATABASE
        assert severity == ErrorSeverity.HIGH
        
        # Parsing errors
        category, severity = error_handler._categorize_error(ValueError("Failed to parse HTML"))
        assert category == ErrorCategory.PARSING
        assert severity == ErrorSeverity.MEDIUM
        
        # Unknown errors
        category, severity = error_handler._categorize_error(Exception("Generic error"))
        assert category == ErrorCategory.UNKNOWN
        assert severity == ErrorSeverity.MEDIUM
    
    @pytest.mark.asyncio
    async def test_handle_network_error(self, error_handler):
        """Test handling of network errors."""
        # Mock the _log_error method
        error_handler._log_error = AsyncMock(return_value={"error_id": "test-123"})
        error_handler._execute_callbacks = AsyncMock()
        
        # Test with a network error
        error = aiohttp.ClientConnectionError("Connection refused")
        await error_handler.handle_network_error(error, "product-123")
        
        # Verify error was logged
        error_handler._log_error.assert_called_once()
        assert error_handler._log_error.call_args[0][0] == error
        assert error_handler._log_error.call_args[0][1]["product_id"] == "product-123"
        assert error_handler._log_error.call_args[0][2] == ErrorCategory.NETWORK
        
        # Verify callbacks were executed
        error_handler._execute_callbacks.assert_called_once()
        
        # Verify retry tracking
        assert error_handler._error_counts.get("network:product-123") == 1
    
    @pytest.mark.asyncio
    async def test_handle_discord_error(self, error_handler):
        """Test handling of Discord API errors."""
        # Mock the _log_error method
        error_handler._log_error = AsyncMock(return_value={"error_id": "test-123"})
        error_handler._execute_callbacks = AsyncMock()
        
        # Create a test notification
        notification = Notification(
            product_id="product-123",
            channel_id=123456789,
            embed_data={},
            role_mentions=[],
            timestamp=datetime.utcnow(),
            retry_count=1,
            max_retries=3
        )
        
        # Test with a Discord error
        error = Exception("Discord API rate limit exceeded")
        await error_handler.handle_discord_error(error, notification)
        
        # Verify error was logged
        error_handler._log_error.assert_called_once()
        assert error_handler._log_error.call_args[0][0] == error
        assert error_handler._log_error.call_args[0][1]["product_id"] == "product-123"
        assert error_handler._log_error.call_args[0][1]["channel_id"] == 123456789
        
        # Verify callbacks were executed
        error_handler._execute_callbacks.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_database_error(self, error_handler):
        """Test handling of database errors."""
        # Mock methods
        error_handler._log_error = AsyncMock(return_value={"error_id": "test-123", "timestamp": datetime.utcnow().isoformat()})
        error_handler._execute_callbacks = AsyncMock()
        
        # Mock database connection
        with patch('src.services.error_handler.db') as mock_db:
            mock_db.close = MagicMock()
            mock_db.connect = MagicMock()
            mock_db.execute = MagicMock()
            
            # Test with a database error
            error = sqlite3.OperationalError("database is locked")
            await error_handler.handle_database_error(error, "insert_product")
            
            # Verify error was logged
            error_handler._log_error.assert_called_once()
            assert error_handler._log_error.call_args[0][0] == error
            assert error_handler._log_error.call_args[0][1]["operation"] == "insert_product"
            assert error_handler._log_error.call_args[0][2] == ErrorCategory.DATABASE
            
            # Verify recovery was attempted
            mock_db.close.assert_called_once()
            mock_db.connect.assert_called_once()
            mock_db.execute.assert_called_once_with("SELECT 1")
            
            # Verify callbacks were executed
            error_handler._execute_callbacks.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_parsing_error(self, error_handler):
        """Test handling of HTML parsing errors."""
        # Mock methods
        error_handler._log_error = AsyncMock(return_value={"error_id": "test-123"})
        error_handler._execute_callbacks = AsyncMock()
        
        # Mock file operations
        with patch('builtins.open', MagicMock()), \
             patch('src.services.error_handler.Environment') as mock_env:
            
            mock_env.get_logs_dir.return_value = Path("/tmp/logs")
            
            # Test with a parsing error
            error = ValueError("Failed to parse product price")
            html_content = "<html><body>Test HTML content</body></html>"
            await error_handler.handle_parsing_error(error, html_content)
            
            # Verify error was logged
            error_handler._log_error.assert_called_once()
            assert error_handler._log_error.call_args[0][0] == error
            assert "html_sample" in error_handler._log_error.call_args[0][1]
            assert error_handler._log_error.call_args[0][2] == ErrorCategory.PARSING
            
            # Verify callbacks were executed
            error_handler._execute_callbacks.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_error(self, error_handler):
        """Test generic error handling."""
        # Mock methods
        error_handler._log_error = AsyncMock(return_value={"error_id": "test-123"})
        error_handler._execute_callbacks = AsyncMock()
        
        # Test with a generic error
        error = Exception("Something went wrong")
        context = {"operation": "test_operation"}
        result = await error_handler.handle_error(error, context)
        
        # Verify error was logged
        error_handler._log_error.assert_called_once()
        assert error_handler._log_error.call_args[0][0] == error
        assert error_handler._log_error.call_args[0][1] == context
        
        # Verify callbacks were executed
        error_handler._execute_callbacks.assert_called_once()
        
        # Verify result
        assert result == {"error_id": "test-123"}
    
    @pytest.mark.asyncio
    async def test_register_error_callback(self, error_handler):
        """Test registering and executing error callbacks."""
        # Create a mock callback
        callback = AsyncMock()
        
        # Register the callback
        error_handler.register_error_callback(ErrorCategory.NETWORK, callback)
        
        # Execute callbacks
        error = Exception("Test error")
        context = {"test": "data"}
        await error_handler._execute_callbacks(ErrorCategory.NETWORK, error, context)
        
        # Verify callback was called
        callback.assert_called_once_with(error, context)
    
    def test_get_error_summary(self, error_handler):
        """Test getting error summary."""
        # Set up some test data
        error_handler._error_counts = {
            "network:ConnectionError": 5,
            "database:OperationalError": 2
        }
        error_handler._last_errors = {
            "network": {"error_id": "net-123"},
            "database": {"error_id": "db-456"}
        }
        
        # Get summary
        summary = error_handler.get_error_summary()
        
        # Verify summary
        assert summary["counts"] == error_handler._error_counts
        assert summary["last_errors"] == error_handler._last_errors
        assert summary["total_errors"] == 7
    
    def test_get_health_status(self, error_handler):
        """Test getting health status."""
        # Set up test health status
        error_handler._health_status = {
            "status": "healthy",
            "last_check": "2023-01-01T00:00:00",
            "components": {
                "network": {"status": "healthy"},
                "database": {"status": "healthy"}
            }
        }
        
        # Get health status
        status = error_handler.get_health_status()
        
        # Verify status was updated with current timestamp
        assert status["status"] == "healthy"
        assert status["last_check"] != "2023-01-01T00:00:00"  # Should be updated
        assert "components" in status
    
    @pytest.mark.asyncio
    async def test_run_health_check(self, error_handler):
        """Test running a health check."""
        # Mock database
        with patch('src.services.error_handler.db') as mock_db, \
             patch('aiohttp.ClientSession') as mock_session:
            
            # Mock successful database check
            mock_db.execute = MagicMock()
            
            # Mock successful network check
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
            
            # Run health check
            result = await error_handler.run_health_check()
            
            # Verify result
            assert "timestamp" in result
            assert "components" in result
            assert "database" in result["components"]
            assert "network" in result["components"]
            assert result["components"]["database"]["status"] == "healthy"
            assert result["components"]["network"]["status"] == "healthy"
            assert result["status"] == "healthy"
    
    def test_reset_error_counts(self, error_handler):
        """Test resetting error counts."""
        # Set up some test data
        error_handler._error_counts = {
            "network:ConnectionError": 5,
            "database:OperationalError": 2
        }
        
        # Reset counts
        error_handler.reset_error_counts()
        
        # Verify counts were reset
        assert error_handler._error_counts == {}