"""
Tests for advanced notification features.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
import discord
from discord import Embed, Color

from src.services.notification_service import NotificationService
from src.models.product_data import (
    ProductData, StockChange, PriceChange, Notification,
    NotificationStyle, NotificationDeliveryStatus, StockStatus
)
from src.config.config_manager import ConfigManager


@pytest.fixture
def config_manager():
    """Create a mock config manager."""
    config = ConfigManager()
    
    # Set notification configuration
    config.set('notifications.colors.in_stock', 0x00ff00)  # Green
    config.set('notifications.colors.out_of_stock', 0xff0000)  # Red
    config.set('notifications.colors.pre_order', 0xffaa00)  # Orange
    config.set('notifications.colors.unknown', 0x808080)  # Gray
    config.set('notifications.max_retries', 3)
    config.set('notifications.retry_delay', 0.1)  # Fast for testing
    config.set('notifications.batch_size', 5)
    config.set('notifications.rate_limit_delay', 0.1)  # Fast for testing
    config.set('notifications.max_queue_size', 100)
    config.set('notifications.cooldown.enabled', True)
    config.set('notifications.cooldown.period', 60)  # 1 minute for testing
    config.set('notifications.cooldown.per_product', True)
    config.set('notifications.batch_window', 1)  # 1 second for testing
    config.set('notifications.price_change_threshold', 5.0)
    
    return config


@pytest.fixture
def discord_client():
    """Create a mock Discord client."""
    client = MagicMock()
    channel = AsyncMock()
    client.get_channel.return_value = channel
    return client


@pytest.fixture
def notification_service(config_manager, discord_client):
    """Create a notification service with mocks."""
    service = NotificationService(config_manager, discord_client)
    service.stock_change_repo = MagicMock()
    return service


@pytest.fixture
def product_data():
    """Create a sample product data object."""
    return ProductData(
        title="Pokemon Scarlet",
        price="€59.99",
        original_price="€59.99",
        image_url="https://example.com/image.jpg",
        product_url="https://example.com/product",
        uncached_url="https://example.com/product?_=123456",
        stock_status=StockStatus.IN_STOCK.value,
        stock_level="",
        website="bol.com",
        delivery_info="Delivery tomorrow",
        sold_by_bol=True,
        last_checked=datetime.utcnow(),
        product_id="test-product-1"
    )


@pytest.fixture
def stock_change():
    """Create a sample stock change object."""
    return StockChange(
        product_id="test-product-1",
        previous_status=StockStatus.OUT_OF_STOCK.value,
        current_status=StockStatus.IN_STOCK.value,
        timestamp=datetime.utcnow(),
        price_change=None,
        notification_sent=False
    )


@pytest.fixture
def price_change():
    """Create a sample price change object."""
    return PriceChange(
        previous_price="€69.99",
        current_price="€59.99",
        change_amount="€-10.00",
        change_percentage=-14.29
    )


@pytest.mark.asyncio
async def test_create_styled_notification(notification_service, product_data, stock_change):
    """Test creating a styled notification."""
    # Test with default style
    embed = await notification_service.create_styled_notification(product_data, stock_change)
    assert embed.title.startswith("🟢")
    assert "Status Changed" in embed.description
    assert embed.color.value == 0x00ff00  # Green for in-stock
    
    # Test with custom style
    custom_style = NotificationStyle(
        embed_color=0x3498db,  # Blue
        use_thumbnail=False,
        use_footer=False,
        compact_mode=True,
        emoji_style="minimal"
    )
    
    embed = await notification_service.create_styled_notification(product_data, stock_change, custom_style)
    assert "🟢" not in embed.title  # No emoji in compact mode
    assert embed.color.value == 0x3498db  # Custom blue color
    assert len(embed.fields) == 2  # Compact mode has fewer fields
    # Discord's Embed doesn't actually set thumbnail to None when not used
    # It creates an empty EmbedProxy object, so we check if it has a url
    assert not hasattr(embed.thumbnail, 'url') or not embed.thumbnail.url
    # Discord's Embed doesn't actually set footer to None when not used
    # It creates an empty EmbedProxy object, so we check if it has a text
    assert not hasattr(embed.footer, 'text') or not embed.footer.text


@pytest.mark.asyncio
async def test_create_price_change_notification(notification_service, product_data, price_change):
    """Test creating a price change notification."""
    notification = await notification_service.create_price_change_notification(
        product_data, price_change, channel_id=123456
    )
    
    assert notification.product_id == product_data.product_id
    assert notification.channel_id == 123456
    assert notification.priority == 2  # Medium priority for price changes
    
    # Check embed data
    embed = Embed.from_dict(notification.embed_data)
    assert "Price changed" in embed.description
    assert "€69.99 → €59.99" in embed.description
    assert "14.3%" in embed.description  # Percentage formatting


@pytest.mark.asyncio
async def test_schedule_notification(notification_service, product_data, stock_change):
    """Test scheduling a notification for future delivery."""
    # Create a notification
    embed = await notification_service.create_stock_notification(product_data, stock_change)
    notification = Notification(
        product_id=product_data.product_id,
        channel_id=123456,
        embed_data=embed.to_dict(),
        role_mentions=["<@&123>"],
        timestamp=datetime.utcnow()
    )
    
    # Schedule it for 2 seconds in the future
    notification_id = await notification_service.schedule_notification(notification, 2)
    
    # Verify it's in the scheduled notifications
    assert notification_id in notification_service.scheduled_notifications
    assert notification_service.scheduled_notifications[notification_id].scheduled_time > datetime.utcnow()
    
    # Wait for scheduler to process it
    await asyncio.sleep(3)
    
    # Verify it was processed
    assert notification_id not in notification_service.scheduled_notifications


@pytest.mark.asyncio
async def test_notification_batching(notification_service, product_data, stock_change):
    """Test notification batching."""
    # Create a batch
    batch_id = await notification_service.create_notification_batch(channel_id=123456, batch_window=1)
    
    # Create notifications
    notifications = []
    for i in range(3):
        embed = await notification_service.create_stock_notification(product_data, stock_change)
        notification = Notification(
            product_id=f"{product_data.product_id}-{i}",
            channel_id=123456,
            embed_data=embed.to_dict(),
            role_mentions=[],
            timestamp=datetime.utcnow()
        )
        notifications.append(notification)
        
        # Add to batch
        result = await notification_service.add_to_batch(batch_id, notification)
        assert result is True
    
    # Wait for batch processing
    await asyncio.sleep(2)
    
    # Verify batch was processed
    assert batch_id not in notification_service.batch_queue
    
    # Verify Discord send was called once with multiple embeds
    channel = notification_service.discord_client.get_channel.return_value
    assert channel.send.called
    call_args = channel.send.call_args
    assert len(call_args[1]['embeds']) == 3


@pytest.mark.asyncio
async def test_notification_delivery_status(notification_service, product_data, stock_change):
    """Test notification delivery status tracking."""
    # Create a notification
    embed = await notification_service.create_stock_notification(product_data, stock_change)
    notification = Notification(
        product_id=product_data.product_id,
        channel_id=123456,
        embed_data=embed.to_dict(),
        role_mentions=[],
        timestamp=datetime.utcnow()
    )
    
    # Update delivery status
    notification_service._update_delivery_status(notification, True)
    
    # Verify status was updated
    assert notification.delivery_status.delivered is True
    assert notification.delivery_status.delivered_at is not None
    assert notification.delivery_status.delivery_attempts == 1
    
    # Verify it's in the tracking dict
    assert notification.notification_id in notification_service.delivery_statuses
    
    # Verify it's in the history
    assert product_data.product_id in notification_service.notification_history
    assert notification.notification_id in notification_service.notification_history[product_data.product_id]


@pytest.mark.asyncio
async def test_notification_cooldown(notification_service, product_data, stock_change):
    """Test notification cooldown functionality."""
    # First notification should be allowed
    assert await notification_service.should_send_notification(product_data.product_id) is True
    
    # Second notification for same product should be blocked by cooldown
    assert await notification_service.should_send_notification(product_data.product_id) is False
    
    # Different product should be allowed
    assert await notification_service.should_send_notification("different-product") is True
    
    # Disable cooldown and try again
    notification_service.cooldown_enabled = False
    assert await notification_service.should_send_notification(product_data.product_id) is True


@pytest.mark.asyncio
async def test_price_history_display(notification_service, product_data, stock_change):
    """Test price history display in notifications."""
    # Mock price history data
    price_history = [
        (datetime.utcnow() - timedelta(days=5), "€69.99", "€59.99", -14.29),
        (datetime.utcnow() - timedelta(days=10), "€79.99", "€69.99", -12.5),
        (datetime.utcnow() - timedelta(days=15), "€89.99", "€79.99", -11.1)
    ]
    
    # Setup mock for price history
    notification_service.stock_change_repo.get_changes_by_product.return_value = [
        StockChange(
            product_id=product_data.product_id,
            previous_status=StockStatus.IN_STOCK.value,
            current_status=StockStatus.IN_STOCK.value,
            timestamp=timestamp,
            price_change=PriceChange(
                previous_price=prev_price,
                current_price=curr_price,
                change_amount=f"€{float(curr_price[1:]) - float(prev_price[1:]):.2f}",
                change_percentage=percentage
            )
        )
        for timestamp, prev_price, curr_price, percentage in price_history
    ]
    
    # Create a price change
    price_change = PriceChange(
        previous_price="€59.99",
        current_price="€49.99",
        change_amount="€-10.00",
        change_percentage=-16.67
    )
    
    # Add price change to stock change
    stock_change.price_change = price_change
    
    # Create notification with price history enabled
    style = NotificationStyle(show_price_history=True)
    embed = await notification_service.create_styled_notification(product_data, stock_change, style)
    
    # Verify price history is included
    assert "Price History" in embed.description
    for _, prev_price, curr_price, _ in price_history:
        assert f"{prev_price} → {curr_price}" in embed.description