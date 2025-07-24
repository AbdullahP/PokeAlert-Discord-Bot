"""
Integration tests for dashboard commands.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import discord

from src.services.admin_manager import AdminManager
from src.models.product_data import (
    DashboardData, StockChange, ProductConfig, MonitoringStatus, URLType
)
from src.config.config_manager import ConfigManager


@pytest.fixture
def mock_interaction():
    """Create mock Discord interaction."""
    interaction = Mock(spec=discord.Interaction)
    interaction.user.id = 12345
    interaction.guild_id = 67890
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.namespace = Mock()
    return interaction


@pytest.fixture
def mock_config_manager():
    """Create mock config manager."""
    config = Mock(spec=ConfigManager)
    config.get.side_effect = lambda key, default=None: {
        'dashboard.max_products_per_embed': 10,
        'dashboard.max_changes_displayed': 5,
        'dashboard.max_errors_displayed': 5,
        'discord.admin_roles': ['Admin']
    }.get(key, default)
    return config


@pytest.fixture
def mock_discord_client():
    """Create mock Discord client."""
    client = AsyncMock()
    client.validate_permissions.return_value = True
    return client


@pytest.fixture
def mock_product_manager():
    """Create mock product manager."""
    manager = AsyncMock()
    
    # Mock dashboard data
    stock_changes = [
        StockChange(
            product_id="test-product-1",
            previous_status="Out of Stock",
            current_status="In Stock",
            timestamp=datetime.utcnow() - timedelta(minutes=5)
        )
    ]
    
    dashboard_data = DashboardData(
        total_products=3,
        active_products=2,
        total_checks_today=150,
        success_rate=95.5,
        recent_stock_changes=stock_changes,
        error_summary={"Network Error": 2}
    )
    
    manager.get_dashboard_data.return_value = dashboard_data
    
    # Mock products
    products = [
        ProductConfig(
            product_id="test-product-1",
            url="https://www.bol.com/nl/nl/p/test/123/",
            url_type=URLType.PRODUCT.value,
            channel_id=12345,
            guild_id=67890,
            monitoring_interval=60,
            is_active=True,
            created_at=datetime.utcnow()
        )
    ]
    
    manager.get_products_by_guild.return_value = products
    manager.get_product_config.return_value = products[0]
    
    return manager


@pytest.fixture
def mock_performance_monitor():
    """Create mock performance monitor."""
    monitor = AsyncMock()
    
    # Mock system metrics
    system_metrics = {
        'success_rate': 95.5,
        'avg_response_time': 250.0,
        'total_checks_today': 150,
        'uptime_seconds': 86400,
        'database_metrics': {'avg_operation_time': 15.0},
        'discord_metrics': {'avg_request_time': 180.0}
    }
    
    monitor.get_system_metrics.return_value = system_metrics
    
    # Mock performance report
    performance_report = {
        'system_metrics': system_metrics,
        'product_metrics': {
            'test-product-1': {
                'success_rate': 98.0,
                'avg_duration_ms': 240.0,
                'total_checks': 50,
                'error_count': 1
            }
        },
        'error_distribution': {'Network Error': 2},
        'hourly_metrics': []
    }
    
    monitor.get_performance_report.return_value = performance_report
    
    # Mock monitoring status
    monitoring_status = MonitoringStatus(
        product_id="test-product-1",
        is_active=True,
        last_check=datetime.utcnow() - timedelta(minutes=1),
        success_rate=98.5,
        error_count=1,
        last_error="Connection timeout"
    )
    
    monitor.get_monitoring_status.return_value = monitoring_status
    
    return monitor


@pytest.fixture
def admin_manager(mock_config_manager, mock_discord_client, mock_product_manager, mock_performance_monitor):
    """Create admin manager instance."""
    return AdminManager(
        config_manager=mock_config_manager,
        discord_client=mock_discord_client,
        product_manager=mock_product_manager,
        performance_monitor=mock_performance_monitor
    )


@pytest.mark.asyncio
class TestDashboardCommands:
    """Test cases for dashboard commands."""
    
    async def test_process_dashboard_command_success(self, admin_manager, mock_interaction):
        """Test successful dashboard command processing."""
        await admin_manager.process_dashboard_command(mock_interaction)
        
        # Verify interaction was deferred
        mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
        
        # Verify followup was called with embeds
        mock_interaction.followup.send.assert_called()
        call_args = mock_interaction.followup.send.call_args
        assert 'embeds' in call_args.kwargs
        assert call_args.kwargs['ephemeral'] is True
    
    async def test_process_dashboard_command_permission_denied(self, admin_manager, mock_interaction):
        """Test dashboard command with permission denied."""
        # Mock permission validation to return False
        admin_manager.discord_client.validate_permissions.return_value = False
        
        await admin_manager.process_dashboard_command(mock_interaction)
        
        # Verify permission denied response
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert "don't have permission" in call_args.args[0]
        assert call_args.kwargs['ephemeral'] is True
    
    async def test_process_performance_dashboard_command_success(self, admin_manager, mock_interaction):
        """Test successful performance dashboard command processing."""
        mock_interaction.namespace.hours = 24
        
        await admin_manager.process_performance_dashboard_command(mock_interaction)
        
        # Verify interaction was deferred
        mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
        
        # Verify followup was called with embeds
        mock_interaction.followup.send.assert_called()
        call_args = mock_interaction.followup.send.call_args
        assert 'embeds' in call_args.kwargs
    
    async def test_process_performance_dashboard_command_no_monitor(self, mock_config_manager, mock_discord_client, mock_product_manager, mock_interaction):
        """Test performance dashboard command without performance monitor."""
        # Create admin manager without performance monitor
        admin_manager = AdminManager(
            config_manager=mock_config_manager,
            discord_client=mock_discord_client,
            product_manager=mock_product_manager,
            performance_monitor=None
        )
        
        await admin_manager.process_performance_dashboard_command(mock_interaction)
        
        # Verify error response
        mock_interaction.followup.send.assert_called()
        call_args = mock_interaction.followup.send.call_args
        # Check if embeds were sent
        if 'embeds' in call_args.kwargs:
            embeds = call_args.kwargs['embeds']
            assert len(embeds) > 0
            # Check the embed description for the error message
            embed = embeds[0]
            assert "Performance monitoring is not available" in embed.description
        else:
            # Check for direct message
            message = call_args.args[0] if call_args.args else call_args.kwargs.get('content', '')
            assert "Performance monitoring is not available" in message
    
    async def test_process_product_status_command_success(self, admin_manager, mock_interaction):
        """Test successful product status command processing."""
        mock_interaction.namespace.product_id = "test-product-1"
        mock_interaction.namespace.hours = 24
        
        await admin_manager.process_product_status_command(mock_interaction)
        
        # Verify interaction was deferred
        mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
        
        # Verify followup was called with embed
        mock_interaction.followup.send.assert_called()
        call_args = mock_interaction.followup.send.call_args
        assert 'embed' in call_args.kwargs
    
    async def test_process_product_status_command_not_found(self, admin_manager, mock_interaction):
        """Test product status command for non-existent product."""
        mock_interaction.namespace.product_id = "non-existent"
        mock_interaction.namespace.hours = 24
        
        # Mock product not found
        admin_manager.product_manager.get_product_config.return_value = None
        
        await admin_manager.process_product_status_command(mock_interaction)
        
        # Verify error response
        mock_interaction.followup.send.assert_called()
        call_args = mock_interaction.followup.send.call_args
        assert "Product not found" in call_args.args[0]
    
    async def test_process_monitoring_history_command_success(self, admin_manager, mock_interaction):
        """Test successful monitoring history command processing."""
        mock_interaction.namespace.hours = 24
        
        await admin_manager.process_monitoring_history_command(mock_interaction)
        
        # Verify interaction was deferred
        mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
        
        # Verify followup was called with embed
        mock_interaction.followup.send.assert_called()
        call_args = mock_interaction.followup.send.call_args
        assert 'embed' in call_args.kwargs
    
    async def test_process_realtime_status_command_success(self, admin_manager, mock_interaction):
        """Test successful real-time status command processing."""
        await admin_manager.process_realtime_status_command(mock_interaction)
        
        # Verify interaction was deferred
        mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
        
        # Verify followup was called with embed
        mock_interaction.followup.send.assert_called()
        call_args = mock_interaction.followup.send.call_args
        assert 'embed' in call_args.kwargs
    
    async def test_dashboard_command_error_handling(self, admin_manager, mock_interaction):
        """Test dashboard command error handling."""
        # Make dashboard service raise an exception
        admin_manager.dashboard_service.create_status_dashboard = AsyncMock(side_effect=Exception("Test error"))
        
        await admin_manager.process_dashboard_command(mock_interaction)
        
        # Verify error response
        mock_interaction.followup.send.assert_called()
        call_args = mock_interaction.followup.send.call_args
        assert "error occurred" in call_args.args[0].lower()
    
    async def test_performance_dashboard_command_error_handling(self, admin_manager, mock_interaction):
        """Test performance dashboard command error handling."""
        mock_interaction.namespace.hours = 24
        
        # Make performance monitor raise an exception
        admin_manager.performance_monitor.get_performance_report.side_effect = Exception("Test error")
        
        await admin_manager.process_performance_dashboard_command(mock_interaction)
        
        # Verify error response
        mock_interaction.followup.send.assert_called()
        call_args = mock_interaction.followup.send.call_args
        
        # Check if embeds were sent (error embeds)
        if 'embeds' in call_args.kwargs:
            embeds = call_args.kwargs['embeds']
            assert len(embeds) > 0
            # Check the embed description for the error message
            embed = embeds[0]
            assert "error" in embed.description.lower() or "failed" in embed.description.lower()
        else:
            # Check for direct message
            message = call_args.args[0] if call_args.args else call_args.kwargs.get('content', '')
            assert "error occurred" in message.lower()
    
    async def test_product_status_command_error_handling(self, admin_manager, mock_interaction):
        """Test product status command error handling."""
        mock_interaction.namespace.product_id = "test-product-1"
        mock_interaction.namespace.hours = 24
        
        # Make dashboard service raise an exception
        admin_manager.dashboard_service.create_product_status_embed = AsyncMock(side_effect=Exception("Test error"))
        
        await admin_manager.process_product_status_command(mock_interaction)
        
        # Verify error response
        mock_interaction.followup.send.assert_called()
        call_args = mock_interaction.followup.send.call_args
        assert "error occurred" in call_args.args[0].lower()
    
    async def test_monitoring_history_command_error_handling(self, admin_manager, mock_interaction):
        """Test monitoring history command error handling."""
        mock_interaction.namespace.hours = 24
        
        # Make dashboard service raise an exception
        admin_manager.dashboard_service.create_monitoring_history_embed = AsyncMock(side_effect=Exception("Test error"))
        
        await admin_manager.process_monitoring_history_command(mock_interaction)
        
        # Verify error response
        mock_interaction.followup.send.assert_called()
        call_args = mock_interaction.followup.send.call_args
        assert "error occurred" in call_args.args[0].lower()
    
    async def test_realtime_status_command_error_handling(self, admin_manager, mock_interaction):
        """Test real-time status command error handling."""
        # Make dashboard service raise an exception
        admin_manager.dashboard_service.create_real_time_status_embed = AsyncMock(side_effect=Exception("Test error"))
        
        await admin_manager.process_realtime_status_command(mock_interaction)
        
        # Verify error response
        mock_interaction.followup.send.assert_called()
        call_args = mock_interaction.followup.send.call_args
        assert "error occurred" in call_args.args[0].lower()


@pytest.mark.asyncio
class TestDashboardCommandsIntegration:
    """Integration tests for dashboard commands."""
    
    async def test_full_dashboard_workflow(self, admin_manager, mock_interaction):
        """Test complete dashboard command workflow."""
        # Test all dashboard commands in sequence
        commands = [
            ('dashboard', admin_manager.process_dashboard_command),
            ('performance', admin_manager.process_performance_dashboard_command),
            ('product_status', admin_manager.process_product_status_command),
            ('history', admin_manager.process_monitoring_history_command),
            ('realtime', admin_manager.process_realtime_status_command)
        ]
        
        for command_name, command_func in commands:
            # Reset mocks
            mock_interaction.response.reset_mock()
            mock_interaction.followup.reset_mock()
            
            # Set up namespace for commands that need it
            if command_name == 'performance':
                mock_interaction.namespace.hours = 24
            elif command_name == 'product_status':
                mock_interaction.namespace.product_id = "test-product-1"
                mock_interaction.namespace.hours = 24
            elif command_name == 'history':
                mock_interaction.namespace.hours = 24
            
            # Execute command
            await command_func(mock_interaction)
            
            # Verify command executed successfully
            assert mock_interaction.response.defer.called or mock_interaction.response.send_message.called
            assert mock_interaction.followup.send.called
    
    async def test_dashboard_commands_with_different_time_windows(self, admin_manager, mock_interaction):
        """Test dashboard commands with different time windows."""
        time_windows = [1, 6, 12, 24, 48]
        
        for hours in time_windows:
            # Reset mocks
            mock_interaction.response.reset_mock()
            mock_interaction.followup.reset_mock()
            
            # Test performance dashboard with different time windows
            mock_interaction.namespace.hours = hours
            
            await admin_manager.process_performance_dashboard_command(mock_interaction)
            
            # Verify command executed successfully
            mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
            mock_interaction.followup.send.assert_called()
            
            # Verify performance monitor was called with correct hours
            admin_manager.performance_monitor.get_performance_report.assert_called_with(hours)
    
    async def test_dashboard_commands_permission_validation(self, admin_manager, mock_interaction):
        """Test that all dashboard commands validate permissions."""
        commands = [
            admin_manager.process_dashboard_command,
            admin_manager.process_performance_dashboard_command,
            admin_manager.process_product_status_command,
            admin_manager.process_monitoring_history_command,
            admin_manager.process_realtime_status_command
        ]
        
        for command_func in commands:
            # Reset mocks
            mock_interaction.response.reset_mock()
            mock_interaction.followup.reset_mock()
            admin_manager.discord_client.validate_permissions.reset_mock()
            
            # Set up namespace for commands that need it
            mock_interaction.namespace.hours = 24
            mock_interaction.namespace.product_id = "test-product-1"
            
            # Execute command
            await command_func(mock_interaction)
            
            # Verify permission validation was called
            admin_manager.discord_client.validate_permissions.assert_called_once_with(
                mock_interaction.user.id, 
                mock_interaction.guild_id
            )