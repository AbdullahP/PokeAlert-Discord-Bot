"""
Tests for Discord client dashboard commands.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import discord
from discord import Interaction

from src.discord.client import DiscordBotClient
from src.config.config_manager import ConfigManager


@pytest.fixture
def mock_config_manager():
    """Create mock config manager."""
    config = Mock(spec=ConfigManager)
    config.get.side_effect = lambda key, default=None: {
        'discord.admin_roles': ['Admin', 'Moderator']
    }.get(key, default)
    return config


@pytest.fixture
def mock_admin_manager():
    """Create mock admin manager."""
    manager = AsyncMock()
    return manager


@pytest.fixture
def mock_product_manager():
    """Create mock product manager."""
    manager = AsyncMock()
    return manager


@pytest.fixture
def discord_client(mock_config_manager):
    """Create Discord client instance."""
    client = DiscordBotClient(mock_config_manager)
    return client


@pytest.fixture
def mock_interaction():
    """Create mock Discord interaction."""
    interaction = AsyncMock(spec=Interaction)
    interaction.user.id = 12345
    interaction.guild_id = 67890
    interaction.command.name = "dashboard"
    interaction.namespace = Mock()
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    return interaction


@pytest.mark.asyncio
class TestDiscordDashboardCommands:
    """Test cases for Discord client dashboard commands."""
    
    async def test_handle_dashboard_command_with_admin_manager(self, discord_client, mock_interaction, mock_admin_manager):
        """Test dashboard command with admin manager available."""
        discord_client._admin_manager = mock_admin_manager
        
        await discord_client._handle_dashboard(mock_interaction)
        
        # Verify admin manager was called
        mock_admin_manager.process_dashboard_command.assert_called_once_with(mock_interaction)
    
    async def test_handle_dashboard_command_without_admin_manager(self, discord_client, mock_interaction):
        """Test dashboard command without admin manager."""
        discord_client._admin_manager = None
        
        await discord_client._handle_dashboard(mock_interaction)
        
        # Verify error response
        mock_interaction.response.send_message.assert_called_once_with(
            "Dashboard command requires admin manager. Please try again later.",
            ephemeral=True
        )
    
    async def test_handle_performance_dashboard_command_with_admin_manager(self, discord_client, mock_interaction, mock_admin_manager):
        """Test performance dashboard command with admin manager available."""
        discord_client._admin_manager = mock_admin_manager
        
        await discord_client._handle_performance_dashboard(mock_interaction)
        
        # Verify admin manager was called
        mock_admin_manager.process_performance_dashboard_command.assert_called_once_with(mock_interaction)
    
    async def test_handle_performance_dashboard_command_without_admin_manager(self, discord_client, mock_interaction):
        """Test performance dashboard command without admin manager."""
        discord_client._admin_manager = None
        
        await discord_client._handle_performance_dashboard(mock_interaction)
        
        # Verify error response
        mock_interaction.response.send_message.assert_called_once_with(
            "Performance dashboard command requires admin manager. Please try again later.",
            ephemeral=True
        )
    
    async def test_handle_product_status_command_with_admin_manager(self, discord_client, mock_interaction, mock_admin_manager):
        """Test product status command with admin manager available."""
        discord_client._admin_manager = mock_admin_manager
        
        await discord_client._handle_product_status(mock_interaction)
        
        # Verify admin manager was called
        mock_admin_manager.process_product_status_command.assert_called_once_with(mock_interaction)
    
    async def test_handle_product_status_command_without_admin_manager(self, discord_client, mock_interaction):
        """Test product status command without admin manager."""
        discord_client._admin_manager = None
        
        await discord_client._handle_product_status(mock_interaction)
        
        # Verify error response
        mock_interaction.response.send_message.assert_called_once_with(
            "Product status command requires admin manager. Please try again later.",
            ephemeral=True
        )
    
    async def test_handle_monitoring_history_command_with_admin_manager(self, discord_client, mock_interaction, mock_admin_manager):
        """Test monitoring history command with admin manager available."""
        discord_client._admin_manager = mock_admin_manager
        
        await discord_client._handle_monitoring_history(mock_interaction)
        
        # Verify admin manager was called
        mock_admin_manager.process_monitoring_history_command.assert_called_once_with(mock_interaction)
    
    async def test_handle_monitoring_history_command_without_admin_manager(self, discord_client, mock_interaction):
        """Test monitoring history command without admin manager."""
        discord_client._admin_manager = None
        
        await discord_client._handle_monitoring_history(mock_interaction)
        
        # Verify error response
        mock_interaction.response.send_message.assert_called_once_with(
            "Monitoring history command requires admin manager. Please try again later.",
            ephemeral=True
        )
    
    async def test_handle_realtime_status_command_with_admin_manager(self, discord_client, mock_interaction, mock_admin_manager):
        """Test real-time status command with admin manager available."""
        discord_client._admin_manager = mock_admin_manager
        
        await discord_client._handle_realtime_status(mock_interaction)
        
        # Verify admin manager was called
        mock_admin_manager.process_realtime_status_command.assert_called_once_with(mock_interaction)
    
    async def test_handle_realtime_status_command_without_admin_manager(self, discord_client, mock_interaction):
        """Test real-time status command without admin manager."""
        discord_client._admin_manager = None
        
        await discord_client._handle_realtime_status(mock_interaction)
        
        # Verify error response
        mock_interaction.response.send_message.assert_called_once_with(
            "Real-time status command requires admin manager. Please try again later.",
            ephemeral=True
        )
    
    async def test_command_handler_registration(self, discord_client):
        """Test that dashboard command handlers are registered."""
        # Setup commands to register handlers
        with patch.object(discord_client.tree, 'sync', new_callable=AsyncMock):
            await discord_client.setup_commands()
        
        expected_handlers = [
            "dashboard",
            "performance",
            "product_status",
            "history",
            "realtime"
        ]
        
        for handler_name in expected_handlers:
            assert handler_name in discord_client._command_handlers
    
    async def test_dashboard_command_routing(self, discord_client, mock_interaction, mock_admin_manager):
        """Test that dashboard commands are routed correctly."""
        # Setup commands to register handlers
        with patch.object(discord_client.tree, 'sync', new_callable=AsyncMock):
            await discord_client.setup_commands()
        
        discord_client._admin_manager = mock_admin_manager
        
        # Test different command names
        command_tests = [
            ("dashboard", "_handle_dashboard", "process_dashboard_command"),
            ("performance", "_handle_performance_dashboard", "process_performance_dashboard_command"),
            ("product_status", "_handle_product_status", "process_product_status_command"),
            ("history", "_handle_monitoring_history", "process_monitoring_history_command"),
            ("realtime", "_handle_realtime_status", "process_realtime_status_command")
        ]
        
        for command_name, handler_method, admin_method in command_tests:
            # Reset mocks
            mock_admin_manager.reset_mock()
            
            # Set command name
            mock_interaction.command.name = command_name
            
            # Call handle_admin_command which should route to the correct handler
            await discord_client.handle_admin_command(mock_interaction)
            
            # Verify the correct admin manager method was called
            admin_manager_method = getattr(mock_admin_manager, admin_method)
            admin_manager_method.assert_called_once_with(mock_interaction)


@pytest.mark.asyncio
class TestDiscordDashboardCommandsIntegration:
    """Integration tests for Discord dashboard commands."""
    
    async def test_full_command_workflow(self, discord_client, mock_interaction, mock_admin_manager):
        """Test full command workflow from Discord to admin manager."""
        discord_client._admin_manager = mock_admin_manager
        
        # Test dashboard command workflow
        mock_interaction.command.name = "dashboard"
        
        await discord_client.handle_admin_command(mock_interaction)
        
        # Verify the workflow
        mock_admin_manager.process_dashboard_command.assert_called_once_with(mock_interaction)
    
    async def test_command_error_handling(self, discord_client, mock_interaction, mock_admin_manager):
        """Test command error handling."""
        discord_client._admin_manager = mock_admin_manager
        
        # Make admin manager raise an exception
        mock_admin_manager.process_dashboard_command.side_effect = Exception("Test error")
        
        mock_interaction.command.name = "dashboard"
        
        # Should not raise exception due to error handling in handle_admin_command
        await discord_client.handle_admin_command(mock_interaction)
        
        # Verify error response was sent
        mock_interaction.response.send_message.assert_called_once()
    
    async def test_command_permission_validation(self, discord_client, mock_interaction):
        """Test that commands validate permissions."""
        # Mock permission validation to fail
        with patch.object(discord_client, 'validate_permissions', return_value=False):
            with patch.object(discord_client, '_validate_admin_command') as mock_validate:
                from src.discord.client import CommandError
                mock_validate.side_effect = CommandError("No permission")
                
                mock_interaction.command.name = "dashboard"
                
                await discord_client.handle_admin_command(mock_interaction)
                
                # Verify error response
                mock_interaction.response.send_message.assert_called_once()
                call_args = mock_interaction.response.send_message.call_args
                assert "No permission" in call_args[0][0]
    
    async def test_all_dashboard_commands_exist(self, discord_client):
        """Test that all expected dashboard commands are registered."""
        # Setup commands to register handlers
        with patch.object(discord_client.tree, 'sync', new_callable=AsyncMock):
            await discord_client.setup_commands()
        
        expected_commands = [
            "dashboard",
            "performance", 
            "product_status",
            "history",
            "realtime"
        ]
        
        for command_name in expected_commands:
            assert command_name in discord_client._command_handlers
            
            # Verify handler exists and is callable
            handler = discord_client._command_handlers[command_name]
            assert callable(handler)
    
    async def test_command_handler_fallback_behavior(self, discord_client, mock_interaction):
        """Test command handler fallback when admin manager is not available."""
        # Setup commands to register handlers
        with patch.object(discord_client.tree, 'sync', new_callable=AsyncMock):
            await discord_client.setup_commands()
        
        discord_client._admin_manager = None
        
        dashboard_commands = [
            "dashboard",
            "performance",
            "product_status", 
            "history",
            "realtime"
        ]
        
        for command_name in dashboard_commands:
            # Reset mock
            mock_interaction.response.send_message.reset_mock()
            
            # Call handler directly
            handler = discord_client._command_handlers[command_name]
            await handler(mock_interaction)
            
            # Verify fallback error message
            mock_interaction.response.send_message.assert_called_once()
            call_args = mock_interaction.response.send_message.call_args
            assert "requires admin manager" in call_args[0][0]
            assert call_args[1]['ephemeral'] is True


@pytest.mark.asyncio 
class TestDiscordCommandSetup:
    """Test Discord command setup and registration."""
    
    async def test_setup_commands_includes_dashboard_commands(self, discord_client):
        """Test that setup_commands includes all dashboard commands."""
        # Mock the tree sync to avoid actual Discord API calls
        with patch.object(discord_client.tree, 'sync', new_callable=AsyncMock):
            await discord_client.setup_commands()
        
        # Verify dashboard command handlers are registered
        dashboard_handlers = [
            "dashboard",
            "performance", 
            "product_status",
            "history",
            "realtime"
        ]
        
        for handler_name in dashboard_handlers:
            assert handler_name in discord_client._command_handlers
    
    async def test_command_descriptions_and_parameters(self, discord_client):
        """Test that commands have proper descriptions and parameters."""
        # Setup commands to register handlers
        with patch.object(discord_client.tree, 'sync', new_callable=AsyncMock):
            await discord_client.setup_commands()
        
        # This would typically test the actual slash command setup
        # For now, we verify the handlers exist
        
        required_handlers = {
            "dashboard": discord_client._handle_dashboard,
            "performance": discord_client._handle_performance_dashboard,
            "product_status": discord_client._handle_product_status,
            "history": discord_client._handle_monitoring_history,
            "realtime": discord_client._handle_realtime_status
        }
        
        for handler_name, expected_handler in required_handlers.items():
            actual_handler = discord_client._command_handlers.get(handler_name)
            assert actual_handler == expected_handler
    
    async def test_command_tree_registration(self, discord_client):
        """Test that commands are properly registered with the command tree."""
        # Mock tree operations
        with patch.object(discord_client.tree, 'add_command') as mock_add_command:
            with patch.object(discord_client.tree, 'command') as mock_command:
                with patch.object(discord_client.tree, 'sync', new_callable=AsyncMock):
                    await discord_client.setup_commands()
        
        # Verify tree.sync was called (commands were registered)
        discord_client.tree.sync.assert_called_once()