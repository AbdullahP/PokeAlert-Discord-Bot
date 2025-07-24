"""
Pytest configuration and fixtures for testing.
"""
import pytest
import tempfile
import asyncio
import os
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from src.database.connection import DatabaseConnection
from src.config.config_manager import ConfigManager
from src.services.performance_monitor import PerformanceMonitor
from src.services.error_handler import ErrorHandler
from src.services.notification_service import NotificationService
from src.services.product_manager import ProductManager
from src.services.monitoring_engine import MonitoringEngine
from src.services.admin_manager import AdminManager
from src.discord.client import DiscordBotClient


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    temp_dir = tempfile.TemporaryDirectory()
    db_path = Path(temp_dir.name) / "test_db.sqlite"
    
    # Initialize database connection
    db = DatabaseConnection(str(db_path))
    db.create_tables()
    
    yield db
    
    # Clean up
    db.close()
    temp_dir.cleanup()


@pytest.fixture
def config_manager():
    """Create a config manager with test settings."""
    config = ConfigManager()
    
    # Set test configuration values
    config.set('discord.token', 'test_token')
    config.set('discord.admin_roles', ['Admin', 'Moderator'])
    config.set('monitoring.interval', 60)
    config.set('monitoring.metrics_interval', 30)
    config.set('monitoring.alert_threshold', 80.0)
    config.set('database.path', ':memory:')
    config.set('logging.level', 'INFO')
    
    return config


@pytest.fixture
def performance_monitor(config_manager):
    """Create a performance monitor instance for testing."""
    monitor = PerformanceMonitor(config_manager)
    monitor._monitoring_loop = AsyncMock()  # Replace the monitoring loop with a mock
    return monitor


@pytest.fixture
def error_handler():
    """Create an error handler instance for testing."""
    handler = ErrorHandler()
    handler._log_to_database = AsyncMock()  # Mock database logging
    return handler


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client for testing."""
    client = AsyncMock()
    
    # Mock successful response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="<html><body>Test HTML</body></html>")
    mock_response.raise_for_status = AsyncMock()
    
    client.get = AsyncMock(return_value=mock_response)
    client.close = AsyncMock()
    
    return client


@pytest.fixture
def notification_service(config_manager):
    """Create a notification service for testing."""
    service = NotificationService(config_manager)
    service.discord_client = AsyncMock()
    service.discord_client.send_notification = AsyncMock(return_value=True)
    return service


@pytest.fixture
def product_manager(temp_db, config_manager):
    """Create a product manager for testing."""
    manager = ProductManager(config_manager)
    manager.db = temp_db
    return manager


@pytest.fixture
def monitoring_engine(config_manager, mock_http_client, performance_monitor):
    """Create a monitoring engine for testing."""
    engine = MonitoringEngine(config_manager)
    engine.http_client = mock_http_client
    engine.performance_monitor = performance_monitor
    return engine


@pytest.fixture
def admin_manager(product_manager, config_manager):
    """Create an admin manager for testing."""
    manager = AdminManager(config_manager)
    manager.product_manager = product_manager
    return manager


@pytest.fixture
def discord_client(config_manager):
    """Create a Discord client for testing."""
    with pytest.MonkeyPatch.context() as mp:
        # Mock Discord client initialization
        mp.setattr('discord.Client.__init__', lambda self, **kwargs: None)
        
        client = DiscordBotClient(config_manager)
        
        # Mock Discord client attributes and methods
        client._connection = MagicMock()
        client.user = MagicMock()
        client.user.id = 123456789
        client.guilds = []
        
        # Mock tree
        client.tree = MagicMock()
        client.tree.sync = AsyncMock()
        
        # Mock get_channel
        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock()
        client.get_channel = MagicMock(return_value=mock_channel)
        
        # Mock get_guild
        mock_guild = MagicMock()
        mock_guild.owner_id = 111111
        client.get_guild = MagicMock(return_value=mock_guild)
        
        return client