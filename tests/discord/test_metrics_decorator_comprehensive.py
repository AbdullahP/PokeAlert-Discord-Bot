"""
Comprehensive tests for the Discord API metrics decorator.
"""
import pytest
import asyncio
import time
from unittest.mock import MagicMock, patch, AsyncMock
import discord

from src.discord.metrics_decorator import discord_metrics, set_performance_monitor
from src.services.performance_monitor import PerformanceMonitor


class TestMetricsDecoratorComprehensive:
    """Comprehensive test suite for the metrics decorator."""
    
    @pytest.fixture
    def performance_monitor(self, config_manager):
        """Create a performance monitor for testing."""
        monitor = PerformanceMonitor(config_manager)
        set_performance_monitor(monitor)
        return monitor
    
    @pytest.mark.asyncio
    async def test_decorator_with_different_endpoints(self, performance_monitor):
        """Test decorator with different endpoints."""
        # Define test functions for different endpoints
        @discord_metrics("messages/send")
        async def send_message():
            await asyncio.sleep(0.01)
            return "message sent"
        
        @discord_metrics("channels/get")
        async def get_channel():
            await asyncio.sleep(0.01)
            return "channel data"
        
        @discord_metrics("guilds/members")
        async def get_members():
            await asyncio.sleep(0.01)
            return "member list"
        
        # Call all functions
        await send_message()
        await get_channel()
        await get_members()
        
        # Verify metrics were recorded for each endpoint
        discord_metrics = performance_monitor.metrics.discord_request_times
        assert len(discord_metrics) == 3
        
        # Check that we have metrics for each endpoint
        endpoints = [
            call[0] for call in 
            performance_monitor.record_discord_request.call_args_list
        ]
        assert "messages/send" in endpoints
        assert "channels/get" in endpoints
        assert "guilds/members" in endpoints
    
    @pytest.mark.asyncio
    async def test_decorator_with_different_status_codes(self, performance_monitor):
        """Test decorator with different HTTP status codes."""
        # Define test functions that raise different errors
        @discord_metrics("test/success")
        async def success_function():
            await asyncio.sleep(0.01)
            return "success"
        
        @discord_metrics("test/forbidden")
        async def forbidden_function():
            await asyncio.sleep(0.01)
            raise discord.errors.Forbidden(
                response=MagicMock(status=403),
                message="Missing permissions"
            )
        
        @discord_metrics("test/not_found")
        async def not_found_function():
            await asyncio.sleep(0.01)
            raise discord.errors.NotFound(
                response=MagicMock(status=404),
                message="Resource not found"
            )
        
        @discord_metrics("test/rate_limited")
        async def rate_limited_function():
            await asyncio.sleep(0.01)
            raise discord.errors.HTTPException(
                response=MagicMock(status=429),
                message="You are being rate limited"
            )
        
        # Call success function
        await success_function()
        
        # Call error functions and catch exceptions
        with pytest.raises(discord.errors.Forbidden):
            await forbidden_function()
        
        with pytest.raises(discord.errors.NotFound):
            await not_found_function()
        
        with pytest.raises(discord.errors.HTTPException):
            await rate_limited_function()
        
        # Verify metrics were recorded with correct status codes
        assert performance_monitor.record_discord_request.call_count == 4
        
        # Extract status codes from calls
        status_codes = [
            call[0][2] for call in 
            performance_monitor.record_discord_request.call_args_list
        ]
        
        assert 200 in status_codes  # Success
        assert 403 in status_codes  # Forbidden
        assert 404 in status_codes  # Not Found
        assert 429 in status_codes  # Rate Limited
    
    @pytest.mark.asyncio
    async def test_decorator_performance_overhead(self):
        """Test the performance overhead of the decorator."""
        # Create a simple async function without decorator
        async def plain_function():
            await asyncio.sleep(0.01)
            return "result"
        
        # Create the same function with decorator
        @discord_metrics("test/performance")
        async def decorated_function():
            await asyncio.sleep(0.01)
            return "result"
        
        # Measure plain function execution time (average of multiple runs)
        plain_times = []
        for _ in range(10):
            start = time.time()
            await plain_function()
            end = time.time()
            plain_times.append(end - start)
        
        avg_plain_time = sum(plain_times) / len(plain_times)
        
        # Measure decorated function execution time (average of multiple runs)
        decorated_times = []
        for _ in range(10):
            start = time.time()
            await decorated_function()
            end = time.time()
            decorated_times.append(end - start)
        
        avg_decorated_time = sum(decorated_times) / len(decorated_times)
        
        # Verify the overhead is reasonable (less than 5ms)
        overhead = (avg_decorated_time - avg_plain_time) * 1000  # Convert to ms
        assert overhead < 5, f"Decorator overhead is too high: {overhead}ms"
    
    @pytest.mark.asyncio
    async def test_decorator_with_complex_return_values(self, performance_monitor):
        """Test decorator with complex return values."""
        # Define a function that returns a complex object
        @discord_metrics("test/complex")
        async def complex_return_function():
            await asyncio.sleep(0.01)
            return {
                "id": 123,
                "name": "Test Object",
                "nested": {
                    "value": [1, 2, 3],
                    "flag": True
                }
            }
        
        # Call the function
        result = await complex_return_function()
        
        # Verify the result is returned correctly
        assert result["id"] == 123
        assert result["name"] == "Test Object"
        assert result["nested"]["value"] == [1, 2, 3]
        assert result["nested"]["flag"] is True
        
        # Verify metrics were recorded
        performance_monitor.record_discord_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_decorator_with_function_arguments(self, performance_monitor):
        """Test decorator with function arguments."""
        # Define a function that takes arguments
        @discord_metrics("test/args")
        async def function_with_args(arg1, arg2, kwarg1=None, kwarg2=None):
            await asyncio.sleep(0.01)
            return f"{arg1}-{arg2}-{kwarg1}-{kwarg2}"
        
        # Call the function with different argument combinations
        result1 = await function_with_args("a", "b")
        result2 = await function_with_args("c", "d", kwarg1="e")
        result3 = await function_with_args("f", "g", kwarg1="h", kwarg2="i")
        
        # Verify results
        assert result1 == "a-b-None-None"
        assert result2 == "c-d-e-None"
        assert result3 == "f-g-h-i"
        
        # Verify metrics were recorded for each call
        assert performance_monitor.record_discord_request.call_count == 3
    
    @pytest.mark.asyncio
    async def test_decorator_with_nested_calls(self, performance_monitor):
        """Test decorator with nested function calls."""
        # Define nested functions
        @discord_metrics("test/inner")
        async def inner_function():
            await asyncio.sleep(0.01)
            return "inner result"
        
        @discord_metrics("test/outer")
        async def outer_function():
            await asyncio.sleep(0.01)
            inner_result = await inner_function()
            return f"outer with {inner_result}"
        
        # Call the outer function
        result = await outer_function()
        
        # Verify result
        assert result == "outer with inner result"
        
        # Verify metrics were recorded for both functions
        assert performance_monitor.record_discord_request.call_count == 2
        
        # Check that we have metrics for each endpoint
        endpoints = [
            call[0][0] for call in 
            performance_monitor.record_discord_request.call_args_list
        ]
        assert "test/inner" in endpoints
        assert "test/outer" in endpoints
"""