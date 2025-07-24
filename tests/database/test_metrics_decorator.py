"""
Tests for the database metrics decorator.
"""
import unittest
from unittest.mock import MagicMock, patch
import time

from src.database.metrics_decorator import db_metrics, set_performance_monitor


class TestDbMetricsDecorator(unittest.TestCase):
    """Test the database metrics decorator."""
    
    def setUp(self):
        """Set up test environment."""
        # Create mock performance monitor
        self.mock_monitor = MagicMock()
        set_performance_monitor(self.mock_monitor)
    
    def test_successful_operation(self):
        """Test decorator with successful operation."""
        @db_metrics("test_query")
        def test_function():
            time.sleep(0.01)  # Small delay to ensure measurable duration
            return "success"
        
        result = test_function()
        
        self.assertEqual(result, "success")
        self.mock_monitor.record_db_operation.assert_called_once()
        
        # Check arguments
        args = self.mock_monitor.record_db_operation.call_args[0]
        self.assertEqual(args[0], "test_query")  # operation_type
        self.assertGreater(args[1], 0)  # duration_ms
        self.assertTrue(args[2])  # success
    
    def test_failed_operation(self):
        """Test decorator with failed operation."""
        @db_metrics("test_error")
        def test_function():
            time.sleep(0.01)  # Small delay to ensure measurable duration
            raise ValueError("Test error")
        
        with self.assertRaises(ValueError):
            test_function()
        
        self.mock_monitor.record_db_operation.assert_called_once()
        
        # Check arguments
        args = self.mock_monitor.record_db_operation.call_args[0]
        self.assertEqual(args[0], "test_error")  # operation_type
        self.assertGreater(args[1], 0)  # duration_ms
        self.assertFalse(args[2])  # success
    
    def test_no_performance_monitor(self):
        """Test decorator when no performance monitor is set."""
        # Reset performance monitor
        set_performance_monitor(None)
        
        @db_metrics("test_no_monitor")
        def test_function():
            return "success"
        
        # Should not raise an exception
        result = test_function()
        self.assertEqual(result, "success")


if __name__ == '__main__':
    unittest.main()