"""
Integration tests for Discord bot workflows.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from discord import app_commands, Interaction

from src.discord.client import DiscordBotClient
from src.services.admin_manager import AdminManager
from src.services.product_manager import ProductManager
from src.models.product_data import ProductConfig, URLType, DashboardData, StockChange
from datetime import datetime


class TestDiscordIntegration:
    """Integration tests for Discord bot workflows."""
    
    @pytest.fixture
    def integrated_bot(self, discord_client, admin_manager, product_manager):
        """Create an integrated Discord bot with all components."""
        # Connect the components
        discord_client.set_admin_manager(admin_manager)
        admin_manager.product_manager = product_manager
        
        return {
            "discord_client": discord_client,
            "admin_manager": admin_manager,
            "product_manager": product_manager
        }
    
    @pytest.mark.asyncio
    async def test_add_product_workflow(self, integrated_bot):
        """Test the complete add product workflow."""
        discord_client = integrated_bot["discord_client"]
        admin_manager = integrated_bot["admin_manager"]
        product_manager = integrated_bot["product_manager"]
        
        # Mock the product manager methods
        product_manager.validate_url = AsyncMock(return_value=True)
        product_manager.add_product = AsyncMock(return_value="test-product-123")
        
        # Create mock interaction
        interaction = AsyncMock()
        interaction.command.name = "add"
        interaction.guild_id = 987654321
        interaction.user.id = 222222  # Admin user
        
        # Mock namespace with command parameters
        interaction.namespace.url = "https://www.bol.com/nl/nl/p/pokemon-scarlet/9300000096287/"
        interaction.namespace.channel = MagicMock()
        interaction.namespace.channel.id = 123456789
        interaction.namespace.channel.mention = "#pokemon-alerts"
        interaction.namespace.interval = 60
        
        # Mock response methods
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        
        # Mock permission validation
        discord_client.validate_permissions = AsyncMock(return_value=True)
        
        # Call the handler
        await discord_client._handle_add_product(interaction)
        
        # Verify the workflow
        interaction.response.defer.assert_called_once()
        product_manager.validate_url.assert_called_once_with(
            "https://www.bol.com/nl/nl/p/pokemon-scarlet/9300000096287/"
        )
        product_manager.add_product.assert_called_once()
        interaction.followup.send.assert_called_once()
        
        # Verify the success message
        success_message = interaction.followup.send.call_args[0][0]
        assert "Product added successfully" in success_message
        assert "test-product-123" in success_message
        assert "#pokemon-alerts" in success_message
    
    @pytest.mark.asyncio
    async def test_remove_product_workflow(self, integrated_bot):
        """Test the complete remove product workflow."""
        discord_client = integrated_bot["discord_client"]
        admin_manager = integrated_bot["admin_manager"]
        product_manager = integrated_bot["product_manager"]
        
        # Mock the product manager methods
        product_config = ProductConfig(
            product_id="test-product-123",
            url="https://www.bol.com/nl/nl/p/pokemon-scarlet/9300000096287/",
            url_type=URLType.PRODUCT.value,
            channel_id=123456789,
            guild_id=987654321,
            monitoring_interval=60,
            role_mentions=[],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        product_manager.get_product_config = AsyncMock(return_value=product_config)
        product_manager.remove_product = AsyncMock(return_value=True)
        
        # Create mock interaction
        interaction = AsyncMock()
        interaction.command.name = "remove"
        interaction.guild_id = 987654321
        interaction.user.id = 222222  # Admin user
        
        # Mock namespace with command parameters
        interaction.namespace.product_id = "test-product-123"
        
        # Mock response methods
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        
        # Mock permission validation
        discord_client.validate_permissions = AsyncMock(return_value=True)
        
        # Call the handler
        await discord_client._handle_remove_product(interaction)
        
        # Verify the workflow
        interaction.response.defer.assert_called_once()
        product_manager.get_product_config.assert_called_once_with("test-product-123")
        product_manager.remove_product.assert_called_once_with("test-product-123")
        interaction.followup.send.assert_called_once()
        
        # Verify the success message
        success_message = interaction.followup.send.call_args[0][0]
        assert "Product removed successfully" in success_message
        assert "test-product-123" in success_message
    
    @pytest.mark.asyncio
    async def test_status_dashboard_workflow(self, integrated_bot):
        """Test the status dashboard workflow."""
        discord_client = integrated_bot["discord_client"]
        admin_manager = integrated_bot["admin_manager"]
        product_manager = integrated_bot["product_manager"]
        
        # Mock the dashboard data
        dashboard_data = DashboardData(
            total_products=5,
            active_products=4,
            total_checks_today=120,
            success_rate=95.5,
            recent_stock_changes=[
                StockChange(
                    product_id="test-product-123",
                    previous_status="Out of Stock",
                    current_status="In Stock",
                    timestamp=datetime.utcnow(),
                    price_change=None,
                    notification_sent=True
                )
            ],
            error_summary={
                "network": 2,
                "parsing": 1
            }
        )
        admin_manager.get_dashboard_data = AsyncMock(return_value=dashboard_data)
        
        # Create mock interaction
        interaction = AsyncMock()
        interaction.command.name = "status"
        interaction.guild_id = 987654321
        interaction.user.id = 222222  # Admin user
        
        # Mock response methods
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        
        # Mock permission validation
        discord_client.validate_permissions = AsyncMock(return_value=True)
        
        # Call the handler
        await discord_client._handle_status(interaction)
        
        # Verify the workflow
        interaction.response.defer.assert_called_once()
        admin_manager.get_dashboard_data.assert_called_once_with(987654321)
        interaction.followup.send.assert_called_once()
        
        # Verify the dashboard content
        dashboard_message = interaction.followup.send.call_args[0][0]
        assert "Monitoring Status" in dashboard_message
        assert "Total Products: 5" in dashboard_message
        assert "Active Products: 4" in dashboard_message
        assert "Success Rate: 95.5%" in dashboard_message
        assert "Total Checks Today: 120" in dashboard_message
    
    @pytest.mark.asyncio
    async def test_permission_denied_workflow(self, integrated_bot):
        """Test the workflow when permissions are denied."""
        discord_client = integrated_bot["discord_client"]
        
        # Create mock interaction
        interaction = AsyncMock()
        interaction.command.name = "add"
        interaction.guild_id = 987654321
        interaction.user.id = 333333  # Non-admin user
        
        # Mock response methods
        interaction.response.send_message = AsyncMock()
        
        # Mock permission validation to deny access
        discord_client.validate_permissions = AsyncMock(return_value=False)
        
        # Call the handler
        await discord_client.handle_admin_command(interaction)
        
        # Verify the error response
        interaction.response.send_message.assert_called_once()
        error_message = interaction.response.send_message.call_args[0][0]
        assert "Error:" in error_message
        assert "permission" in error_message.lower()
    
    @pytest.mark.asyncio
    async def test_invalid_url_workflow(self, integrated_bot):
        """Test the workflow with an invalid URL."""
        discord_client = integrated_bot["discord_client"]
        admin_manager = integrated_bot["admin_manager"]
        product_manager = integrated_bot["product_manager"]
        
        # Mock the product manager to reject the URL
        product_manager.validate_url = AsyncMock(return_value=False)
        
        # Create mock interaction
        interaction = AsyncMock()
        interaction.command.name = "add"
        interaction.guild_id = 987654321
        interaction.user.id = 222222  # Admin user
        
        # Mock namespace with command parameters
        interaction.namespace.url = "https://invalid-url.com/product"
        interaction.namespace.channel = MagicMock()
        interaction.namespace.channel.id = 123456789
        interaction.namespace.interval = 60
        
        # Mock response methods
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        
        # Mock permission validation
        discord_client.validate_permissions = AsyncMock(return_value=True)
        
        # Call the handler
        await discord_client._handle_add_product(interaction)
        
        # Verify the error response
        interaction.followup.send.assert_called_once()
        error_message = interaction.followup.send.call_args[0][0]
        assert "Error" in error_message
        assert "invalid" in error_message.lower() or "not supported" in error_message.lower()
    
    @pytest.mark.asyncio
    async def test_command_error_handling(self, integrated_bot):
        """Test error handling during command execution."""
        discord_client = integrated_bot["discord_client"]
        admin_manager = integrated_bot["admin_manager"]
        product_manager = integrated_bot["product_manager"]
        
        # Mock the product manager to raise an exception
        product_manager.add_product = AsyncMock(side_effect=Exception("Database error"))
        
        # Create mock interaction
        interaction = AsyncMock()
        interaction.command.name = "add"
        interaction.guild_id = 987654321
        interaction.user.id = 222222  # Admin user
        
        # Mock namespace with command parameters
        interaction.namespace.url = "https://www.bol.com/nl/nl/p/pokemon-scarlet/9300000096287/"
        interaction.namespace.channel = MagicMock()
        interaction.namespace.channel.id = 123456789
        interaction.namespace.interval = 60
        
        # Mock response methods
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        
        # Mock permission validation
        discord_client.validate_permissions = AsyncMock(return_value=True)
        product_manager.validate_url = AsyncMock(return_value=True)
        
        # Call the handler
        await discord_client._handle_add_product(interaction)
        
        # Verify the error response
        interaction.followup.send.assert_called_once()
        error_message = interaction.followup.send.call_args[0][0]
        assert "Error" in error_message
        assert "Database error" in error_message
"""