"""
Tests for the Discord API metrics decorator.
"""
import unittest
from unittest.mock import MagicMock, patch
import asyncio
import discord

from src.discord.metrics_decorator import discord_metrics, set_performance_monitor


class TestDiscordMetricsDecorator(unittest.IsolatedAsyncioTestCase):
    """Test the Discord API metrics decorator."""
    
    def setUp(self):
        """Set up test environment."""
        # Create mock performance monitor
        self.mock_monitor = MagicMock()
        set_performance_monitor(self.mock_monitor)
    
    async def test_successful_operation(self):
        """Test decorator with successful operation."""
        @discord_metrics("messages/send")
        async def test_function():
            await asyncio.sleep(0.01)  # Small delay to ensure measurable duration
            return "success"
        
        result = await test_function()
        
        self.assertEqual(result, "success")
        self.mock_monitor.record_discord_request.assert_called_once()
        
        # Check arguments
        args = self.mock_monitor.record_discord_request.call_args[0]
        self.assertEqual(args[0], "messages/send")  # endpoint
        self.assertGreater(args[1], 0)  # duration_ms
        self.assertEqual(args[2], 200)  # status_code (default success)
    
    async def test_rate_limited_operation(self):
        """Test decorator with rate limited operation."""
        @discord_metrics("messages/send")
        async def test_function():
            await asyncio.sleep(0.01)  # Small delay to ensure measurable duration
            raise discord.errors.HTTPException(
                response=MagicMock(status=429),
                message="You are being rate limited"
            )
        
        with self.assertRaises(discord.errors.HTTPException):
            await test_function()
        
        self.mock_monitor.record_discord_request.assert_called_once()
        
        # Check arguments
        args = self.mock_monitor.record_discord_request.call_args[0]
        self.assertEqual(args[0], "messages/send")  # endpoint
        self.assertGreater(args[1], 0)  # duration_ms
        self.assertEqual(args[2], 429)  # status_code (rate limited)
    
    async def test_other_error(self):
        """Test decorator with other HTTP error."""
        @discord_metrics("messages/send")
        async def test_function():
            await asyncio.sleep(0.01)  # Small delay to ensure measurable duration
            raise discord.errors.Forbidden(
                response=MagicMock(status=403),
                message="Missing permissions"
            )
        
        with self.assertRaises(discord.errors.Forbidden):
            await test_function()
        
        self.mock_monitor.record_discord_request.assert_called_once()
        
        # Check arguments
        args = self.mock_monitor.record_discord_request.call_args[0]
        self.assertEqual(args[0], "messages/send")  # endpoint
        self.assertGreater(args[1], 0)  # duration_ms
        self.assertEqual(args[2], 403)  # status_code
    
    async def test_generic_error(self):
        """Test decorator with generic error."""
        @discord_metrics("messages/send")
        async def test_function():
            await asyncio.sleep(0.01)  # Small delay to ensure measurable duration
            raise ValueError("Test error")
        
        with self.assertRaises(ValueError):
            await test_function()
        
        self.mock_monitor.record_discord_request.assert_called_once()
        
        # Check arguments
        args = self.mock_monitor.record_discord_request.call_args[0]
        self.assertEqual(args[0], "messages/send")  # endpoint
        self.assertGreater(args[1], 0)  # duration_ms
        self.assertEqual(args[2], 500)  # status_code (generic error)
    
    async def test_no_performance_monitor(self):
        """Test decorator when no performance monitor is set."""
        # Reset performance monitor
        set_performance_monitor(None)
        
        @discord_metrics("messages/send")
        async def test_function():
            return "success"
        
        # Should not raise an exception
        result = await test_function()
        self.assertEqual(result, "success")


if __name__ == '__main__':
    unittest.main()