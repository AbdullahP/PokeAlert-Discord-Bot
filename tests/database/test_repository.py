"""
Unit tests for database repository operations.
"""
import unittest
import os
import tempfile
from datetime import datetime
from pathlib import Path

from src.database.connection import DatabaseConnection
from src.database.repository import (
    ProductRepository, ProductStatusRepository, 
    StockChangeRepository, MetricsRepository
)
from src.models.product_data import (
    ProductData, ProductConfig, StockChange, PriceChange,
    StockStatus, URLType
)


class BaseRepositoryTest(unittest.TestCase):
    """Base class for repository tests."""
    
    def setUp(self):
        """Set up test database."""
        # Create a temporary database file
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_db.sqlite"
        
        # Initialize database connection
        self.db = DatabaseConnection(str(self.db_path))
        self.db.create_tables()
        
        # Initialize repositories
        self.product_repo = ProductRepository()
        self.product_repo.db = self.db
        
        self.status_repo = ProductStatusRepository()
        self.status_repo.db = self.db
        
        self.stock_change_repo = StockChangeRepository()
        self.stock_change_repo.db = self.db
        
        self.metrics_repo = MetricsRepository()
        self.metrics_repo.db = self.db
        
        # Create test data
        self.product_config = ProductConfig(
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
        
        self.product_data = ProductData(
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
        
        self.price_change = PriceChange(
            previous_price="€69.99",
            current_price="€59.99",
            change_amount="€10.00",
            change_percentage=14.29
        )
        
        self.stock_change = StockChange(
            product_id="test-product-123",
            previous_status=StockStatus.OUT_OF_STOCK.value,
            current_status=StockStatus.IN_STOCK.value,
            timestamp=datetime.utcnow(),
            price_change=self.price_change,
            notification_sent=False
        )
    
    def tearDown(self):
        """Clean up after tests."""
        self.db.close()
        self.temp_dir.cleanup()


class TestProductRepository(BaseRepositoryTest):
    """Test cases for ProductRepository."""
    
    def test_add_product(self):
        """Test adding a product to the database."""
        result = self.product_repo.add_product(self.product_config)
        self.assertTrue(result)
        
        # Verify product was added
        product = self.product_repo.get_product("test-product-123")
        self.assertIsNotNone(product)
        self.assertEqual(product.url, "https://bol.com/product/123")
        self.assertEqual(product.channel_id, 123456789)
    
    def test_update_product(self):
        """Test updating a product in the database."""
        # First add the product
        self.product_repo.add_product(self.product_config)
        
        # Update the product
        self.product_config.monitoring_interval = 120
        self.product_config.is_active = False
        result = self.product_repo.update_product(self.product_config)
        self.assertTrue(result)
        
        # Verify product was updated
        product = self.product_repo.get_product("test-product-123")
        self.assertIsNotNone(product)
        self.assertEqual(product.monitoring_interval, 120)
        self.assertFalse(product.is_active)
    
    def test_delete_product(self):
        """Test deleting a product from the database."""
        # First add the product
        self.product_repo.add_product(self.product_config)
        
        # Delete the product
        result = self.product_repo.delete_product("test-product-123")
        self.assertTrue(result)
        
        # Verify product was deleted
        product = self.product_repo.get_product("test-product-123")
        self.assertIsNone(product)
    
    def test_get_products_by_channel(self):
        """Test getting products by channel."""
        # Add two products with the same channel
        self.product_repo.add_product(self.product_config)
        
        second_config = ProductConfig(
            product_id="test-product-456",
            url="https://bol.com/product/456",
            url_type=URLType.PRODUCT.value,
            channel_id=123456789,  # Same channel
            guild_id=987654321,
            monitoring_interval=60,
            role_mentions=[],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.product_repo.add_product(second_config)
        
        # Get products by channel
        products = self.product_repo.get_products_by_channel(123456789)
        self.assertEqual(len(products), 2)
        product_ids = [p.product_id for p in products]
        self.assertIn("test-product-123", product_ids)
        self.assertIn("test-product-456", product_ids)
    
    def test_get_all_active_products(self):
        """Test getting all active products."""
        # Add one active and one inactive product
        self.product_repo.add_product(self.product_config)
        
        inactive_config = ProductConfig(
            product_id="test-product-456",
            url="https://bol.com/product/456",
            url_type=URLType.PRODUCT.value,
            channel_id=123456789,
            guild_id=987654321,
            monitoring_interval=60,
            role_mentions=[],
            is_active=False,  # Inactive
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.product_repo.add_product(inactive_config)
        
        # Get active products
        products = self.product_repo.get_all_active_products()
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].product_id, "test-product-123")


class TestProductStatusRepository(BaseRepositoryTest):
    """Test cases for ProductStatusRepository."""
    
    def test_update_product_status(self):
        """Test updating product status."""
        # First add the product
        self.product_repo.add_product(self.product_config)
        
        # Update product status
        result = self.status_repo.update_product_status(self.product_data)
        self.assertTrue(result)
        
        # Verify status was updated
        status = self.status_repo.get_product_status("test-product-123")
        self.assertIsNotNone(status)
        self.assertEqual(status.title, "Pokemon Scarlet")
        self.assertEqual(status.price, "€59.99")
        self.assertEqual(status.stock_status, StockStatus.IN_STOCK.value)
    
    def test_update_product_status_changes(self):
        """Test updating product status with changes."""
        # First add the product and initial status
        self.product_repo.add_product(self.product_config)
        self.status_repo.update_product_status(self.product_data)
        
        # Update status with changes
        updated_data = ProductData(
            title="Pokemon Scarlet",
            price="€49.99",  # Price changed
            original_price="€69.99",
            image_url="https://example.com/image.jpg",
            product_url="https://bol.com/product/123",
            uncached_url="https://bol.com/product/123?t=12345",
            stock_status=StockStatus.OUT_OF_STOCK.value,  # Status changed
            stock_level="Out of stock",
            website="bol.com",
            delivery_info="Currently unavailable",
            sold_by_bol=True,
            last_checked=datetime.utcnow(),
            product_id="test-product-123"
        )
        
        result = self.status_repo.update_product_status(updated_data)
        self.assertTrue(result)
        
        # Verify status was updated
        status = self.status_repo.get_product_status("test-product-123")
        self.assertIsNotNone(status)
        self.assertEqual(status.price, "€49.99")
        self.assertEqual(status.stock_status, StockStatus.OUT_OF_STOCK.value)
    
    def test_get_all_product_statuses(self):
        """Test getting all product statuses."""
        # Add two products and their statuses
        self.product_repo.add_product(self.product_config)
        self.status_repo.update_product_status(self.product_data)
        
        second_config = ProductConfig(
            product_id="test-product-456",
            url="https://bol.com/product/456",
            url_type=URLType.PRODUCT.value,
            channel_id=123456789,
            guild_id=987654321,
            monitoring_interval=60,
            role_mentions=[],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self.product_repo.add_product(second_config)
        
        second_data = ProductData(
            title="Pokemon Violet",
            price="€59.99",
            original_price="€69.99",
            image_url="https://example.com/image2.jpg",
            product_url="https://bol.com/product/456",
            uncached_url="https://bol.com/product/456?t=12345",
            stock_status=StockStatus.OUT_OF_STOCK.value,
            stock_level="Out of stock",
            website="bol.com",
            delivery_info="Currently unavailable",
            sold_by_bol=True,
            last_checked=datetime.utcnow(),
            product_id="test-product-456"
        )
        self.status_repo.update_product_status(second_data)
        
        # Get all statuses
        statuses = self.status_repo.get_all_product_statuses()
        self.assertEqual(len(statuses), 2)
        titles = [s.title for s in statuses]
        self.assertIn("Pokemon Scarlet", titles)
        self.assertIn("Pokemon Violet", titles)


class TestStockChangeRepository(BaseRepositoryTest):
    """Test cases for StockChangeRepository."""
    
    def test_add_stock_change(self):
        """Test adding a stock change event."""
        # First add the product
        self.product_repo.add_product(self.product_config)
        
        # Add stock change
        change_id = self.stock_change_repo.add_stock_change(self.stock_change)
        self.assertIsNotNone(change_id)
        
        # Verify stock change was added
        change = self.stock_change_repo.get_stock_change(change_id)
        self.assertIsNotNone(change)
        self.assertEqual(change.product_id, "test-product-123")
        self.assertEqual(change.previous_status, StockStatus.OUT_OF_STOCK.value)
        self.assertEqual(change.current_status, StockStatus.IN_STOCK.value)
        self.assertIsNotNone(change.price_change)
        self.assertEqual(change.price_change.previous_price, "€69.99")
        self.assertEqual(change.price_change.current_price, "€59.99")
    
    def test_mark_notification_sent(self):
        """Test marking a notification as sent."""
        # First add the product and stock change
        self.product_repo.add_product(self.product_config)
        change_id = self.stock_change_repo.add_stock_change(self.stock_change)
        
        # Mark notification as sent
        result = self.stock_change_repo.mark_notification_sent(change_id)
        self.assertTrue(result)
        
        # Verify notification was marked as sent
        change = self.stock_change_repo.get_stock_change(change_id)
        self.assertIsNotNone(change)
        self.assertTrue(change.notification_sent)
    
    def test_get_pending_notifications(self):
        """Test getting pending notifications."""
        # First add the product and stock changes
        self.product_repo.add_product(self.product_config)
        
        # Add one pending and one sent notification
        self.stock_change_repo.add_stock_change(self.stock_change)
        
        sent_change = StockChange(
            product_id="test-product-123",
            previous_status=StockStatus.IN_STOCK.value,
            current_status=StockStatus.OUT_OF_STOCK.value,
            timestamp=datetime.utcnow(),
            price_change=None,
            notification_sent=True  # Already sent
        )
        self.stock_change_repo.add_stock_change(sent_change)
        
        # Get pending notifications
        pending = self.stock_change_repo.get_pending_notifications()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].product_id, "test-product-123")
        self.assertEqual(pending[0].current_status, StockStatus.IN_STOCK.value)
        self.assertFalse(pending[0].notification_sent)


class TestMetricsRepository(BaseRepositoryTest):
    """Test cases for MetricsRepository."""
    
    def test_add_metric(self):
        """Test adding a monitoring metric."""
        # First add the product
        self.product_repo.add_product(self.product_config)
        
        # Add metric
        result = self.metrics_repo.add_metric(
            product_id="test-product-123",
            duration_ms=150,
            success=True,
            error_message=None
        )
        self.assertTrue(result)
        
        # Add failed metric
        result = self.metrics_repo.add_metric(
            product_id="test-product-123",
            duration_ms=200,
            success=False,
            error_message="Connection timeout"
        )
        self.assertTrue(result)
    
    def test_get_monitoring_status(self):
        """Test getting monitoring status."""
        # First add the product and metrics
        self.product_repo.add_product(self.product_config)
        
        # Add 4 successful metrics and 1 failed metric
        for i in range(4):
            self.metrics_repo.add_metric(
                product_id="test-product-123",
                duration_ms=150 + i * 10,
                success=True,
                error_message=None
            )
        
        self.metrics_repo.add_metric(
            product_id="test-product-123",
            duration_ms=200,
            success=False,
            error_message="Connection timeout"
        )
        
        # Get monitoring status
        status = self.metrics_repo.get_monitoring_status("test-product-123")
        self.assertIsNotNone(status)
        self.assertEqual(status.product_id, "test-product-123")
        self.assertTrue(status.is_active)
        self.assertEqual(status.success_rate, 80.0)  # 4 out of 5 = 80%
        self.assertEqual(status.error_count, 1)
        self.assertEqual(status.last_error, "Connection timeout")
    
    def test_get_average_duration(self):
        """Test getting average check duration."""
        # First add the product and metrics
        self.product_repo.add_product(self.product_config)
        
        # Add metrics with different durations
        durations = [100, 150, 200, 250]
        for duration in durations:
            self.metrics_repo.add_metric(
                product_id="test-product-123",
                duration_ms=duration,
                success=True,
                error_message=None
            )
        
        # Get average duration
        avg_duration = self.metrics_repo.get_average_duration("test-product-123")
        expected_avg = sum(durations) / len(durations)
        self.assertEqual(avg_duration, expected_avg)


if __name__ == "__main__":
    unittest.main()