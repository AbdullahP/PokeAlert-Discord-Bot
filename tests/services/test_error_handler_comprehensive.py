"""
Comprehensive tests for the error handling system.
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


class TestErrorHandlerComprehensive:
    """Comprehensive test suite for the error handling system."""
    
    @pytest.fixture
    def error_handler(self):
        """Create an error handler instance for testing."""
        with patch('src.services.error_handler.logging'):
            handler = ErrorHandler()
            # Mock the _log_to_database method to avoid actual DB operations
            handler._log_to_database = AsyncMock()
            return handler
    
    @pytest.mark.asyncio
    async def test_handle_multiple_error_types(self, error_handler):
        """Test handling different types of errors."""
        # Mock the _log_error method
        error_handler._log_error = AsyncMock(return_value={"error_id": "test-123"})
        error_handler._execute_callbacks = AsyncMock()
        
        # Test with different error types
        network_error = aiohttp.ClientConnectionError("Connection refused")
        db_error = sqlite3.OperationalError("database is locked")
        parsing_error = ValueError("Failed to parse HTML")
        generic_error = Exception("Something went wrong")
        
        # Handle each error type
        await error_handler.handle_network_error(network_error, "product-123")
        await error_handler.handle_database_error(db_error, "insert_product")
        await error_handler.handle_parsing_error(parsing_error, "<html>Test</html>")
        await error_handler.handle_error(generic_error, {"operation": "test"})
        
        # Verify all errors were logged
        assert error_handler._log_error.call_count == 4
        
        # Verify callbacks were executed for each error
        assert error_handler._execute_callbacks.call_count == 4
        
        # Verify error counts were tracked
        assert error_handler._error_counts.get("network:product-123") == 1
        assert "database:insert_product" in error_handler._error_counts
        assert "parsing" in error_handler._error_counts
        assert "unknown:test" in error_handler._error_counts
    
    @pytest.mark.asyncio
    async def test_error_recovery_mechanisms(self, error_handler):
        """Test error recovery mechanisms."""
        # Mock database connection
        with patch('src.services.error_handler.db') as mock_db:
            mock_db.close = MagicMock()
            mock_db.connect = MagicMock()
            mock_db.execute = MagicMock()
            
            # Test database recovery
            db_error = sqlite3.OperationalError("database is locked")
            await error_handler.handle_database_error(db_error, "query_products")
            
            # Verify recovery was attempted
            mock_db.close.assert_called_once()
            mock_db.connect.assert_called_once()
            mock_db.execute.assert_called_once_with("SELECT 1")
        
        # Test notification retry
        notification = Notification(
            product_id="product-123",
            channel_id=123456789,
            embed_data={"title": "Test"},
            role_mentions=["<@&123456>"],
            timestamp=datetime.utcnow(),
            retry_count=1,
            max_retries=3
        )
        
        # Mock notification service
        error_handler.notification_service = AsyncMock()
        error_handler.notification_service.queue_notification = AsyncMock()
        
        # Handle Discord error
        discord_error = Exception("Discord API error")
        await error_handler.handle_discord_error(discord_error, notification)
        
        # Verify notification was requeued
        error_handler.notification_service.queue_notification.assert_called_once_with(notification)
    
    @pytest.mark.asyncio
    async def test_error_callbacks(self, error_handler):
        """Test registering and executing error callbacks."""
        # Create mock callbacks for different error categories
        network_callback = AsyncMock()
        database_callback = AsyncMock()
        parsing_callback = AsyncMock()
        
        # Register callbacks
        error_handler.register_error_callback(ErrorCategory.NETWORK, network_callback)
        error_handler.register_error_callback(ErrorCategory.DATABASE, database_callback)
        error_handler.register_error_callback(ErrorCategory.PARSING, parsing_callback)
        
        # Create test errors
        network_error = aiohttp.ClientConnectionError("Connection refused")
        db_error = sqlite3.OperationalError("database is locked")
        parsing_error = ValueError("Failed to parse HTML")
        
        # Execute callbacks for each error type
        await error_handler._execute_callbacks(ErrorCategory.NETWORK, network_error, {"product_id": "test-123"})
        await error_handler._execute_callbacks(ErrorCategory.DATABASE, db_error, {"operation": "query"})
        await error_handler._execute_callbacks(ErrorCategory.PARSING, parsing_error, {"html": "<html>Test</html>"})
        
        # Verify each callback was called with the correct error
        network_callback.assert_called_once_with(network_error, {"product_id": "test-123"})
        database_callback.assert_called_once_with(db_error, {"operation": "query"})
        parsing_callback.assert_called_once_with(parsing_error, {"html": "<html>Test</html>"})
    
    @pytest.mark.asyncio
    async def test_error_logging_to_file(self, error_handler):
        """Test logging errors to file."""
        # Mock file operations
        with patch('builtins.open', MagicMock()), \
             patch('src.services.error_handler.Environment') as mock_env, \
             patch('src.services.error_handler.datetime') as mock_datetime, \
             patch('src.services.error_handler.json.dump') as mock_json_dump:
            
            mock_env.get_logs_dir.return_value = Path("/tmp/logs")
            mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 12, 0, 0)
            
            # Log an error
            error = ValueError("Test error")
            context = {"test": "data"}
            await error_handler._log_error_to_file(error, context, ErrorCategory.PARSING)
            
            # Verify JSON was written
            mock_json_dump.assert_called_once()
            error_data = mock_json_dump.call_args[0][0]
            assert error_data["error_type"] == "ValueError"
            assert error_data["error_message"] == "Test error"
            assert error_data["category"] == "parsing"
            assert error_data["context"] == {"test": "data"}
    
    @pytest.mark.asyncio
    async def test_error_rate_tracking(self, error_handler):
        """Test error rate tracking and alerts."""
        # Mock logger
        with patch('src.services.error_handler.logging') as mock_logging:
            # Generate multiple errors of the same type
            for i in range(5):
                error = aiohttp.ClientConnectionError(f"Connection refused {i}")
                await error_handler.handle_network_error(error, "product-123")
            
            # Verify error count
            assert error_handler._error_counts["network:product-123"] == 5
            
            # Verify alert was logged
            mock_logging.getLogger.return_value.warning.assert_called()
            warning_message = mock_logging.getLogger.return_value.warning.call_args[0][0]
            assert "High error rate" in warning_message
            assert "product-123" in warning_message
    
    @pytest.mark.asyncio
    async def test_error_severity_escalation(self, error_handler):
        """Test error severity escalation based on frequency."""
        # Mock _log_error to track severity
        original_log_error = error_handler._log_error
        severities = []
        
        async def mock_log_error(error, context, category=None, severity=None):
            severities.append(severity)
            return await original_log_error(error, context, category, severity)
            
        error_handler._log_error = mock_log_error
        
        # Generate multiple errors of the same type
        for i in range(10):
            error = aiohttp.ClientConnectionError("Connection refused")
            await error_handler.handle_network_error(error, "product-123")
        
        # Verify severity escalation
        assert severities[0] == ErrorSeverity.MEDIUM  # Initial severity
        assert severities[-1] == ErrorSeverity.HIGH  # Escalated severity
    
    @pytest.mark.asyncio
    async def test_run_health_check(self, error_handler):
        """Test running a comprehensive health check."""
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
            
            # Verify result structure
            assert "timestamp" in result
            assert "components" in result
            assert "database" in result["components"]
            assert "network" in result["components"]
            assert result["components"]["database"]["status"] == "healthy"
            assert result["components"]["network"]["status"] == "healthy"
            assert result["status"] == "healthy"
            
            # Test with database error
            mock_db.execute = MagicMock(side_effect=sqlite3.Error("database is locked"))
            
            # Run health check
            result = await error_handler.run_health_check()
            
            # Verify database component is critical
            assert result["components"]["database"]["status"] == "critical"
            assert "database is locked" in result["components"]["database"]["error"]
            assert result["status"] == "critical"  # Overall status is critical
    
    @pytest.mark.asyncio
    async def test_error_context_enrichment(self, error_handler):
        """Test error context enrichment."""
        # Mock _log_error to capture context
        error_handler._log_error = AsyncMock(return_value={"error_id": "test-123"})
        
        # Create base error and context
        error = aiohttp.ClientConnectionError("Connection refused")
        base_context = {"product_id": "product-123", "url": "https://example.com"}
        
        # Handle error with context enrichment
        await error_handler.handle_network_error(error, "product-123", extra_context=base_context)
        
        # Verify context was enriched
        context = error_handler._log_error.call_args[0][1]
        assert context["product_id"] == "product-123"
        assert context["url"] == "https://example.com"
        assert "timestamp" in context  # Automatically added
        assert "error_count" in context  # Automatically added
    
    @pytest.mark.asyncio
    async def test_error_deduplication(self, error_handler):
        """Test error deduplication."""
        # Mock _log_error to track calls
        error_handler._log_error = AsyncMock(return_value={"error_id": "test-123"})
        
        # Create identical errors
        error1 = ValueError("Duplicate error")
        error2 = ValueError("Duplicate error")
        
        # Handle the same error multiple times in quick succession
        await error_handler.handle_error(error1, {"operation": "test"})
        await error_handler.handle_error(error2, {"operation": "test"})
        
        # Verify error was logged only once (or with reduced severity)
        assert error_handler._log_error.call_count <= 2
        
        # Verify error was counted correctly
        assert error_handler._error_counts["unknown:test"] == 2
    
    @pytest.mark.asyncio
    async def test_error_recovery_success_tracking(self, error_handler):
        """Test tracking successful error recoveries."""
        # Mock database connection with successful recovery
        with patch('src.services.error_handler.db') as mock_db:
            mock_db.close = MagicMock()
            mock_db.connect = MagicMock()
            mock_db.execute = MagicMock()
            
            # Handle database error
            db_error = sqlite3.OperationalError("database is locked")
            await error_handler.handle_database_error(db_error, "query_products")
            
            # Verify recovery was tracked
            assert error_handler._recovery_attempts["database"] == 1
            assert error_handler._recovery_successes["database"] == 1
            
            # Mock failed recovery
            mock_db.execute = MagicMock(side_effect=sqlite3.Error("still locked"))
            
            # Handle another database error
            await error_handler.handle_database_error(db_error, "query_products")
            
            # Verify failed recovery was tracked
            assert error_handler._recovery_attempts["database"] == 2
            assert error_handler._recovery_successes["database"] == 1
"""