"""
Tests for price tracking service.
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.services.price_tracking import PriceTrackingService
from src.models.product_data import ProductData, PriceChange, StockStatus


@pytest.fixture
def price_tracking_service():
    """Create a price tracking service with mocked repository."""
    service = PriceTrackingService()
    service.notification_repo = MagicMock()
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


def test_extract_price_value(price_tracking_service):
    """Test extracting numeric price values from price strings."""
    assert price_tracking_service._extract_price_value("€59.99") == 59.99
    assert price_tracking_service._extract_price_value("€ 59,99") == 59.99
    assert price_tracking_service._extract_price_value("59.99") == 59.99
    assert price_tracking_service._extract_price_value("€59") == 59.0
    assert price_tracking_service._extract_price_value("Invalid") == 0.0


def test_detect_price_change_first_check(price_tracking_service, product_data):
    """Test price change detection on first check."""
    # First check should record price but not detect change
    price_change = price_tracking_service.detect_price_change(product_data, None)
    
    assert price_change is None
    price_tracking_service.notification_repo.add_price_history.assert_called_once_with(
        product_data.product_id, product_data.price
    )


def test_detect_price_change_no_change(price_tracking_service, product_data):
    """Test price change detection with no change."""
    # Create previous product with same price
    previous_product = ProductData(
        title="Pokemon Scarlet",
        price="€59.99",  # Same price
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
    
    # No price change should be detected
    price_change = price_tracking_service.detect_price_change(product_data, previous_product)
    
    assert price_change is None
    # Price should not be recorded again if unchanged
    assert not price_tracking_service.notification_repo.add_price_history.called


def test_detect_price_change_price_decrease(price_tracking_service, product_data):
    """Test price change detection with price decrease."""
    # Create previous product with higher price
    previous_product = ProductData(
        title="Pokemon Scarlet",
        price="€69.99",  # Higher price
        original_price="€69.99",
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
    
    # Price decrease should be detected
    price_change = price_tracking_service.detect_price_change(product_data, previous_product)
    
    assert price_change is not None
    assert price_change.previous_price == "€69.99"
    assert price_change.current_price == "€59.99"
    assert price_change.change_amount == "€-10.00"
    assert price_change.change_percentage == pytest.approx(-14.29, 0.01)
    
    # New price should be recorded
    price_tracking_service.notification_repo.add_price_history.assert_called_once_with(
        product_data.product_id, product_data.price
    )


def test_detect_price_change_price_increase(price_tracking_service, product_data):
    """Test price change detection with price increase."""
    # Create previous product with lower price
    previous_product = ProductData(
        title="Pokemon Scarlet",
        price="€49.99",  # Lower price
        original_price="€49.99",
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
    
    # Price increase should be detected
    price_change = price_tracking_service.detect_price_change(product_data, previous_product)
    
    assert price_change is not None
    assert price_change.previous_price == "€49.99"
    assert price_change.current_price == "€59.99"
    assert price_change.change_amount == "€10.00"
    assert price_change.change_percentage == pytest.approx(20.0, 0.01)
    
    # New price should be recorded
    price_tracking_service.notification_repo.add_price_history.assert_called_once_with(
        product_data.product_id, product_data.price
    )


def test_is_significant_price_change(price_tracking_service):
    """Test significant price change detection."""
    # Create price changes with different percentages
    small_change = PriceChange(
        previous_price="€59.99",
        current_price="€58.99",
        change_amount="€-1.00",
        change_percentage=-1.67
    )
    
    medium_change = PriceChange(
        previous_price="€59.99",
        current_price="€54.99",
        change_amount="€-5.00",
        change_percentage=-8.33
    )
    
    large_change = PriceChange(
        previous_price="€59.99",
        current_price="€39.99",
        change_amount="€-20.00",
        change_percentage=-33.33
    )
    
    # Test with default threshold (5%)
    assert not price_tracking_service.is_significant_price_change(small_change)
    assert price_tracking_service.is_significant_price_change(medium_change)
    assert price_tracking_service.is_significant_price_change(large_change)
    
    # Test with custom threshold (10%)
    assert not price_tracking_service.is_significant_price_change(small_change, 10.0)
    assert not price_tracking_service.is_significant_price_change(medium_change, 10.0)
    assert price_tracking_service.is_significant_price_change(large_change, 10.0)


@pytest.mark.asyncio
async def test_get_price_history(price_tracking_service):
    """Test getting price history."""
    # Mock repository response
    now = datetime.utcnow()
    mock_history = [
        ("€59.99", now),
        ("€69.99", now)
    ]
    price_tracking_service.notification_repo.get_price_history.return_value = mock_history
    
    # Get price history
    history = await price_tracking_service.get_price_history("test-product-1")
    
    assert history == mock_history
    price_tracking_service.notification_repo.get_price_history.assert_called_once_with(
        "test-product-1", 10
    )