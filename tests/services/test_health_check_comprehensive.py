"""
Comprehensive tests for the health check system.
"""
import pytest
import asyncio
import json
from unittest.mock import MagicMock, AsyncMock, patch
import aiohttp
import sqlite3
from datetime import datetime, timedelta

from src.services.health_check import HealthCheckService
from src.config.config_manager import ConfigManager


class TestHealthCheckComprehensive:
    """Comprehensive test suite for the health check system."""
    
    @pytest.fixture
    def config_manager(self):
        """Create a config manager with test settings."""
        config = ConfigManager()
        config.set('monitoring.health_check_interval', 60)
        config.set('monitoring.critical_error_threshold', 5)
        config.set('monitoring.warning_error_threshold', 3)
        return config
    
    @pytest.fixture
    def health_check_service(self, config_manager):
        """Create a health check service for testing."""
        service = HealthCheckService(config_manager)
        
        # Mock dependencies
        service.db = MagicMock()
        service.db.execute = MagicMock(return_value=True)
        
        service.monitoring_engine = MagicMock()
        service.monitoring_engine.get_monitoring_status = AsyncMock(return_value={
            "active_products": 5,
            "success_rate": 95.0,
            "error_count": 2
        })
        
        service.error_handler = MagicMock()
        service.error_handler.get_error_summary = MagicMock(return_value={
            "total_errors": 3,
            "counts": {
                "network": 2,
                "parsing": 1
            }
        })
        
        return service
    
    @pytest.mark.asyncio
    async def test_check_database_health(self, health_check_service):
        """Test database health check."""
        # Test successful database check
        result = await health_check_service.check_database_health()
        assert result["status"] == "healthy"
        
        # Test database error
        health_check_service.db.execute = MagicMock(side_effect=sqlite3.Error("database is locked"))
        result = await health_check_service.check_database_health()
        assert result["status"] == "critical"
        assert "database is locked" in result["error"]
    
    @pytest.mark.asyncio
    async def test_check_monitoring_health(self, health_check_service):
        """Test monitoring system health check."""
        # Test healthy monitoring
        result = await health_check_service.check_monitoring_health()
        assert result["status"] == "healthy"
        assert result["active_products"] == 5
        assert result["success_rate"] == 95.0
        
        # Test degraded monitoring (lower success rate)
        health_check_service.monitoring_engine.get_monitoring_status = AsyncMock(return_value={
            "active_products": 5,
            "success_rate": 75.0,
            "error_count": 8
        })
        result = await health_check_service.check_monitoring_health()
        assert result["status"] == "degraded"
        
        # Test critical monitoring (very low success rate)
        health_check_service.monitoring_engine.get_monitoring_status = AsyncMock(return_value={
            "active_products": 5,
            "success_rate": 50.0,
            "error_count": 15
        })
        result = await health_check_service.check_monitoring_health()
        assert result["status"] == "critical"
        
        # Test error in monitoring check
        health_check_service.monitoring_engine.get_monitoring_status = AsyncMock(
            side_effect=Exception("Monitoring engine error")
        )
        result = await health_check_service.check_monitoring_health()
        assert result["status"] == "critical"
        assert "Monitoring engine error" in result["error"]
    
    @pytest.mark.asyncio
    async def test_check_discord_health(self, health_check_service):
        """Test Discord API health check."""
        # Mock Discord client
        health_check_service.discord_client = MagicMock()
        health_check_service.discord_client.is_ready = MagicMock(return_value=True)
        health_check_service.discord_client.latency = 0.05  # 50ms latency
        
        # Test healthy Discord connection
        result = await health_check_service.check_discord_health()
        assert result["status"] == "healthy"
        assert result["latency_ms"] == 50
        
        # Test high latency
        health_check_service.discord_client.latency = 0.5  # 500ms latency
        result = await health_check_service.check_discord_health()
        assert result["status"] == "degraded"
        assert result["latency_ms"] == 500
        
        # Test disconnected
        health_check_service.discord_client.is_ready = MagicMock(return_value=False)
        result = await health_check_service.check_discord_health()
        assert result["status"] == "critical"
        assert "disconnected" in result["error"].lower()
        
        # Test no Discord client
        health_check_service.discord_client = None
        result = await health_check_service.check_discord_health()
        assert result["status"] == "unknown"
    
    @pytest.mark.asyncio
    async def test_check_external_api_health(self, health_check_service):
        """Test external API health check."""
        # Mock HTTP client
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status = AsyncMock()
        
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            # Test successful API check
            result = await health_check_service.check_external_api_health()
            assert result["status"] == "healthy"
            
            # Test slow API response
            async def delayed_get(*args, **kwargs):
                await asyncio.sleep(2)  # Simulate slow response
                return mock_response
                
            mock_session.__aenter__.return_value.get = delayed_get
            result = await health_check_service.check_external_api_health()
            assert result["status"] == "degraded"
            assert "slow response" in result["warning"].lower()
            
            # Test API error
            mock_session.__aenter__.return_value.get = AsyncMock(
                side_effect=aiohttp.ClientError("Connection refused")
            )
            result = await health_check_service.check_external_api_health()
            assert result["status"] == "critical"
            assert "connection refused" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_run_health_check(self, health_check_service):
        """Test running a complete health check."""
        # Mock individual health checks
        health_check_service.check_database_health = AsyncMock(return_value={
            "status": "healthy",
            "last_query_time_ms": 5
        })
        health_check_service.check_monitoring_health = AsyncMock(return_value={
            "status": "healthy",
            "active_products": 5,
            "success_rate": 95.0
        })
        health_check_service.check_discord_health = AsyncMock(return_value={
            "status": "healthy",
            "latency_ms": 50
        })
        health_check_service.check_external_api_health = AsyncMock(return_value={
            "status": "healthy",
            "response_time_ms": 150
        })
        
        # Run health check
        result = await health_check_service.run_health_check()
        
        # Verify result structure
        assert "timestamp" in result
        assert "status" in result
        assert "components" in result
        assert "database" in result["components"]
        assert "monitoring" in result["components"]
        assert "discord" in result["components"]
        assert "external_api" in result["components"]
        
        # Verify overall status is healthy
        assert result["status"] == "healthy"
        
        # Test with one degraded component
        health_check_service.check_discord_health = AsyncMock(return_value={
            "status": "degraded",
            "latency_ms": 500,
            "warning": "High latency"
        })
        
        result = await health_check_service.run_health_check()
        assert result["status"] == "degraded"
        
        # Test with one critical component
        health_check_service.check_database_health = AsyncMock(return_value={
            "status": "critical",
            "error": "Database connection failed"
        })
        
        result = await health_check_service.run_health_check()
        assert result["status"] == "critical"
    
    @pytest.mark.asyncio
    async def test_health_check_background_task(self, health_check_service):
        """Test the health check background task."""
        # Mock run_health_check to return different results on successive calls
        health_results = [
            {"status": "healthy", "components": {}},
            {"status": "degraded", "components": {}},
            {"status": "critical", "components": {}}
        ]
        
        health_check_service.run_health_check = AsyncMock(side_effect=health_results)
        
        # Mock sleep to avoid actual delays
        with patch('asyncio.sleep', AsyncMock()) as mock_sleep:
            # Start the background task
            task = asyncio.create_task(health_check_service._health_check_loop())
            
            # Let it run for a few iterations
            await asyncio.sleep(0.1)
            
            # Stop the task
            health_check_service.running = False
            await task
            
            # Verify health check was called multiple times
            assert health_check_service.run_health_check.call_count >= 1
            
            # Verify health status was updated
            assert health_check_service.last_health_status["status"] == "critical"
    
    @pytest.mark.asyncio
    async def test_get_health_status(self, health_check_service):
        """Test getting the current health status."""
        # Set a test health status
        test_status = {
            "status": "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "database": {"status": "healthy"},
                "monitoring": {"status": "degraded", "warning": "High error rate"}
            }
        }
        health_check_service.last_health_status = test_status
        
        # Get the status
        status = health_check_service.get_health_status()
        
        # Verify it matches what we set
        assert status["status"] == "degraded"
        assert "timestamp" in status
        assert status["components"]["monitoring"]["status"] == "degraded"
    
    @pytest.mark.asyncio
    async def test_health_check_with_timeout(self, health_check_service):
        """Test health check with timeout handling."""
        # Mock a health check that takes too long
        async def slow_check():
            await asyncio.sleep(2)  # Simulate slow check
            return {"status": "healthy"}
            
        health_check_service.check_external_api_health = slow_check
        
        # Set a short timeout
        health_check_service.timeout = 0.5
        
        # Run the check
        result = await health_check_service.check_external_api_health_with_timeout()
        
        # Verify timeout was detected
        assert result["status"] == "critical"
        assert "timeout" in result["error"].lower()
"""