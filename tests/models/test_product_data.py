"""
Unit tests for product data models.
"""
import unittest
import json
from datetime import datetime
from src.models.product_data import (
    ProductData, ProductConfig, StockChange, PriceChange,
    StockStatus, URLType, MonitoringStatus, DashboardData, Notification
)


class TestProductData(unittest.TestCase):
    """Test cases for ProductData class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.valid_product_data = ProductData(
            title="Pokemon Scarlet",
            price="€59.99",
            original_price="€69.99",
            image_url="https://example.com/image.jpg",
            product_url="https://bol.com/product/123",
            uncached_url="https://bol.com/product/123?t=12345",
            stock_status=StockStatus.IN_STOCK.value,
            stock_level="10+ available",
            website="bol.com",
            delivery_info="Delivery within 24 hours",
            sold_by_bol=True,
            last_checked=datetime.utcnow(),
            product_id="test-product-123"
        )
    
    def test_product_data_validation_valid(self):
        """Test ProductData validation with valid data."""
        self.assertTrue(self.valid_product_data.validate())
    
    def test_product_data_validation_invalid_missing_title(self):
        """Test ProductData validation with missing title."""
        invalid_data = ProductData(
            title="",
            price="€59.99",
            original_price="€69.99",
            image_url="https://example.com/image.jpg",
            product_url="https://bol.com/product/123",
            uncached_url="https://bol.com/product/123?t=12345",
            stock_status=StockStatus.IN_STOCK.value,
            stock_level="10+ available",
            website="bol.com",
            delivery_info="Delivery within 24 hours",
            sold_by_bol=True,
            last_checked=datetime.utcnow(),
            product_id="test-product-123"
        )
        self.assertFalse(invalid_data.validate())
    
    def test_product_data_validation_invalid_stock_status(self):
        """Test ProductData validation with invalid stock status."""
        invalid_data = ProductData(
            title="Pokemon Scarlet",
            price="€59.99",
            original_price="€69.99",
            image_url="https://example.com/image.jpg",
            product_url="https://bol.com/product/123",
            uncached_url="https://bol.com/product/123?t=12345",
            stock_status="Invalid Status",
            stock_level="10+ available",
            website="bol.com",
            delivery_info="Delivery within 24 hours",
            sold_by_bol=True,
            last_checked=datetime.utcnow(),
            product_id="test-product-123"
        )
        self.assertFalse(invalid_data.validate())
    
    def test_product_data_to_dict(self):
        """Test conversion of ProductData to dictionary."""
        data_dict = self.valid_product_data.to_dict()
        self.assertEqual(data_dict["title"], "Pokemon Scarlet")
        self.assertEqual(data_dict["price"], "€59.99")
        self.assertEqual(data_dict["stock_status"], StockStatus.IN_STOCK.value)
        self.assertIsInstance(data_dict["last_checked"], str)
    
    def test_product_data_from_dict(self):
        """Test creation of ProductData from dictionary."""
        data_dict = self.valid_product_data.to_dict()
        product_data = ProductData.from_dict(data_dict)
        self.assertEqual(product_data.title, "Pokemon Scarlet")
        self.assertEqual(product_data.price, "€59.99")
        self.assertEqual(product_data.stock_status, StockStatus.IN_STOCK.value)
        self.assertIsInstance(product_data.last_checked, datetime)


class TestProductConfig(unittest.TestCase):
    """Test cases for ProductConfig class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.valid_product_config = ProductConfig(
            product_id="test-product-123",
            url="https://bol.com/product/123",
            url_type=URLType.PRODUCT.value,
            channel_id=123456789,
            guild_id=987654321,
            monitoring_interval=60,
            role_mentions=["<@&123456>", "<@&789012>"],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    
    def test_product_config_validation_valid(self):
        """Test ProductConfig validation with valid data."""
        self.assertTrue(self.valid_product_config.validate())
    
    def test_product_config_validation_invalid_url_type(self):
        """Test ProductConfig validation with invalid URL type."""
        invalid_config = ProductConfig(
            product_id="test-product-123",
            url="https://bol.com/product/123",
            url_type="invalid_type",
            channel_id=123456789,
            guild_id=987654321,
            monitoring_interval=60,
            role_mentions=["<@&123456>", "<@&789012>"],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.assertFalse(invalid_config.validate())
    
    def test_product_config_validation_invalid_interval(self):
        """Test ProductConfig validation with invalid monitoring interval."""
        invalid_config = ProductConfig(
            product_id="test-product-123",
            url="https://bol.com/product/123",
            url_type=URLType.PRODUCT.value,
            channel_id=123456789,
            guild_id=987654321,
            monitoring_interval=20,  # Less than minimum 30
            role_mentions=["<@&123456>", "<@&789012>"],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.assertFalse(invalid_config.validate())
    
    def test_product_config_to_dict(self):
        """Test conversion of ProductConfig to dictionary."""
        config_dict = self.valid_product_config.to_dict()
        self.assertEqual(config_dict["product_id"], "test-product-123")
        self.assertEqual(config_dict["url"], "https://bol.com/product/123")
        self.assertEqual(config_dict["url_type"], URLType.PRODUCT.value)
        self.assertIsInstance(config_dict["created_at"], str)
        self.assertIsInstance(config_dict["role_mentions"], str)
        self.assertIn("<@&123456>", config_dict["role_mentions"])
    
    def test_product_config_from_dict(self):
        """Test creation of ProductConfig from dictionary."""
        config_dict = self.valid_product_config.to_dict()
        product_config = ProductConfig.from_dict(config_dict)
        self.assertEqual(product_config.product_id, "test-product-123")
        self.assertEqual(product_config.url, "https://bol.com/product/123")
        self.assertEqual(product_config.url_type, URLType.PRODUCT.value)
        self.assertIsInstance(product_config.created_at, datetime)
        self.assertIsInstance(product_config.role_mentions, list)
        self.assertIn("<@&123456>", product_config.role_mentions)
    
    def test_product_config_create_new(self):
        """Test creation of new ProductConfig with generated ID."""
        new_config = ProductConfig.create_new(
            url="https://bol.com/product/456",
            url_type=URLType.PRODUCT.value,
            channel_id=123456789,
            guild_id=987654321,
            monitoring_interval=120
        )
        self.assertIsNotNone(new_config.product_id)
        self.assertEqual(new_config.url, "https://bol.com/product/456")
        self.assertEqual(new_config.monitoring_interval, 120)
        self.assertTrue(new_config.is_active)
        self.assertIsInstance(new_config.created_at, datetime)
        self.assertIsInstance(new_config.updated_at, datetime)


class TestStockChange(unittest.TestCase):
    """Test cases for StockChange class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.price_change = PriceChange(
            previous_price="€69.99",
            current_price="€59.99",
            change_amount="€10.00",
            change_percentage=14.29
        )
        
        self.valid_stock_change = StockChange(
            product_id="test-product-123",
            previous_status=StockStatus.OUT_OF_STOCK.value,
            current_status=StockStatus.IN_STOCK.value,
            timestamp=datetime.utcnow(),
            price_change=self.price_change,
            notification_sent=False
        )
    
    def test_stock_change_validation_valid(self):
        """Test StockChange validation with valid data."""
        self.assertTrue(self.valid_stock_change.validate())
    
    def test_stock_change_validation_invalid_status(self):
        """Test StockChange validation with invalid status."""
        invalid_change = StockChange(
            product_id="test-product-123",
            previous_status="Invalid Status",
            current_status=StockStatus.IN_STOCK.value,
            timestamp=datetime.utcnow(),
            price_change=None,
            notification_sent=False
        )
        self.assertFalse(invalid_change.validate())
    
    def test_stock_change_to_dict(self):
        """Test conversion of StockChange to dictionary."""
        change_dict = self.valid_stock_change.to_dict()
        self.assertEqual(change_dict["product_id"], "test-product-123")
        self.assertEqual(change_dict["previous_status"], StockStatus.OUT_OF_STOCK.value)
        self.assertEqual(change_dict["current_status"], StockStatus.IN_STOCK.value)
        self.assertIsInstance(change_dict["timestamp"], str)
        self.assertIsInstance(change_dict["price_change"], str)
        self.assertFalse(change_dict["notification_sent"])
    
    def test_stock_change_from_dict(self):
        """Test creation of StockChange from dictionary."""
        change_dict = self.valid_stock_change.to_dict()
        stock_change = StockChange.from_dict(change_dict)
        self.assertEqual(stock_change.product_id, "test-product-123")
        self.assertEqual(stock_change.previous_status, StockStatus.OUT_OF_STOCK.value)
        self.assertEqual(stock_change.current_status, StockStatus.IN_STOCK.value)
        self.assertIsInstance(stock_change.timestamp, datetime)
        self.assertIsInstance(stock_change.price_change, PriceChange)
        self.assertEqual(stock_change.price_change.previous_price, "€69.99")
        self.assertEqual(stock_change.price_change.current_price, "€59.99")
        self.assertFalse(stock_change.notification_sent)


class TestPriceChange(unittest.TestCase):
    """Test cases for PriceChange class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.price_change = PriceChange(
            previous_price="€69.99",
            current_price="€59.99",
            change_amount="€10.00",
            change_percentage=14.29
        )
    
    def test_price_change_to_dict(self):
        """Test conversion of PriceChange to dictionary."""
        change_dict = self.price_change.to_dict()
        self.assertEqual(change_dict["previous_price"], "€69.99")
        self.assertEqual(change_dict["current_price"], "€59.99")
        self.assertEqual(change_dict["change_amount"], "€10.00")
        self.assertEqual(change_dict["change_percentage"], 14.29)
    
    def test_price_change_from_dict(self):
        """Test creation of PriceChange from dictionary."""
        change_dict = self.price_change.to_dict()
        price_change = PriceChange.from_dict(change_dict)
        self.assertEqual(price_change.previous_price, "€69.99")
        self.assertEqual(price_change.current_price, "€59.99")
        self.assertEqual(price_change.change_amount, "€10.00")
        self.assertEqual(price_change.change_percentage, 14.29)


class TestMonitoringStatus(unittest.TestCase):
    """Test cases for MonitoringStatus class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.monitoring_status = MonitoringStatus(
            product_id="test-product-123",
            is_active=True,
            last_check=datetime.utcnow(),
            success_rate=95.5,
            error_count=2,
            last_error="Connection timeout"
        )
    
    def test_monitoring_status_to_dict(self):
        """Test conversion of MonitoringStatus to dictionary."""
        status_dict = self.monitoring_status.to_dict()
        self.assertEqual(status_dict["product_id"], "test-product-123")
        self.assertTrue(status_dict["is_active"])
        self.assertIsInstance(status_dict["last_check"], str)
        self.assertEqual(status_dict["success_rate"], 95.5)
        self.assertEqual(status_dict["error_count"], 2)
        self.assertEqual(status_dict["last_error"], "Connection timeout")
    
    def test_monitoring_status_from_dict(self):
        """Test creation of MonitoringStatus from dictionary."""
        status_dict = self.monitoring_status.to_dict()
        monitoring_status = MonitoringStatus.from_dict(status_dict)
        self.assertEqual(monitoring_status.product_id, "test-product-123")
        self.assertTrue(monitoring_status.is_active)
        self.assertIsInstance(monitoring_status.last_check, datetime)
        self.assertEqual(monitoring_status.success_rate, 95.5)
        self.assertEqual(monitoring_status.error_count, 2)
        self.assertEqual(monitoring_status.last_error, "Connection timeout")


class TestNotification(unittest.TestCase):
    """Test cases for Notification class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.notification = Notification(
            product_id="test-product-123",
            channel_id=123456789,
            embed_data={
                "title": "Pokemon Scarlet",
                "description": "Now in stock!",
                "color": 0x00ff00
            },
            role_mentions=["<@&123456>", "<@&789012>"],
            timestamp=datetime.utcnow(),
            retry_count=0,
            max_retries=3
        )
    
    def test_notification_to_dict(self):
        """Test conversion of Notification to dictionary."""
        notification_dict = self.notification.to_dict()
        self.assertEqual(notification_dict["product_id"], "test-product-123")
        self.assertEqual(notification_dict["channel_id"], 123456789)
        self.assertEqual(notification_dict["embed_data"]["title"], "Pokemon Scarlet")
        self.assertIsInstance(notification_dict["timestamp"], str)
        self.assertEqual(notification_dict["retry_count"], 0)
        self.assertEqual(notification_dict["max_retries"], 3)
    
    def test_notification_from_dict(self):
        """Test creation of Notification from dictionary."""
        notification_dict = self.notification.to_dict()
        notification = Notification.from_dict(notification_dict)
        self.assertEqual(notification.product_id, "test-product-123")
        self.assertEqual(notification.channel_id, 123456789)
        self.assertEqual(notification.embed_data["title"], "Pokemon Scarlet")
        self.assertIsInstance(notification.timestamp, datetime)
        self.assertEqual(notification.retry_count, 0)
        self.assertEqual(notification.max_retries, 3)


if __name__ == "__main__":
    unittest.main()