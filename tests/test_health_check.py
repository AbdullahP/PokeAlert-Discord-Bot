"""
Tests for the health check script.
"""
import pytest
import json
from unittest.mock import patch, MagicMock

from src.health_check import check_health, main


class TestHealthCheck:
    """Test suite for health check script."""
    
    def test_check_health_success(self):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "healthy"}
        mock_response.raise_for_status = MagicMock()
        
        with patch('src.health_check.requests.get', return_value=mock_response):
            result = check_health()
            
            assert result["status"] == "healthy"
    
    def test_check_health_failure(self):
        """Test failed health check."""
        with patch('src.health_check.requests.get', side_effect=Exception("Connection refused")):
            result = check_health()
            
            assert result["status"] == "critical"
            assert "error" in result
            assert "Connection refused" in result["error"]
    
    def test_main_healthy(self):
        """Test main function with healthy status."""
        with patch('src.health_check.check_health', return_value={"status": "healthy"}), \
             patch('src.health_check.argparse.ArgumentParser.parse_args', 
                  return_value=MagicMock(host='127.0.0.1', port=8080, detailed=False, 
                                        timeout=5, json=False)):
            
            exit_code = main()
            assert exit_code == 0
    
    def test_main_degraded(self):
        """Test main function with degraded status."""
        with patch('src.health_check.check_health', return_value={"status": "degraded"}), \
             patch('src.health_check.argparse.ArgumentParser.parse_args', 
                  return_value=MagicMock(host='127.0.0.1', port=8080, detailed=False, 
                                        timeout=5, json=False)):
            
            exit_code = main()
            assert exit_code == 1
    
    def test_main_critical(self):
        """Test main function with critical status."""
        with patch('src.health_check.check_health', return_value={"status": "critical"}), \
             patch('src.health_check.argparse.ArgumentParser.parse_args', 
                  return_value=MagicMock(host='127.0.0.1', port=8080, detailed=False, 
                                        timeout=5, json=False)):
            
            exit_code = main()
            assert exit_code == 2
    
    def test_main_json_output(self):
        """Test main function with JSON output."""
        health_data = {"status": "healthy", "components": {"database": {"status": "healthy"}}}
        
        with patch('src.health_check.check_health', return_value=health_data), \
             patch('src.health_check.argparse.ArgumentParser.parse_args', 
                  return_value=MagicMock(host='127.0.0.1', port=8080, detailed=True, 
                                        timeout=5, json=True)), \
             patch('builtins.print') as mock_print:
            
            main()
            mock_print.assert_called_once_with(json.dumps(health_data, indent=2))
    
    def test_main_detailed_output(self):
        """Test main function with detailed output."""
        health_data = {
            "status": "degraded",
            "components": {
                "database": {"status": "healthy"},
                "network": {"status": "degraded", "error": "High latency"}
            }
        }
        
        with patch('src.health_check.check_health', return_value=health_data), \
             patch('src.health_check.argparse.ArgumentParser.parse_args', 
                  return_value=MagicMock(host='127.0.0.1', port=8080, detailed=True, 
                                        timeout=5, json=False)), \
             patch('builtins.print') as mock_print:
            
            main()
            # First call should print the status
            assert mock_print.call_args_list[0][0][0] == "Status: degraded"