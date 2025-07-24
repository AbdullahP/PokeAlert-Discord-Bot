"""
Tests for the health check server.
"""
import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from src.services.health_check import HealthCheckServer


@pytest.fixture
def health_server():
    """Create a health check server instance for testing."""
    with patch('src.services.health_check.error_handler'), \
         patch('src.services.health_check.config'), \
         patch('src.services.health_check.db'):
        server = HealthCheckServer(host='127.0.0.1', port=8080)
        server.logger = MagicMock()
        return server


class TestHealthCheckServer:
    """Test suite for HealthCheckServer class."""
    
    @pytest.mark.asyncio
    async def test_health_handler(self, health_server):
        """Test the basic health endpoint."""
        # Mock error handler
        with patch('src.services.health_check.error_handler') as mock_error_handler:
            mock_error_handler.get_health_status.return_value = {
                "status": "healthy",
                "last_check": "2023-01-01T00:00:00",
                "components": {}
            }
            
            # Create a mock request
            request = make_mocked_request('GET', '/health')
            
            # Call the handler
            response = await health_server.health_handler(request)
            
            # Verify response
            assert response.status == 200
            body = json.loads(await response.text())
            assert body["status"] == "healthy"
            assert "timestamp" in body
    
    @pytest.mark.asyncio
    async def test_health_handler_critical(self, health_server):
        """Test the health endpoint with critical status."""
        # Mock error handler
        with patch('src.services.health_check.error_handler') as mock_error_handler:
            mock_error_handler.get_health_status.return_value = {
                "status": "critical",
                "last_check": "2023-01-01T00:00:00",
                "components": {}
            }
            
            # Create a mock request
            request = make_mocked_request('GET', '/health')
            
            # Call the handler
            response = await health_server.health_handler(request)
            
            # Verify response
            assert response.status == 503  # Service Unavailable
            body = json.loads(await response.text())
            assert body["status"] == "critical"
    
    @pytest.mark.asyncio
    async def test_detailed_health_handler(self, health_server):
        """Test the detailed health endpoint."""
        # Mock error handler
        with patch('src.services.health_check.error_handler') as mock_error_handler:
            mock_error_handler.run_health_check.return_value = {
                "status": "healthy",
                "timestamp": "2023-01-01T00:00:00",
                "components": {
                    "database": {"status": "healthy"},
                    "network": {"status": "healthy"}
                }
            }
            
            # Create a mock request
            request = make_mocked_request('GET', '/health/detailed')
            
            # Call the handler
            response = await health_server.detailed_health_handler(request)
            
            # Verify response
            assert response.status == 200
            body = json.loads(await response.text())
            assert body["status"] == "healthy"
            assert "components" in body
            assert "database" in body["components"]
            assert "network" in body["components"]
    
    @pytest.mark.asyncio
    async def test_metrics_handler(self, health_server):
        """Test the metrics endpoint."""
        # Mock error handler and database methods
        with patch('src.services.health_check.error_handler') as mock_error_handler, \
             patch.object(health_server, '_get_database_metrics') as mock_get_db_metrics, \
             patch.object(health_server, '_get_uptime') as mock_get_uptime:
            
            mock_error_handler.get_error_summary.return_value = {
                "counts": {"network:ConnectionError": 5},
                "last_errors": {},
                "total_errors": 5
            }
            
            mock_get_db_metrics.return_value = {
                "product_count": 10,
                "active_product_count": 8,
                "checks_today": 100,
                "success_rate": 95.5
            }
            
            mock_get_uptime.return_value = {
                "start_time": "2023-01-01T00:00:00",
                "uptime_seconds": 3600
            }
            
            # Create a mock request
            request = make_mocked_request('GET', '/metrics')
            
            # Call the handler
            response = await health_server.metrics_handler(request)
            
            # Verify response
            assert response.status == 200
            body = json.loads(await response.text())
            assert "timestamp" in body
            assert "errors" in body
            assert "database" in body
            assert "uptime" in body
            assert body["errors"]["total_errors"] == 5
            assert body["database"]["product_count"] == 10
    
    @pytest.mark.asyncio
    async def test_status_handler(self, health_server):
        """Test the status endpoint."""
        # Mock methods
        with patch('src.services.health_check.error_handler') as mock_error_handler, \
             patch.object(health_server, '_get_monitoring_status') as mock_get_monitoring:
            
            mock_error_handler.get_health_status.return_value = {
                "status": "healthy",
                "components": {
                    "database": {"status": "healthy"},
                    "network": {"status": "healthy"}
                }
            }
            
            mock_get_monitoring.return_value = {
                "recent_changes": [],
                "error_counts": {}
            }
            
            # Create a mock request
            request = make_mocked_request('GET', '/status')
            
            # Call the handler
            response = await health_server.status_handler(request)
            
            # Verify response
            assert response.status == 200
            body = json.loads(await response.text())
            assert "timestamp" in body
            assert "system" in body
            assert "monitoring" in body
            assert body["system"]["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_get_database_metrics(self, health_server):
        """Test getting database metrics."""
        # Mock database
        with patch('src.services.health_check.db') as mock_db:
            # Mock cursor and fetchone results
            mock_cursor = MagicMock()
            mock_cursor.fetchone.side_effect = [
                [10],  # product_count
                [8],   # active_product_count
                [100], # checks_today
                [95]   # successful_checks
            ]
            mock_db.execute.return_value = mock_cursor
            
            # Call the method
            result = health_server._get_database_metrics()
            
            # Verify result
            assert result["product_count"] == 10
            assert result["active_product_count"] == 8
            assert result["checks_today"] == 100
            assert result["success_rate"] == 95.0
    
    @pytest.mark.asyncio
    async def test_get_monitoring_status(self, health_server):
        """Test getting monitoring status."""
        # Mock database
        with patch('src.services.health_check.db') as mock_db:
            # Mock cursor and fetchall results for stock changes
            mock_cursor1 = MagicMock()
            mock_cursor1.fetchall.return_value = [
                {
                    "product_id": "product-123",
                    "title": "Pokemon Scarlet",
                    "previous_status": "Out of Stock",
                    "current_status": "In Stock",
                    "timestamp": "2023-01-01T12:00:00",
                    "notification_sent": 1
                }
            ]
            
            # Mock cursor and fetchall results for error counts
            mock_cursor2 = MagicMock()
            mock_cursor2.fetchall.return_value = [
                {"error_message": "Connection refused", "count": 5}
            ]
            
            mock_db.execute.side_effect = [mock_cursor1, mock_cursor2]
            
            # Call the method
            result = health_server._get_monitoring_status()
            
            # Verify result
            assert "recent_changes" in result
            assert len(result["recent_changes"]) == 1
            assert result["recent_changes"][0]["product_id"] == "product-123"
            assert "error_counts" in result
            assert "Connection refused" in result["error_counts"]
            assert result["error_counts"]["Connection refused"] == 5
    
    @pytest.mark.asyncio
    async def test_start_and_stop(self, health_server):
        """Test starting and stopping the server."""
        # Mock web.AppRunner and web.TCPSite
        with patch('aiohttp.web.AppRunner') as mock_runner_class, \
             patch('aiohttp.web.TCPSite') as mock_site_class:
            
            mock_runner = MagicMock()
            mock_runner.setup = AsyncMock()
            mock_runner.cleanup = AsyncMock()
            mock_runner_class.return_value = mock_runner
            
            mock_site = MagicMock()
            mock_site.start = AsyncMock()
            mock_site_class.return_value = mock_site
            
            # Start server
            await health_server.start()
            
            # Verify server was started
            mock_runner_class.assert_called_once_with(health_server.app)
            mock_runner.setup.assert_called_once()
            mock_site_class.assert_called_once_with(mock_runner, '127.0.0.1', 8080)
            mock_site.start.assert_called_once()
            assert health_server._running is True
            
            # Stop server
            await health_server.stop()
            
            # Verify server was stopped
            mock_runner.cleanup.assert_called_once()
            assert health_server._running is False