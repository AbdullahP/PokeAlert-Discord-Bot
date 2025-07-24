"""
Tests for monitoring notification integration.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from src.services.monitoring_notification_integration import MonitoringNotificationIntegration
from src.models.product_data import (
    ProductData, StockChange, PriceChange, NotificationStyle,
    StockStatus, ProductConfig
)


@pytest.fixture
def notification_service():
    """Create a mock notification service."""
    service = AsyncMock()
    service.config_manager = MagicMock()
    service.config_manager.get.return_value = 60  # batch window
    service.batch_queue = {}
    
    # Setup async methods
    service.create_styled_notification = AsyncMock()
    service.create_price_change_notification = AsyncMock()
    service.queue_notification = AsyncMock()
    service.create_notification_batch = AsyncMock()
    service.add_to_batch = AsyncMock()
    service.should_send_notification = AsyncMock(return_value=True)
    
    return service


@pytest.fixture
def integration(notification_service):
    """Create a monitoring notification integration."""
    integration = MonitoringNotificationIntegration(notification_service)
    integration.product_repo = AsyncMock()
    integration.notification_repo = AsyncMock()
    
    # Setup notification_repo methods
    integration.notification_repo.get_product_style = AsyncMock(return_value=None)
    
    return integration


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
def product_config():
    """Create a sample product configuration."""
    return ProductConfig(
        product_id="test-product-1",
        url="https://example.com/product",
        url_type="product",
        channel_id=123456,
        guild_id=789012,
        monitoring_interval=60,
        role_mentions=["<@&123>"],
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
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
async def test_handle_stock_change_status_change(integration, product_data, stock_change, product_config):
    """Test handling stock status change."""
    # Setup mocks
    integration.product_repo.get_product.return_value = product_config
    integration.notification_service.should_send_notification.return_value = True
    
    # Create a mock embed with to_dict method
    mock_embed = MagicMock()
    mock_embed.to_dict.return_value = {"title": "Test Embed"}
    integration.notification_service.create_styled_notification.return_value = mock_embed
    
    # Call method
    await integration.handle_stock_change(product_data, stock_change)
    
    # Verify notification was created and queued
    assert integration.notification_service.create_styled_notification.called
    assert integration.notification_service.queue_notification.called
    integration.notification_service.queue_notification.assert_called_once()
    
    # Verify notification has high priority
    notification = integration.notification_service.queue_notification.call_args[0][0]
    assert notification.priority == 1  # High priority for stock changes


@pytest.mark.asyncio
async def test_handle_stock_change_price_change(integration, product_data, stock_change, product_config, price_change):
    """Test handling price change."""
    # Setup stock change with price change but no status change
    stock_change.previous_status = StockStatus.IN_STOCK.value
    stock_change.current_status = StockStatus.IN_STOCK.value
    stock_change.price_change = price_change
    
    # Setup mocks
    integration.product_repo.get_product.return_value = product_config
    integration.notification_service.should_send_notification.return_value = True
    
    # Create a mock notification
    mock_notification = MagicMock()
    integration.notification_service.create_price_change_notification.return_value = mock_notification
    integration.notification_service.create_notification_batch.return_value = "test-batch-1"
    
    # Call method
    await integration.handle_stock_change(product_data, stock_change)
    
    # Verify price change notification was created and added to batch
    assert integration.notification_service.create_price_change_notification.called
    assert integration.notification_service.create_notification_batch.called
    assert integration.notification_service.add_to_batch.called
    
    # Verify notification was added to batch
    integration.notification_service.create_notification_batch.assert_called_once()
    integration.notification_service.add_to_batch.assert_called_once()


@pytest.mark.asyncio
async def test_handle_stock_change_cooldown(integration, product_data, stock_change, product_config):
    """Test notification cooldown."""
    # Setup mocks
    integration.product_repo.get_product.return_value = product_config
    integration.notification_service.should_send_notification.return_value = False
    
    # Call method
    await integration.handle_stock_change(product_data, stock_change)
    
    # Verify no notification was created
    integration.notification_service.create_styled_notification.assert_not_called()
    integration.notification_service.queue_notification.assert_not_called()


@pytest.mark.asyncio
async def test_get_notification_style(integration, product_data):
    """Test getting notification style for product."""
    # Setup mock style
    style = NotificationStyle(
        embed_color=0x3498db,
        use_thumbnail=True,
        use_footer=True,
        compact_mode=False,
        show_price_history=True,
        emoji_style="default"
    )
    
    # Set up the return value as a tuple
    mock_return = ("Test Style", style)
    integration.notification_repo.get_product_style.return_value = mock_return
    
    # Call method
    result = await integration._get_notification_style(product_data.product_id)
    
    # Verify style was returned
    assert result == style
    
    # Verify style was cached
    assert product_data.product_id in integration.style_cache
    assert integration.style_cache[product_data.product_id] == style
    
    # Reset mock and call again
    integration.notification_repo.get_product_style.reset_mock()
    
    # Call method again
    result2 = await integration._get_notification_style(product_data.product_id)
    
    # Verify style was returned from cache
    assert result2 == style
    integration.notification_repo.get_product_style.assert_not_called()


@pytest.mark.asyncio
async def test_register_with_monitoring_engine(integration):
    """Test registering with monitoring engine."""
    # Create mock monitoring engine
    monitoring_engine = MagicMock()
    monitoring_engine.register_stock_change_callback = MagicMock()
    
    # Register with monitoring engine
    await integration.register_with_monitoring_engine(monitoring_engine)
    
    # Verify callback was registered
    monitoring_engine.register_stock_change_callback.assert_called_once_with(
        integration.handle_stock_change
    )