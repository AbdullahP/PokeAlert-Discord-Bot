"""
Tests for admin manager dashboard commands.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import discord
from discord import Interaction

from src.services.admin_manager import AdminManager
from src.services.dashboard_service import DashboardService
from src.models.product_data import ProductConfig, URLType
from src.config.config_manager import ConfigManager


@pytest.fixture
def mock_config_manager():
    """Create mock config manager."""
    config = Mock(spec=ConfigManager)
    config.get.side_effect = lambda key, default=None: {
        'monitoring.min_interval': 30,
        'discord.admin_roles': ['Admin', 'Moderator']
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
    
    # Mock product config
    product_config = ProductConfig(
        product_id="test-product-1",
        url="https://www.bol.com/nl/nl/p/test/123/",
        url_type=URLType.PRODUCT.value,
        channel_id=12345,
        guild_id=67890,
        monitoring_interval=60,
        is_active=True
    )
    
    manager.get_product_config.return_value = product_config
    return manager


@pytest.fixture
def mock_performance_monitor():
    """Create mock performance monitor."""
    monitor = AsyncMock()
    return monitor


@pytest.fixture
def mock_dashboard_service():
    """Create mock dashboard service."""
    service = AsyncMock(spec=DashboardService)
    
    # Mock embeds
    mock_embed = Mock(spec=discord.Embed)
    mock_embed.title = "Test Dashboard"
    mock_embed.color = 0x00ff00
    
    service.create_status_dashboard.return_value = [mock_embed]
    service.create_performance_dashboard.return_value = [mock_embed]
    service.create_product_status_embed.return_value = mock_embed
    service.create_monitoring_history_embed.return_value = mock_embed
    service.create_real_time_status_embed.return_value = mock_embed
    
    return service


@pytest.fixture
def admin_manager(mock_config_manager, mock_discord_client, mock_product_manager, 
                 mock_performance_monitor):
    """Create admin manager instance."""
    manager = AdminManager(
        config_manager=mock_config_manager,
        discord_client=mock_discord_client,
        product_manager=mock_product_manager,
        performance_monitor=mock_performance_monitor
    )
    return manager


@pytest.fixture
def mock_interaction():
    """Create mock Discord interaction."""
    interaction = AsyncMock(spec=Interaction)
    interaction.user.id = 12345
    interaction.guild_id = 67890
    interaction.namespace = Mock()
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    return interaction


@pytest.mark.asyncio
class TestAdminManagerDashboardCommands:
    """Test cases for admin manager dashboard commands."""
    
    async def test_process_dashboard_command_success(self, admin_manager, mock_interaction):
        """Test successful dashboard command processing."""
        # Mock dashboard service
        with patch.object(admin_manager, 'dashboard_service') as mock_dashboard:
            mock_embed = Mock(spec=discord.Embed)
            mock_dashboard.create_status_dashboard.return_value = [mock_embed]
            
            await admin_manager.process_dashboard_command(mock_interaction)
            
            # Verify permissions were checked
            admin_manager.discord_client.validate_permissions.assert_called_once_with(
                mock_interaction.user.id, mock_interaction.guild_id
            )
            
            # Verify response was deferred
            mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
            
            # Verify dashboard was created
            mock_dashboard.create_status_dashboard.assert_called_once_with(mock_interaction.guild_id)
            
            # Verify response was sent
            mock_interaction.followup.send.assert_called_once()
    
    async def test_process_dashboard_command_no_permission(self, admin_manager, mock_interaction):
        """Test dashboard command without permission."""
        # Mock no permission
        admin_manager.discord_client.validate_permissions.return_value = False
        
        await admin_manager.process_dashboard_command(mock_interaction)
        
        # Verify permission error response
        mock_interaction.response.send_message.assert_called_once_with(
            "You don't have permission to use this command.", ephemeral=True
        )
        
        # Verify dashboard was not created
        assert not hasattr(admin_manager.dashboard_service, 'create_status_dashboard') or \
               not admin_manager.dashboard_service.create_status_dashboard.called
    
    async def test_process_dashboard_command_error(self, admin_manager, mock_interaction):
        """Test dashboard command error handling."""
        # Mock dashboard service to raise exception
        with patch.object(admin_manager, 'dashboard_service') as mock_dashboard:
            mock_dashboard.create_status_dashboard.side_effect = Exception("Dashboard error")
            
            await admin_manager.process_dashboard_command(mock_interaction)
            
            # Verify error response
            mock_interaction.followup.send.assert_called_once()
            call_args = mock_interaction.followup.send.call_args
            assert "Dashboard error" in call_args[1]['content']
            assert call_args[1]['ephemeral'] is True
    
    async def test_process_performance_dashboard_command_success(self, admin_manager, mock_interaction):
        """Test successful performance dashboard command processing."""
        # Set hours parameter
        mock_interaction.namespace.hours = 48
        
        with patch.object(admin_manager, 'dashboard_service') as mock_dashboard:
            mock_embed = Mock(spec=discord.Embed)
            mock_dashboard.create_performance_dashboard.return_value = [mock_embed]
            
            await admin_manager.process_performance_dashboard_command(mock_interaction)
            
            # Verify dashboard was created with correct parameters
            mock_dashboard.create_performance_dashboard.assert_called_once_with(
                mock_interaction.guild_id, 48
            )
    
    async def test_process_performance_dashboard_command_default_hours(self, admin_manager, mock_interaction):
        """Test performance dashboard command with default hours."""
        # No hours parameter set
        mock_interaction.namespace.hours = None
        
        with patch.object(admin_manager, 'dashboard_service') as mock_dashboard:
            mock_embed = Mock(spec=discord.Embed)
            mock_dashboard.create_performance_dashboard.return_value = [mock_embed]
            
            # Mock getattr to return default
            with patch('builtins.getattr', return_value=24):
                await admin_manager.process_performance_dashboard_command(mock_interaction)
            
            # Verify dashboard was created with default hours
            mock_dashboard.create_performance_dashboard.assert_called_once_with(
                mock_interaction.guild_id, 24
            )
    
    async def test_process_product_status_command_success(self, admin_manager, mock_interaction):
        """Test successful product status command processing."""
        # Set parameters
        mock_interaction.namespace.product_id = "test-product-1"
        mock_interaction.namespace.hours = 12
        
        with patch.object(admin_manager, 'dashboard_service') as mock_dashboard:
            mock_embed = Mock(spec=discord.Embed)
            mock_dashboard.create_product_status_embed.return_value = mock_embed
            
            await admin_manager.process_product_status_command(mock_interaction)
            
            # Verify product config was checked
            admin_manager.product_manager.get_product_config.assert_called_once_with("test-product-1")
            
            # Verify status embed was created
            mock_dashboard.create_product_status_embed.assert_called_once_with("test-product-1", 12)
            
            # Verify response was sent
            mock_interaction.followup.send.assert_called_once()
    
    async def test_process_product_status_command_product_not_found(self, admin_manager, mock_interaction):
        """Test product status command with non-existent product."""
        # Set parameters
        mock_interaction.namespace.product_id = "non-existent"
        
        # Mock product not found
        admin_manager.product_manager.get_product_config.return_value = None
        
        await admin_manager.process_product_status_command(mock_interaction)
        
        # Verify error response
        mock_interaction.followup.send.assert_called_once_with(
            "Product not found. Please check the product ID and try again.",
            ephemeral=True
        )
    
    async def test_process_product_status_command_wrong_guild(self, admin_manager, mock_interaction):
        """Test product status command with product from different guild."""
        # Set parameters
        mock_interaction.namespace.product_id = "test-product-1"
        mock_interaction.guild_id = 99999  # Different guild
        
        await admin_manager.process_product_status_command(mock_interaction)
        
        # Verify error response
        mock_interaction.followup.send.assert_called_once_with(
            "Product not found. Please check the product ID and try again.",
            ephemeral=True
        )
    
    async def test_process_monitoring_history_command_success(self, admin_manager, mock_interaction):
        """Test successful monitoring history command processing."""
        # Set hours parameter
        mock_interaction.namespace.hours = 6
        
        with patch.object(admin_manager, 'dashboard_service') as mock_dashboard:
            mock_embed = Mock(spec=discord.Embed)
            mock_dashboard.create_monitoring_history_embed.return_value = mock_embed
            
            await admin_manager.process_monitoring_history_command(mock_interaction)
            
            # Verify history embed was created
            mock_dashboard.create_monitoring_history_embed.assert_called_once_with(
                mock_interaction.guild_id, 6
            )
    
    async def test_process_realtime_status_command_success(self, admin_manager, mock_interaction):
        """Test successful real-time status command processing."""
        with patch.object(admin_manager, 'dashboard_service') as mock_dashboard:
            mock_embed = Mock(spec=discord.Embed)
            mock_dashboard.create_real_time_status_embed.return_value = mock_embed
            
            await admin_manager.process_realtime_status_command(mock_interaction)
            
            # Verify real-time status embed was created
            mock_dashboard.create_real_time_status_embed.assert_called_once_with(
                mock_interaction.guild_id
            )
    
    async def test_dashboard_command_multiple_embeds(self, admin_manager, mock_interaction):
        """Test dashboard command with multiple embeds."""
        with patch.object(admin_manager, 'dashboard_service') as mock_dashboard:
            # Create multiple mock embeds
            mock_embeds = [Mock(spec=discord.Embed) for _ in range(15)]  # More than 10
            mock_dashboard.create_status_dashboard.return_value = mock_embeds
            
            await admin_manager.process_dashboard_command(mock_interaction)
            
            # Verify multiple followup calls were made (batches of 10)
            assert mock_interaction.followup.send.call_count == 2
            
            # Verify first batch has 10 embeds
            first_call = mock_interaction.followup.send.call_args_list[0]
            assert len(first_call[1]['embeds']) == 10
            
            # Verify second batch has remaining embeds
            second_call = mock_interaction.followup.send.call_args_list[1]
            assert len(second_call[1]['embeds']) == 5
    
    async def test_dashboard_service_initialization(self, admin_manager):
        """Test that dashboard service is properly initialized."""
        assert hasattr(admin_manager, 'dashboard_service')
        assert isinstance(admin_manager.dashboard_service, DashboardService)
        
        # Verify dashboard service has correct dependencies
        assert admin_manager.dashboard_service.config_manager == admin_manager.config_manager
        assert admin_manager.dashboard_service.product_manager == admin_manager.product_manager
        assert admin_manager.dashboard_service.performance_monitor == admin_manager.performance_monitor
    
    async def test_all_dashboard_commands_require_permissions(self, admin_manager, mock_interaction):
        """Test that all dashboard commands require admin permissions."""
        # Mock no permission
        admin_manager.discord_client.validate_permissions.return_value = False
        
        dashboard_commands = [
            admin_manager.process_dashboard_command,
            admin_manager.process_performance_dashboard_command,
            admin_manager.process_product_status_command,
            admin_manager.process_monitoring_history_command,
            admin_manager.process_realtime_status_command
        ]
        
        for command in dashboard_commands:
            # Reset mock
            mock_interaction.response.send_message.reset_mock()
            
            await command(mock_interaction)
            
            # Verify permission error response
            mock_interaction.response.send_message.assert_called_once_with(
                "You don't have permission to use this command.", ephemeral=True
            )
    
    async def test_dashboard_commands_error_handling(self, admin_manager, mock_interaction):
        """Test error handling in all dashboard commands."""
        dashboard_commands = [
            (admin_manager.process_dashboard_command, "dashboard"),
            (admin_manager.process_performance_dashboard_command, "performance dashboard"),
            (admin_manager.process_monitoring_history_command, "monitoring history"),
            (admin_manager.process_realtime_status_command, "real-time status")
        ]
        
        for command, command_name in dashboard_commands:
            # Reset mocks
            mock_interaction.followup.send.reset_mock()
            
            # Mock dashboard service to raise exception
            with patch.object(admin_manager, 'dashboard_service') as mock_dashboard:
                mock_dashboard.create_status_dashboard.side_effect = Exception("Test error")
                mock_dashboard.create_performance_dashboard.side_effect = Exception("Test error")
                mock_dashboard.create_monitoring_history_embed.side_effect = Exception("Test error")
                mock_dashboard.create_real_time_status_embed.side_effect = Exception("Test error")
                
                await command(mock_interaction)
                
                # Verify error response
                mock_interaction.followup.send.assert_called_once()
                call_args = mock_interaction.followup.send.call_args
                assert "Test error" in call_args[1]['content']
                assert call_args[1]['ephemeral'] is True


@pytest.mark.asyncio
class TestAdminManagerDashboardIntegration:
    """Integration tests for admin manager dashboard functionality."""
    
    async def test_dashboard_workflow_integration(self, admin_manager, mock_interaction):
        """Test complete dashboard workflow integration."""
        # Test dashboard command
        with patch.object(admin_manager, 'dashboard_service') as mock_dashboard:
            mock_embed = Mock(spec=discord.Embed)
            mock_dashboard.create_status_dashboard.return_value = [mock_embed]
            
            await admin_manager.process_dashboard_command(mock_interaction)
            
            # Verify workflow
            assert admin_manager.discord_client.validate_permissions.called
            assert mock_interaction.response.defer.called
            assert mock_dashboard.create_status_dashboard.called
            assert mock_interaction.followup.send.called
    
    async def test_product_status_workflow_integration(self, admin_manager, mock_interaction):
        """Test product status workflow integration."""
        # Set parameters
        mock_interaction.namespace.product_id = "test-product-1"
        mock_interaction.namespace.hours = 24
        
        with patch.object(admin_manager, 'dashboard_service') as mock_dashboard:
            mock_embed = Mock(spec=discord.Embed)
            mock_dashboard.create_product_status_embed.return_value = mock_embed
            
            await admin_manager.process_product_status_command(mock_interaction)
            
            # Verify complete workflow
            assert admin_manager.discord_client.validate_permissions.called
            assert mock_interaction.response.defer.called
            assert admin_manager.product_manager.get_product_config.called
            assert mock_dashboard.create_product_status_embed.called
            assert mock_interaction.followup.send.called
    
    async def test_dashboard_service_dependency_injection(self, mock_config_manager, 
                                                        mock_discord_client, mock_product_manager):
        """Test dashboard service dependency injection."""
        # Create admin manager without performance monitor
        admin_manager = AdminManager(
            config_manager=mock_config_manager,
            discord_client=mock_discord_client,
            product_manager=mock_product_manager,
            performance_monitor=None
        )
        
        # Verify dashboard service was created with correct dependencies
        assert admin_manager.dashboard_service.config_manager == mock_config_manager
        assert admin_manager.dashboard_service.product_manager == mock_product_manager
        assert admin_manager.dashboard_service.performance_monitor is None
    
    async def test_parameter_handling_in_commands(self, admin_manager, mock_interaction):
        """Test parameter handling in dashboard commands."""
        # Test with various parameter combinations
        test_cases = [
            # (command, parameters, expected_calls)
            (
                admin_manager.process_performance_dashboard_command,
                {'hours': 48},
                lambda mock_dashboard: mock_dashboard.create_performance_dashboard.assert_called_with(67890, 48)
            ),
            (
                admin_manager.process_monitoring_history_command,
                {'hours': 12},
                lambda mock_dashboard: mock_dashboard.create_monitoring_history_embed.assert_called_with(67890, 12)
            ),
            (
                admin_manager.process_product_status_command,
                {'product_id': 'test-123', 'hours': 6},
                lambda mock_dashboard: mock_dashboard.create_product_status_embed.assert_called_with('test-123', 6)
            )
        ]
        
        for command, params, verification in test_cases:
            # Set parameters
            for key, value in params.items():
                setattr(mock_interaction.namespace, key, value)
            
            with patch.object(admin_manager, 'dashboard_service') as mock_dashboard:
                mock_embed = Mock(spec=discord.Embed)
                mock_dashboard.create_performance_dashboard.return_value = [mock_embed]
                mock_dashboard.create_monitoring_history_embed.return_value = mock_embed
                mock_dashboard.create_product_status_embed.return_value = mock_embed
                
                # Skip product validation for product status command
                if 'product_id' in params:
                    admin_manager.product_manager.get_product_config.return_value = Mock(guild_id=67890)
                
                await command(mock_interaction)
                
                # Verify correct parameters were passed
                verification(mock_dashboard)