"""
Tests for the performance monitoring and metrics service.
"""
import unittest
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from src.services.performance_monitor import PerformanceMonitor, PerformanceMetrics
from src.config.config_manager import ConfigManager


class TestPerformanceMetrics(unittest.TestCase):
    """Test the PerformanceMetrics class."""
    
    def test_init(self):
        """Test initialization of metrics."""
        metrics = PerformanceMetrics()
        self.assertEqual(metrics.success_count, 0)
        self.assertEqual(metrics.error_count, 0)
        self.assertEqual(len(metrics.response_times), 0)
        self.assertEqual(len(metrics.db_operation_times), 0)
        self.assertEqual(len(metrics.discord_request_times), 0)
    
    def test_reset(self):
        """Test resetting metrics."""
        metrics = PerformanceMetrics()
        metrics.success_count = 10
        metrics.error_count = 5
        metrics.response_times.append(100)
        metrics.db_operation_times.append(50)
        
        metrics.reset()
        
        self.assertEqual(metrics.success_count, 0)
        self.assertEqual(metrics.error_count, 0)
        self.assertEqual(len(metrics.response_times), 0)
        self.assertEqual(len(metrics.db_operation_times), 0)


class TestPerformanceMonitor(unittest.IsolatedAsyncioTestCase):
    """Test the PerformanceMonitor class."""
    
    def setUp(self):
        """Set up test environment."""
        self.config_manager = MagicMock(spec=ConfigManager)
        self.config_manager.get.return_value = 60  # Default interval
        
        # Mock the metrics repository
        self.metrics_repo_patcher = patch('src.services.performance_monitor.MetricsRepository')
        self.mock_metrics_repo = self.metrics_repo_patcher.start()
        
        # Create monitor instance
        self.monitor = PerformanceMonitor(self.config_manager)
        
        # Replace monitoring task with mock
        self.monitor._monitoring_loop = MagicMock()
    
    def tearDown(self):
        """Clean up after tests."""
        self.metrics_repo_patcher.stop()
    
    async def test_start_stop(self):
        """Test starting and stopping the monitor."""
        # Start monitoring
        await self.monitor.start()
        self.assertTrue(self.monitor.running)
        
        # Stop monitoring
        await self.monitor.stop()
        self.assertFalse(self.monitor.running)
    
    def test_record_response_time(self):
        """Test recording response times."""
        self.monitor.record_response_time("test-product", "bol.com", 150.5, True)
        
        self.assertEqual(len(self.monitor.metrics.response_times), 1)
        self.assertEqual(self.monitor.metrics.response_times[0], 150.5)
        self.assertEqual(self.monitor.metrics.success_count, 1)
        self.assertEqual(self.monitor.metrics.error_count, 0)
        
        # Test error case
        self.monitor.record_response_time("test-product", "bol.com", 200.0, False)
        
        self.assertEqual(len(self.monitor.metrics.response_times), 2)
        self.assertEqual(self.monitor.metrics.success_count, 1)
        self.assertEqual(self.monitor.metrics.error_count, 1)
    
    def test_record_db_operation(self):
        """Test recording database operations."""
        self.monitor.record_db_operation("query", 25.5, True)
        
        self.assertEqual(len(self.monitor.metrics.db_operation_times), 1)
        self.assertEqual(self.monitor.metrics.db_operation_times[0], 25.5)
        self.assertEqual(self.monitor.metrics.db_operation_counts["query"], 1)
        self.assertEqual(self.monitor.metrics.db_error_counts["query"], 0)
        
        # Test error case
        self.monitor.record_db_operation("query", 30.0, False)
        
        self.assertEqual(len(self.monitor.metrics.db_operation_times), 2)
        self.assertEqual(self.monitor.metrics.db_operation_counts["query"], 2)
        self.assertEqual(self.monitor.metrics.db_error_counts["query"], 1)
    
    def test_record_discord_request(self):
        """Test recording Discord API requests."""
        self.monitor.record_discord_request("messages/send", 120.5, 200)
        
        self.assertEqual(len(self.monitor.metrics.discord_request_times), 1)
        self.assertEqual(self.monitor.metrics.discord_request_times[0], 120.5)
        self.assertEqual(len(self.monitor.metrics.discord_rate_limits), 0)
        
        # Test rate limit case
        self.monitor.record_discord_request("messages/send", 150.0, 429)
        
        self.assertEqual(len(self.monitor.metrics.discord_request_times), 2)
        self.assertEqual(len(self.monitor.metrics.discord_rate_limits), 1)
        self.assertEqual(self.monitor.metrics.discord_error_counts["rate_limit"], 1)
    
    async def test_get_system_metrics(self):
        """Test getting system metrics."""
        # Add some test data
        self.monitor.record_response_time("test-product", "bol.com", 150.5, True)
        self.monitor.record_response_time("test-product", "bol.com", 200.0, False)
        self.monitor.record_db_operation("query", 25.5, True)
        self.monitor.record_discord_request("messages/send", 120.5, 200)
        
        # Mock the get_total_checks_today method
        self.monitor.metrics_repo.get_total_checks_today = MagicMock(return_value=100)
        
        # Get metrics
        metrics = await self.monitor.get_system_metrics()
        
        # Verify metrics
        self.assertIn('timestamp', metrics)
        self.assertIn('success_rate', metrics)
        self.assertIn('avg_response_time', metrics)
        self.assertIn('domain_metrics', metrics)
        self.assertIn('database_metrics', metrics)
        self.assertIn('discord_metrics', metrics)
        
        # Check calculated values
        self.assertEqual(metrics['success_count'], 1)
        self.assertEqual(metrics['error_count'], 1)
        self.assertEqual(metrics['success_rate'], 50.0)
        self.assertEqual(metrics['avg_response_time'], 175.25)
        self.assertEqual(metrics['total_checks_today'], 100)


if __name__ == '__main__':
    unittest.main()