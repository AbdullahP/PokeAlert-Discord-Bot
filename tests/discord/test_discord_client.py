"""
Integration tests for Discord bot client and command handling.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import discord
from discord import app_commands, Interaction

from src.discord.client import DiscordBotClient, CommandError
from src.config.config_manager import ConfigManager
from src.models.product_data import ProductConfig, URLType


@pytest.fixture
def config_manager():
    """Create a mock config manager."""
    config = ConfigManager()
    config.set('discord.admin_roles', ['Admin', 'Moderator'])
    return config


@pytest.fixture
def mock_product_manager():
    """Create a mock product manager."""
    product_manager = AsyncMock()
    
    # Mock validate_url method
    product_manager.validate_url.return_value = True
    
    # Mock add_product method
    product_manager.add_product.return_value = "test-product-id"
    
    # Mock get_product_config method
    mock_config = ProductConfig(
        product_id="test-product-id",
        url="https://www.bol.com/nl/nl/p/12345/",
        url_type=URLType.PRODUCT.value,
        channel_id=123456789,
        guild_id=987654321,
        monitoring_interval=60
    )
    product_manager.get_product_config.return_value = mock_config
    
    # Mock remove_product method
    product_manager.remove_product.return_value = True
    
    # Mock get_products_by_channel method
    product_manager.get_products_by_channel.return_value = [mock_config]
    
    # Mock get_products_by_guild method
    product_manager.get_products_by_guild.return_value = [mock_config]
    
    # Mock get_dashboard_data method
    from src.models.product_data import DashboardData, StockChange
    from datetime import datetime
    
    mock_dashboard = DashboardData(
        total_products=1,
        active_products=1,
        total_checks_today=10,
        success_rate=95.0,
        recent_stock_changes=[
            StockChange(
                product_id="test-product-id",
                previous_status="Out of Stock",
                current_status="In Stock",
                timestamp=datetime.utcnow()
            )
        ],
        error_summary={}
    )
    product_manager.get_dashboard_data.return_value = mock_dashboard
    
    return product_manager


@pytest.fixture
def discord_client(config_manager, mock_product_manager):
    """Create a Discord client with mocked dependencies."""
    with patch('discord.Client.__init__', return_value=None):
        client = DiscordBotClient(config_manager)
        
        # Mock Discord client attributes and methods
        client._connection = MagicMock()
        client.user = MagicMock()
        client.user.id = 123456789
        client.guilds = []
        
        # Mock tree
        client.tree = MagicMock()
        client.tree.sync = AsyncMock()
        
        # Set product manager
        client.set_product_manager(mock_product_manager)
        
        # Mock get_channel
        mock_channel = AsyncMock()
        mock_channel.send = AsyncMock()
        client.get_channel = MagicMock(return_value=mock_channel)
        
        # Mock get_guild
        mock_guild = MagicMock()
        mock_guild.owner_id = 111111
        
        # Mock member with admin role
        mock_admin = MagicMock()
        mock_admin.id = 222222
        mock_admin.guild_permissions.administrator = False
        mock_admin_role = MagicMock()
        mock_admin_role.name = "Admin"
        mock_admin.roles = [mock_admin_role]
        
        # Mock member without admin role
        mock_user = MagicMock()
        mock_user.id = 333333
        mock_user.guild_permissions.administrator = False
        mock_user.roles = []
        
        # Add members to guild
        mock_guild.get_member = MagicMock(side_effect=lambda id: {
            111111: mock_guild.owner,
            222222: mock_admin,
            333333: mock_user
        }.get(id))
        
        client.get_guild = MagicMock(return_value=mock_guild)
        
        return client


@pytest.mark.asyncio
async def test_validate_permissions_admin(discord_client):
    """Test permission validation for admin users."""
    # Test guild owner
    assert await discord_client.validate_permissions(111111, 987654321)
    
    # Test user with admin role
    assert await discord_client.validate_permissions(222222, 987654321)
    
    # Test user without admin role
    assert not await discord_client.validate_permissions(333333, 987654321)
    
    # Test non-existent user
    assert not await discord_client.validate_permissions(444444, 987654321)
    
    # Test non-existent guild
    discord_client.get_guild = MagicMock(return_value=None)
    assert not await discord_client.validate_permissions(222222, 999999)


@pytest.mark.asyncio
async def test_handle_add_product_command(discord_client, mock_product_manager):
    """Test handling add product command."""
    # Create mock interaction
    interaction = AsyncMock()
    interaction.command.name = "add"
    interaction.guild_id = 987654321
    interaction.user.id = 222222  # Admin user
    
    # Mock namespace with command parameters
    interaction.namespace.url = "https://www.bol.com/nl/nl/p/12345/"
    interaction.namespace.channel = MagicMock()
    interaction.namespace.channel.id = 123456789
    interaction.namespace.channel.mention = "#test-channel"
    interaction.namespace.interval = 60
    
    # Mock response methods
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    
    # Call the handler
    await discord_client._handle_add_product(interaction)
    
    # Verify interactions
    interaction.response.defer.assert_called_once()
    mock_product_manager.add_product.assert_called_once_with(
        url="https://www.bol.com/nl/nl/p/12345/",
        channel_id=123456789,
        guild_id=987654321,
        monitoring_interval=60
    )
    interaction.followup.send.assert_called_once()
    assert "Product added successfully" in interaction.followup.send.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_remove_product_command(discord_client, mock_product_manager):
    """Test handling remove product command."""
    # Create mock interaction
    interaction = AsyncMock()
    interaction.command.name = "remove"
    interaction.guild_id = 987654321
    interaction.user.id = 222222  # Admin user
    
    # Mock namespace with command parameters
    interaction.namespace.product_id = "test-product-id"
    
    # Mock response methods
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    
    # Call the handler
    await discord_client._handle_remove_product(interaction)
    
    # Verify interactions
    interaction.response.defer.assert_called_once()
    mock_product_manager.get_product_config.assert_called_once_with("test-product-id")
    mock_product_manager.remove_product.assert_called_once_with("test-product-id")
    interaction.followup.send.assert_called_once()
    assert "Product removed successfully" in interaction.followup.send.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_list_products_command(discord_client, mock_product_manager):
    """Test handling list products command."""
    # Create mock interaction
    interaction = AsyncMock()
    interaction.command.name = "list"
    interaction.guild_id = 987654321
    interaction.user.id = 222222  # Admin user
    
    # Mock namespace with command parameters
    interaction.namespace.channel = None  # Test listing all guild products
    
    # Mock response methods
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    
    # Call the handler
    await discord_client._handle_list_products(interaction)
    
    # Verify interactions
    interaction.response.defer.assert_called_once()
    mock_product_manager.get_products_by_guild.assert_called_once_with(987654321)
    interaction.followup.send.assert_called_once()
    
    # Test with specific channel
    interaction.namespace.channel = MagicMock()
    interaction.namespace.channel.id = 123456789
    interaction.namespace.channel.mention = "#test-channel"
    
    await discord_client._handle_list_products(interaction)
    mock_product_manager.get_products_by_channel.assert_called_once_with(123456789)


@pytest.mark.asyncio
async def test_handle_status_command(discord_client, mock_product_manager):
    """Test handling status command."""
    # Create mock interaction
    interaction = AsyncMock()
    interaction.command.name = "status"
    interaction.guild_id = 987654321
    interaction.user.id = 222222  # Admin user
    
    # Mock response methods
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    
    # Call the handler
    await discord_client._handle_status(interaction)
    
    # Verify interactions
    interaction.response.defer.assert_called_once()
    mock_product_manager.get_dashboard_data.assert_called_once_with(987654321)
    interaction.followup.send.assert_called_once()


@pytest.mark.asyncio
async def test_handle_admin_command_permission_error(discord_client):
    """Test handling admin command with permission error."""
    # Create mock interaction
    interaction = AsyncMock()
    interaction.command.name = "add"
    interaction.guild_id = 987654321
    interaction.user.id = 333333  # Non-admin user
    
    # Mock validate_permissions to return False
    with patch.object(discord_client, 'validate_permissions', AsyncMock(return_value=False)):
        # Mock _validate_admin_command to raise CommandError
        with patch.object(discord_client, '_validate_admin_command', 
                         AsyncMock(side_effect=CommandError("Permission denied"))):
            
            # Call handle_admin_command
            await discord_client.handle_admin_command(interaction)
            
            # Verify error response
            interaction.response.send_message.assert_called_once()
            assert "Error:" in interaction.response.send_message.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_discord_error(discord_client):
    """Test handling Discord API errors."""
    # Create mock interaction
    interaction = AsyncMock()
    
    # Test Forbidden error
    forbidden_error = discord.errors.Forbidden(MagicMock(), "Missing permissions")
    await discord_client._handle_discord_error(interaction, forbidden_error)
    assert "permission" in interaction.response.send_message.call_args[0][0].lower()
    
    # Test NotFound error
    not_found_error = discord.errors.NotFound(MagicMock(), "Resource not found")
    await discord_client._handle_discord_error(interaction, not_found_error)
    assert "not found" in interaction.response.send_message.call_args[0][0].lower()
    
    # Test rate limit error
    rate_limit_error = discord.errors.HTTPException(MagicMock(), "Too many requests")
    rate_limit_error.status = 429
    await discord_client._handle_discord_error(interaction, rate_limit_error)
    assert "rate limit" in interaction.response.send_message.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_send_notification(discord_client):
    """Test sending notifications."""
    # Create mock embed
    embed = discord.Embed(title="Test Notification")
    
    # Test successful notification
    result = await discord_client.send_notification(123456789, embed)
    assert result is True
    
    # Test channel not found
    discord_client.get_channel = MagicMock(return_value=None)
    result = await discord_client.send_notification(999999, embed)
    assert result is False
    
    # Test Discord API error
    discord_client.get_channel = MagicMock(side_effect=discord.errors.HTTPException(MagicMock(), "API Error"))
    result = await discord_client.send_notification(123456789, embed)
    assert result is False