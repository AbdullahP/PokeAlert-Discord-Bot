"""
Tests for the AdminManager class.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import discord
from discord import Interaction, Embed

from src.services.admin_manager import AdminManager
from src.models.product_data import (
    DashboardData, ProductConfig, StockChange, URLType
)


@pytest.fixture
def mock_config_manager():
    """Create a mock ConfigManager."""
    config_manager = MagicMock()
    config_manager.get.return_value = 30  # Default min_interval
    return config_manager


@pytest.fixture
def mock_discord_client():
    """Create a mock DiscordBotClient."""
    discord_client = AsyncMock()
    discord_client.validate_permissions.return_value = True
    return discord_client


@pytest.fixture
def mock_product_manager():
    """Create a mock ProductManager."""
    product_manager = AsyncMock()
    product_manager.validate_url.return_value = True
    product_manager.add_product.return_value = "test-product-id"
    product_manager.get_product_config.return_value = ProductConfig(
        product_id="test-product-id",
        url="https://www.bol.com/nl/nl/p/123456/",
        url_type=URLType.PRODUCT.value,
        channel_id=123456789,
        guild_id=987654321,
        monitoring_interval=60,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    return product_manager


@pytest.fixture
def admin_manager(mock_config_manager, mock_discord_client, mock_product_manager):
    """Create an AdminManager instance with mocked dependencies."""
    return AdminManager(
        config_manager=mock_config_manager,
        discord_client=mock_discord_client,
        product_manager=mock_product_manager
    )


@pytest.fixture
def mock_interaction():
    """Create a mock Discord Interaction."""
    interaction = AsyncMock(spec=Interaction)
    interaction.user.id = 123456
    interaction.guild_id = 987654321
    interaction.namespace = MagicMock()
    interaction.namespace.url = "https://www.bol.com/nl/nl/p/123456/"
    interaction.namespace.channel = MagicMock()
    interaction.namespace.channel.id = 123456789
    interaction.namespace.channel.mention = "#test-channel"
    interaction.namespace.interval = 60
    interaction.namespace.product_id = "test-product-id"
    interaction.data = {"options": [{"name": "get"}]}
    
    # Mock response methods
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    
    return interaction


@pytest.mark.asyncio
class TestAdminManager:
    """Tests for the AdminManager class."""
    
    async def test_validate_admin_permissions(self, admin_manager, mock_discord_client):
        """Test validate_admin_permissions method."""
        # Test with valid permissions
        mock_discord_client.validate_permissions.return_value = True
        result = await admin_manager.validate_admin_permissions(123456, 987654321)
        assert result is True
        mock_discord_client.validate_permissions.assert_called_once_with(123456, 987654321)
        
        # Test with invalid permissions
        mock_discord_client.validate_permissions.reset_mock()
        mock_discord_client.validate_permissions.return_value = False
        result = await admin_manager.validate_admin_permissions(123456, 987654321)
        assert result is False
        mock_discord_client.validate_permissions.assert_called_once_with(123456, 987654321)
    
    async def test_process_add_product_command_success(self, admin_manager, mock_interaction, mock_product_manager):
        """Test process_add_product_command with successful product addition."""
        # Setup
        mock_product_manager.add_product.return_value = "new-product-id"
        
        # Execute
        await admin_manager.process_add_product_command(mock_interaction)
        
        # Verify
        mock_interaction.response.defer.assert_called_once()
        mock_product_manager.validate_url.assert_called_once_with(mock_interaction.namespace.url)
        mock_product_manager.add_product.assert_called_once()
        mock_interaction.followup.send.assert_called_once()
        assert "Product added successfully" in mock_interaction.followup.send.call_args[0][0]
    
    async def test_process_add_product_command_invalid_url(self, admin_manager, mock_interaction, mock_product_manager):
        """Test process_add_product_command with invalid URL."""
        # Setup
        mock_product_manager.validate_url.return_value = False
        
        # Execute
        await admin_manager.process_add_product_command(mock_interaction)
        
        # Verify
        mock_interaction.response.defer.assert_called_once()
        mock_product_manager.validate_url.assert_called_once_with(mock_interaction.namespace.url)
        mock_product_manager.add_product.assert_not_called()
        mock_interaction.followup.send.assert_called_once()
        assert "Invalid bol.com URL" in mock_interaction.followup.send.call_args[0][0]
    
    async def test_process_add_product_command_min_interval(self, admin_manager, mock_interaction, mock_config_manager):
        """Test process_add_product_command with interval below minimum."""
        # Setup
        mock_config_manager.get.return_value = 30
        mock_interaction.namespace.interval = 10
        
        # Execute
        await admin_manager.process_add_product_command(mock_interaction)
        
        # Verify
        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called()
        assert "Monitoring interval set to minimum value" in mock_interaction.followup.send.call_args_list[0][0][0]
    
    async def test_process_remove_product_command_success(self, admin_manager, mock_interaction, mock_product_manager):
        """Test process_remove_product_command with successful product removal."""
        # Setup
        mock_product_manager.remove_product.return_value = True
        
        # Execute
        await admin_manager.process_remove_product_command(mock_interaction)
        
        # Verify
        mock_interaction.response.defer.assert_called_once()
        mock_product_manager.get_product_config.assert_called_once_with(mock_interaction.namespace.product_id)
        mock_product_manager.remove_product.assert_called_once_with(mock_interaction.namespace.product_id)
        mock_interaction.followup.send.assert_called_once()
        assert "Product removed successfully" in mock_interaction.followup.send.call_args[0][0]
    
    async def test_process_remove_product_command_not_found(self, admin_manager, mock_interaction, mock_product_manager):
        """Test process_remove_product_command with product not found."""
        # Setup
        mock_product_manager.get_product_config.return_value = None
        
        # Execute
        await admin_manager.process_remove_product_command(mock_interaction)
        
        # Verify
        mock_interaction.response.defer.assert_called_once()
        mock_product_manager.get_product_config.assert_called_once_with(mock_interaction.namespace.product_id)
        mock_product_manager.remove_product.assert_not_called()
        mock_interaction.followup.send.assert_called_once()
        assert "Product not found" in mock_interaction.followup.send.call_args[0][0]
    
    async def test_process_status_command(self, admin_manager, mock_interaction, mock_product_manager):
        """Test process_status_command."""
        # Setup
        dashboard_data = DashboardData(
            total_products=5,
            active_products=3,
            total_checks_today=100,
            success_rate=95.5,
            recent_stock_changes=[],
            error_summary={}
        )
        mock_product_manager.get_dashboard_data.return_value = dashboard_data
        
        # Execute
        await admin_manager.process_status_command(mock_interaction)
        
        # Verify
        mock_interaction.response.defer.assert_called_once()
        mock_product_manager.get_dashboard_data.assert_called_once_with(mock_interaction.guild_id)
        mock_interaction.followup.send.assert_called_once()
        
        # Check that an embed was sent
        args, kwargs = mock_interaction.followup.send.call_args
        assert 'embed' in kwargs
        assert isinstance(kwargs['embed'], discord.Embed)
        assert kwargs['embed'].title == "Monitoring Status"
    
    async def test_process_list_products_command_with_products(self, admin_manager, mock_interaction, mock_product_manager):
        """Test process_list_products_command with products found."""
        # Setup
        products = [
            ProductConfig(
                product_id=f"test-product-{i}",
                url=f"https://www.bol.com/nl/nl/p/{i}/",
                url_type=URLType.PRODUCT.value,
                channel_id=123456789,
                guild_id=987654321,
                monitoring_interval=60,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            for i in range(3)
        ]
        mock_product_manager.get_products_by_guild.return_value = products
        
        # Execute
        await admin_manager.process_list_products_command(mock_interaction)
        
        # Verify
        mock_interaction.response.defer.assert_called_once()
        mock_product_manager.get_products_by_guild.assert_called_once_with(mock_interaction.guild_id)
        mock_interaction.followup.send.assert_called_once()
        
        # Check that an embed was sent
        args, kwargs = mock_interaction.followup.send.call_args
        assert 'embed' in kwargs
        assert isinstance(kwargs['embed'], discord.Embed)
        assert kwargs['embed'].title == "Monitored Products"
        assert "Total: 3 products" in kwargs['embed'].description
    
    async def test_process_list_products_command_no_products(self, admin_manager, mock_interaction, mock_product_manager):
        """Test process_list_products_command with no products found."""
        # Setup
        mock_product_manager.get_products_by_guild.return_value = []
        
        # Execute
        await admin_manager.process_list_products_command(mock_interaction)
        
        # Verify
        mock_interaction.response.defer.assert_called_once()
        mock_product_manager.get_products_by_guild.assert_called_once_with(mock_interaction.guild_id)
        mock_interaction.followup.send.assert_called_once()
        assert "No products are being monitored" in mock_interaction.followup.send.call_args[0][0]
    
    async def test_process_update_product_command(self, admin_manager, mock_interaction, mock_product_manager):
        """Test process_update_product_command."""
        # Setup
        mock_interaction.namespace.channel = MagicMock()
        mock_interaction.namespace.channel.id = 987654
        mock_interaction.namespace.interval = 120
        mock_interaction.namespace.active = False
        
        mock_product_manager.update_channel_assignment.return_value = True
        mock_product_manager.update_product.return_value = True
        mock_product_manager.set_product_active.return_value = True
        
        # Execute
        await admin_manager.process_update_product_command(mock_interaction)
        
        # Verify
        mock_interaction.response.defer.assert_called_once()
        mock_product_manager.get_product_config.assert_called()
        mock_product_manager.update_channel_assignment.assert_called_once_with(
            mock_interaction.namespace.product_id, 
            mock_interaction.namespace.channel.id
        )
        mock_product_manager.set_product_active.assert_called_once_with(
            mock_interaction.namespace.product_id,
            mock_interaction.namespace.active
        )
        mock_interaction.followup.send.assert_called_once()
        
        # Check that an embed was sent
        args, kwargs = mock_interaction.followup.send.call_args
        assert 'embed' in kwargs
        assert isinstance(kwargs['embed'], discord.Embed)
        assert kwargs['embed'].title == "Product Updated"
    
    async def test_get_dashboard_data(self, admin_manager, mock_product_manager):
        """Test get_dashboard_data method."""
        # Setup
        dashboard_data = DashboardData(
            total_products=5,
            active_products=3,
            total_checks_today=100,
            success_rate=95.5,
            recent_stock_changes=[],
            error_summary={}
        )
        mock_product_manager.get_dashboard_data.return_value = dashboard_data
        
        # Execute
        result = await admin_manager.get_dashboard_data(987654321)
        
        # Verify
        assert result == dashboard_data
        mock_product_manager.get_dashboard_data.assert_called_once_with(987654321)