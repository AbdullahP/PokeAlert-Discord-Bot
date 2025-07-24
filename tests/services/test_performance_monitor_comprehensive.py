"""
Comprehensive tests for the performance monitoring system.
"""
import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta

from src.services.performance_monitor import PerformanceMonitor, PerformanceMetrics
from src.config.config_manager import ConfigManager


class TestPerformanceMonitorComprehensive:
    """Comprehensive test suite for the performance monitoring system."""
    
    @pytest.fixture
    def config_manager(self):
        """Create a config manager with test settings."""
        config = ConfigManager()
        config.set('monitoring.metrics_interval', 30)
        config.set('monitoring.metrics_retention', 7)
        config.set('monitoring.alert_threshold', 80.0)
        return config
    
    @pytest.fixture
    def performance_monitor(self, config_manager):
        """Create a performance monitor for testing."""
        monitor = PerformanceMonitor(config_manager)
        
        # Mock the metrics repository
        monitor.metrics_repo = MagicMock()
        monitor.metrics_repo.add_metric = MagicMock(return_value=True)
        monitor.metrics_repo.get_monitoring_status = MagicMock(return_value={
            "product_id": "test-product-123",
            "is_active": True,
            "success_rate": 95.0,
            "error_count": 2,
            "last_error": "Connection timeout"
        })
        monitor.metrics_repo.get_total_checks_today = MagicMock(return_value=100)
        
        # Replace monitoring task with mock
        monitor._monitoring_loop = AsyncMock()
        
        return monitor
    
    @pytest.mark.asyncio
    async def test_start_stop(self, performance_monitor):
        """Test starting and stopping the monitor."""
        # Start monitoring
        await performance_monitor.start()
        assert performance_monitor.running is True
        
        # Stop monitoring
        await performance_monitor.stop()
        assert performance_monitor.running is False
    
    def test_record_response_time_multiple_domains(self, performance_monitor):
        """Test recording response times for multiple domains."""
        # Record response times for different domains
        performance_monitor.record_response_time("product-1", "bol.com", 150.5, True)
        performance_monitor.record_response_time("product-2", "bol.com", 180.2, True)
        performance_monitor.record_response_time("product-3", "amazon.nl", 200.8, True)
        performance_monitor.record_response_time("product-4", "amazon.nl", 220.3, False)
        
        # Verify metrics were recorded
        assert len(performance_monitor.metrics.response_times) == 4
        assert len(performance_monitor.metrics.response_time_by_domain["bol.com"]) == 2
        assert len(performance_monitor.metrics.response_time_by_domain["amazon.nl"]) == 2
        
        # Verify success/error counts
        assert performance_monitor.metrics.success_count == 3
        assert performance_monitor.metrics.error_count == 1
        assert performance_monitor.metrics.success_by_domain["bol.com"] == 2
        assert performance_monitor.metrics.success_by_domain["amazon.nl"] == 1
        assert performance_monitor.metrics.error_by_domain["amazon.nl"] == 1
    
    def test_record_db_operation_different_types(self, performance_monitor):
        """Test recording different types of database operations."""
        # Record different operation types
        performance_monitor.record_db_operation("query", 25.5, True)
        performance_monitor.record_db_operation("insert", 30.2, True)
        performance_monitor.record_db_operation("update", 28.7, True)
        performance_monitor.record_db_operation("query", 35.1, False)  # Failed query
        
        # Verify metrics were recorded
        assert len(performance_monitor.metrics.db_operation_times) == 4
        assert performance_monitor.metrics.db_operation_counts["query"] == 2
        assert performance_monitor.metrics.db_operation_counts["insert"] == 1
        assert performance_monitor.metrics.db_operation_counts["update"] == 1
        
        # Verify error counts
        assert performance_monitor.metrics.db_error_counts["query"] == 1
        assert "insert" not in performance_monitor.metrics.db_error_counts
    
    def test_record_discord_request_with_rate_limits(self, performance_monitor):
        """Test recording Discord requests with rate limits."""
        # Record successful requests
        performance_monitor.record_discord_request("messages/send", 120.5, 200)
        performance_monitor.record_discord_request("channels/get", 80.3, 200)
        
        # Record rate limited requests
        performance_monitor.record_discord_request("messages/send", 150.0, 429)
        performance_monitor.record_discord_request("messages/send", 160.0, 429)
        
        # Record other errors
        performance_monitor.record_discord_request("guilds/get", 90.5, 403)
        
        # Verify metrics were recorded
        assert len(performance_monitor.metrics.discord_request_times) == 5
        assert len(performance_monitor.metrics.discord_rate_limits) == 2
        assert performance_monitor.metrics.discord_error_counts["rate_limit"] == 2
        assert performance_monitor.metrics.discord_error_counts["status_403"] == 1
    
    @pytest.mark.asyncio
    async def test_collect_metrics(self, performance_monitor):
        """Test collecting and logging metrics."""
        # Add some test data
        performance_monitor.record_response_time("product-1", "bol.com", 150.5, True)
        performance_monitor.record_response_time("product-2", "bol.com", 180.2, False)
        performance_monitor.record_db_operation("query", 25.5, True)
        performance_monitor.record_discord_request("messages/send", 120.5, 200)
        
        # Mock logger
        with patch('src.services.performance_monitor.logging') as mock_logging:
            # Collect metrics
            await performance_monitor._collect_metrics()
            
            # Verify logging
            mock_logging.getLogger.return_value.info.assert_called()
            log_message = mock_logging.getLogger.return_value.info.call_args[0][0]
            assert "Performance metrics" in log_message
            assert "Success rate" in log_message
            
            # No warning should be logged (success rate is above threshold)
            mock_logging.getLogger.return_value.warning.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_collect_metrics_with_alert(self, performance_monitor):
        """Test metrics collection with alert condition."""
        # Set up test data with low success rate
        for i in range(8):
            performance_monitor.record_response_time(f"product-{i}", "bol.com", 150.0, False)
        
        for i in range(2):
            performance_monitor.record_response_time(f"product-{i+8}", "bol.com", 150.0, True)
        
        # Success rate should be 20% (2 out of 10)
        
        # Mock logger
        with patch('src.services.performance_monitor.logging') as mock_logging:
            # Collect metrics
            await performance_monitor._collect_metrics()
            
            # Verify warning was logged
            mock_logging.getLogger.return_value.warning.assert_called()
            warning_message = mock_logging.getLogger.return_value.warning.call_args[0][0]
            assert "Performance alert" in warning_message
            assert "Success rate" in warning_message
    
    @pytest.mark.asyncio
    async def test_cleanup_old_metrics(self, performance_monitor):
        """Test cleaning up old metrics."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 15  # 15 records deleted
        mock_conn.cursor.return_value = mock_cursor
        performance_monitor.metrics_repo.db.connect = MagicMock(return_value=mock_conn)
        
        # Mock logger
        with patch('src.services.performance_monitor.logging') as mock_logging:
            # Run cleanup
            await performance_monitor._cleanup_old_metrics()
            
            # Verify SQL execution
            mock_cursor.execute.assert_called_once()
            sql = mock_cursor.execute.call_args[0][0]
            assert "DELETE FROM monitoring_metrics" in sql
            
            # Verify commit
            mock_conn.commit.assert_called_once()
            
            # Verify logging
            mock_logging.getLogger.return_value.info.assert_called()
            log_message = mock_logging.getLogger.return_value.info.call_args[0][0]
            assert "Cleaned up 15 old metrics records" in log_message
    
    @pytest.mark.asyncio
    async def test_get_monitoring_status(self, performance_monitor):
        """Test getting monitoring status for a product."""
        # Call get_monitoring_status
        status = await performance_monitor.get_monitoring_status("test-product-123")
        
        # Verify repository was called
        performance_monitor.metrics_repo.get_monitoring_status.assert_called_once_with(
            "test-product-123", 24  # Default hours
        )
        
        # Verify returned status
        assert status["product_id"] == "test-product-123"
        assert status["success_rate"] == 95.0
        assert status["error_count"] == 2
    
    @pytest.mark.asyncio
    async def test_get_system_metrics(self, performance_monitor):
        """Test getting system-wide metrics."""
        # Add some test data
        performance_monitor.record_response_time("product-1", "bol.com", 150.5, True)
        performance_monitor.record_response_time("product-2", "bol.com", 180.2, False)
        performance_monitor.record_db_operation("query", 25.5, True)
        performance_monitor.record_discord_request("messages/send", 120.5, 200)
        performance_monitor.record_discord_request("messages/send", 130.0, 429)
        
        # Get system metrics
        metrics = await performance_monitor.get_system_metrics()
        
        # Verify metrics structure
        assert "timestamp" in metrics
        assert "success_rate" in metrics
        assert "avg_response_time" in metrics
        assert "domain_metrics" in metrics
        assert "database_metrics" in metrics
        assert "discord_metrics" in metrics
        
        # Verify calculated values
        assert metrics["success_count"] == 1
        assert metrics["error_count"] == 1
        assert metrics["success_rate"] == 50.0
        assert "bol.com" in metrics["domain_metrics"]
        assert metrics["domain_metrics"]["bol.com"]["success_rate"] == 50.0
        assert metrics["discord_metrics"]["rate_limit_count"] == 1
    
    @pytest.mark.asyncio
    async def test_get_performance_report(self, performance_monitor):
        """Test generating a comprehensive performance report."""
        # Mock database queries
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        performance_monitor.metrics_repo.db.connect = MagicMock(return_value=mock_conn)
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock cursor fetchall results for different queries
        mock_cursor.fetchall.side_effect = [
            # Product metrics query
            [
                {
                    "product_id": "test-product-1",
                    "total": 100,
                    "successes": 95,
                    "avg_duration": 150.5
                },
                {
                    "product_id": "test-product-2",
                    "total": 80,
                    "successes": 75,
                    "avg_duration": 180.2
                }
            ],
            # Error distribution query
            [
                {
                    "error_message": "Connection timeout",
                    "count": 5
                },
                {
                    "error_message": "HTML parsing error",
                    "count": 3
                }
            ],
            # Hourly metrics query
            [
                {
                    "hour": "2023-01-01 12:00:00",
                    "total": 20,
                    "successes": 19,
                    "avg_duration": 145.3
                },
                {
                    "hour": "2023-01-01 13:00:00",
                    "total": 22,
                    "successes": 20,
                    "avg_duration": 152.8
                }
            ]
        ]
        
        # Mock get_system_metrics
        performance_monitor.get_system_metrics = AsyncMock(return_value={
            "timestamp": datetime.utcnow().isoformat(),
            "success_rate": 92.5,
            "avg_response_time": 165.3,
            "total_checks_today": 180
        })
        
        # Get performance report
        report = await performance_monitor.get_performance_report(hours=24)
        
        # Verify report structure
        assert "timestamp" in report
        assert "time_window_hours" in report
        assert "system_metrics" in report
        assert "product_metrics" in report
        assert "error_distribution" in report
        assert "hourly_metrics" in report
        
        # Verify product metrics
        assert "test-product-1" in report["product_metrics"]
        assert "test-product-2" in report["product_metrics"]
        assert report["product_metrics"]["test-product-1"]["success_rate"] == 95.0
        assert report["product_metrics"]["test-product-2"]["success_rate"] == 93.75  # 75/80 * 100
        
        # Verify error distribution
        assert "Connection timeout" in report["error_distribution"]
        assert "HTML parsing error" in report["error_distribution"]
        assert report["error_distribution"]["Connection timeout"] == 5
        
        # Verify hourly metrics
        assert len(report["hourly_metrics"]) == 2
        assert report["hourly_metrics"][0]["hour"] == "2023-01-01 12:00:00"
        assert report["hourly_metrics"][0]["success_rate"] == 95.0  # 19/20 * 100
    
    @pytest.mark.asyncio
    async def test_monitoring_loop(self, performance_monitor):
        """Test the monitoring loop."""
        # Replace the mocked monitoring loop with the real one
        original_loop = performance_monitor._monitoring_loop
        performance_monitor._monitoring_loop = PerformanceMonitor._monitoring_loop
        
        # Mock the methods called by the loop
        performance_monitor._collect_metrics = AsyncMock()
        performance_monitor._cleanup_old_metrics = AsyncMock()
        
        # Mock sleep to avoid actual delays
        with patch('asyncio.sleep', AsyncMock()) as mock_sleep:
            # Start the loop
            performance_monitor.running = True
            task = asyncio.create_task(performance_monitor._monitoring_loop(performance_monitor))
            
            # Let it run for a bit
            await asyncio.sleep(0.1)
            
            # Stop the loop
            performance_monitor.running = False
            await task
            
            # Verify methods were called
            performance_monitor._collect_metrics.assert_called()
            
            # Restore the mock
            performance_monitor._monitoring_loop = original_loop
"""