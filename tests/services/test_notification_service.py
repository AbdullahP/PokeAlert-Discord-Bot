"""
Tests for the notification service.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
import discord
from discord import Embed

from src.services.notification_service import NotificationService
from src.models.product_data import (
    ProductData, StockChange, Notification, PriceChange, StockStatus
)
from src.config.config_manager import ConfigManager


@pytest.fixture
def mock_config_manager():
    """Create a mock config manager."""
    config = MagicMock(spec=ConfigManager)
    
    # Set up notification config values
    config.get.side_effect = lambda key, default=None: {
        'notifications.colors.in_stock': 0x00ff00,  # Green
        'notifications.colors.out_of_stock': 0xff0000,  # Red
        'notifications.colors.pre_order': 0xffaa00,  # Orange
        'notifications.colors.unknown': 0x808080,  # Gray
        'notifications.embed_color': 0x00ff00,
        'notifications.max_retries': 3,
        'notifications.retry_delay': 0.1,  # Short delay for tests
        'notifications.batch_size': 2,
        'notifications.rate_limit_delay': 0.1,  # Short delay for tests
        'notifications.max_queue_size': 100
    }.get(key, default)
    
    return config


@pytest.fixture
def mock_discord_client():
    """Create a mock Discord client."""
    client = MagicMock()
    client.get_channel = MagicMock(return_value=AsyncMock())
    return client


@pytest.fixture
def notification_service(mock_config_manager, mock_discord_client):
    """Create a notification service instance with mocks."""
    return NotificationService(mock_config_manager, mock_discord_client)


@pytest.fixture
def sample_product_data():
    """Create sample product data for testing."""
    return ProductData(
        title="Pokemon Scarlet Nintendo Switch",
        price="€59.99",
        original_price="€69.99",
        image_url="https://example.com/image.jpg",
        product_url="https://bol.com/product/123",
        uncached_url="https://bol.com/product/123?timestamp=123456",
        stock_status=StockStatus.IN_STOCK.value,
        stock_level="10+ available",
        website="bol.com",
        delivery_info="Delivery tomorrow",
        sold_by_bol=True,
        last_checked=datetime.utcnow(),
        product_id="prod-123"
    )


@pytest.fixture
def sample_stock_change():
    """Create sample stock change for testing."""
    return StockChange(
        product_id="prod-123",
        previous_status=StockStatus.OUT_OF_STOCK.value,
        current_status=StockStatus.IN_STOCK.value,
        timestamp=datetime.utcnow(),
        price_change=PriceChange(
            previous_price="€69.99",
            current_price="€59.99",
            change_amount="-€10.00",
            change_percentage=-14.3
        ),
        notification_sent=False
    )


@pytest.fixture
def sample_notification(sample_product_data, sample_stock_change):
    """Create sample notification for testing."""
    embed = Embed(
        title="Test Notification",
        description="Test Description",
        color=0x00ff00
    )
    
    return Notification(
        product_id=sample_product_data.product_id,
        channel_id=123456789,
        embed_data=embed.to_dict(),
        role_mentions=["<@&123456>"],
        timestamp=datetime.utcnow(),
        retry_count=0,
        max_retries=3
    )


@pytest.mark.asyncio
async def test_create_stock_notification(notification_service, sample_product_data, sample_stock_change):
    """Test creating a stock notification embed."""
    embed = await notification_service.create_stock_notification(sample_product_data, sample_stock_change)
    
    # Verify embed structure
    assert embed.title.startswith("🟢")
    assert sample_product_data.title in embed.title
    assert "Status Changed" in embed.description
    assert sample_stock_change.previous_status in embed.description
    assert sample_stock_change.current_status in embed.description
    assert "Click here to purchase" in embed.description
    assert embed.url == sample_product_data.uncached_url
    
    # Verify fields
    fields = {field.name: field.value for field in embed.fields}
    assert "Price" in fields
    assert sample_product_data.price in fields["Price"]
    assert "Status" in fields
    assert sample_product_data.stock_status in fields["Status"]
    assert "Delivery" in fields
    assert sample_product_data.delivery_info in fields["Delivery"]
    
    # Verify image
    assert embed.thumbnail.url == sample_product_data.image_url
    
    # Verify footer
    assert "Detected at" in embed.footer.text


@pytest.mark.asyncio
async def test_create_stock_notification_with_price_change(notification_service, sample_product_data, sample_stock_change):
    """Test creating a stock notification embed with price change."""
    embed = await notification_service.create_stock_notification(sample_product_data, sample_stock_change)
    
    # Verify price change information is included
    assert "Price changed" in embed.description
    assert sample_stock_change.price_change.previous_price in embed.description
    assert sample_stock_change.price_change.current_price in embed.description
    assert "14.3%" in embed.description  # Percentage change


@pytest.mark.asyncio
async def test_create_stock_notification_out_of_stock(notification_service, sample_product_data, sample_stock_change):
    """Test creating an out-of-stock notification embed."""
    # Modify product to be out of stock
    sample_product_data.stock_status = StockStatus.OUT_OF_STOCK.value
    sample_stock_change.current_status = StockStatus.OUT_OF_STOCK.value
    sample_stock_change.previous_status = StockStatus.IN_STOCK.value
    
    embed = await notification_service.create_stock_notification(sample_product_data, sample_stock_change)
    
    # Verify embed structure for out-of-stock
    assert embed.title.startswith("🔴")
    assert "Click here to purchase" not in embed.description
    
    # Verify color is red for out-of-stock
    assert embed.color.value == 0xff0000


@pytest.mark.asyncio
async def test_send_notification_success(notification_service, mock_discord_client):
    """Test sending a notification successfully."""
    channel_mock = AsyncMock()
    mock_discord_client.get_channel.return_value = channel_mock
    
    embed = Embed(title="Test Notification", description="Test Description")
    mentions = ["<@&123456>"]
    
    result = await notification_service.send_notification(123456789, embed, mentions)
    
    # Verify the notification was sent
    assert result is True
    mock_discord_client.get_channel.assert_called_once_with(123456789)
    channel_mock.send.assert_called_once()
    
    # Verify mentions were included
    args, kwargs = channel_mock.send.call_args
    assert kwargs["content"] == "<@&123456>"
    assert kwargs["embed"] == embed


@pytest.mark.asyncio
async def test_send_notification_channel_not_found(notification_service, mock_discord_client):
    """Test sending a notification when channel is not found."""
    mock_discord_client.get_channel.return_value = None
    
    embed = Embed(title="Test Notification", description="Test Description")
    
    result = await notification_service.send_notification(123456789, embed)
    
    # Verify the notification failed
    assert result is False
    mock_discord_client.get_channel.assert_called_once_with(123456789)


@pytest.mark.asyncio
async def test_send_notification_discord_error(notification_service, mock_discord_client):
    """Test sending a notification with Discord API error."""
    channel_mock = AsyncMock()
    channel_mock.send.side_effect = discord.errors.HTTPException(
        response=MagicMock(), message="Rate limited"
    )
    mock_discord_client.get_channel.return_value = channel_mock
    
    embed = Embed(title="Test Notification", description="Test Description")
    
    result = await notification_service.send_notification(123456789, embed)
    
    # Verify the notification failed
    assert result is False
    mock_discord_client.get_channel.assert_called_once_with(123456789)
    channel_mock.send.assert_called_once()


@pytest.mark.asyncio
async def test_queue_notification(notification_service, sample_notification):
    """Test queuing a notification."""
    # Mock the process_notification_queue method
    notification_service.process_notification_queue = AsyncMock()
    
    await notification_service.queue_notification(sample_notification)
    
    # Verify notification was added to queue
    assert notification_service.notification_queue.qsize() == 1
    
    # Verify processing task was started
    notification_service.process_notification_queue.assert_called_once()


@pytest.mark.asyncio
async def test_process_notification_queue(notification_service, sample_notification):
    """Test processing the notification queue."""
    # Add a notification to the queue
    await notification_service.notification_queue.put(sample_notification)
    
    # Mock send_notification to succeed
    notification_service.send_notification = AsyncMock(return_value=True)
    
    # Process the queue
    await notification_service.process_notification_queue()
    
    # Verify queue is empty after processing
    assert notification_service.notification_queue.empty()
    
    # Verify send_notification was called
    notification_service.send_notification.assert_called_once()


@pytest.mark.asyncio
async def test_process_notification_queue_with_retry(notification_service, sample_notification):
    """Test processing the notification queue with retry on failure."""
    # Add a notification to the queue
    await notification_service.notification_queue.put(sample_notification)
    
    # Mock send_notification to fail first, then succeed
    notification_service.send_notification = AsyncMock()
    notification_service.send_notification.side_effect = [False, True]
    
    # Process the queue
    await notification_service.process_notification_queue()
    
    # Verify queue is empty after processing
    assert notification_service.notification_queue.empty()
    
    # Verify send_notification was called twice (original + retry)
    assert notification_service.send_notification.call_count == 2


@pytest.mark.asyncio
async def test_create_and_queue_notification(notification_service, sample_product_data, sample_stock_change):
    """Test creating and queuing a notification in one step."""
    # Mock the methods
    notification_service.create_stock_notification = AsyncMock(return_value=Embed())
    notification_service.queue_notification = AsyncMock()
    
    channel_id = 123456789
    role_mentions = ["<@&123456>"]
    
    await notification_service.create_and_queue_notification(
        sample_product_data, sample_stock_change, channel_id, role_mentions
    )
    
    # Verify methods were called
    notification_service.create_stock_notification.assert_called_once_with(
        sample_product_data, sample_stock_change
    )
    notification_service.queue_notification.assert_called_once()
    
    # Verify notification object was created correctly
    notification = notification_service.queue_notification.call_args[0][0]
    assert notification.product_id == sample_product_data.product_id
    assert notification.channel_id == channel_id
    assert notification.role_mentions == role_mentions


@pytest.mark.asyncio
async def test_get_queue_status(notification_service, sample_notification):
    """Test getting queue status."""
    # Add notifications to the queue
    await notification_service.notification_queue.put(sample_notification)
    await notification_service.notification_queue.put(sample_notification)
    
    # Get queue status
    status = await notification_service.get_queue_status()
    
    # Verify status information
    assert status["queue_size"] == 2
    assert status["max_queue_size"] == notification_service.max_queue_size
    assert "is_processing" in status


@pytest.mark.asyncio
async def test_mention_formatting(notification_service, mock_discord_client):
    """Test formatting of role mentions."""
    channel_mock = AsyncMock()
    mock_discord_client.get_channel.return_value = channel_mock
    
    embed = Embed(title="Test Notification", description="Test Description")
    
    # Test different mention formats
    mentions = ["<@&123456>", "456789", "&987654"]
    
    await notification_service.send_notification(123456789, embed, mentions)
    
    # Verify mentions were formatted correctly
    args, kwargs = channel_mock.send.call_args
    assert "<@&123456>" in kwargs["content"]
    assert "<@&456789>" in kwargs["content"]
    assert "<@&987654>" in kwargs["content"]