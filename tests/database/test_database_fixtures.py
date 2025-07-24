"""
Test database fixtures and utilities for testing.
"""
import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta

from src.database.connection import DatabaseConnection
from src.models.product_data import ProductConfig, ProductData, StockStatus, URLType


class TestDatabaseFixtures:
    """Test suite for database fixtures."""
    
    @pytest.fixture
    def test_db(self):
        """Create a test database with tables."""
        # Create a temporary database file
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "test_db.sqlite"
        
        # Initialize database connection
        db = DatabaseConnection(str(db_path))
        db.create_tables()
        
        yield db
        
        # Clean up
        db.close()
        temp_dir.cleanup()
    
    @pytest.fixture
    def populated_db(self, test_db):
        """Create a test database populated with test data."""
        # Add test products
        conn = test_db.connect()
        cursor = conn.cursor()
        
        # Add products
        products = [
            (
                "test-product-1",
                "https://www.bol.com/nl/nl/p/pokemon-scarlet/9300000096287/",
                "product",
                123456789,
                987654321,
                60,
                '["<@&123456>"]',
                1,
                (datetime.utcnow() - timedelta(days=7)).isoformat(),
                datetime.utcnow().isoformat()
            ),
            (
                "test-product-2",
                "https://www.bol.com/nl/nl/p/pokemon-violet/9300000096288/",
                "product",
                123456789,
                987654321,
                120,
                '["<@&123456>", "<@&789012>"]',
                1,
                (datetime.utcnow() - timedelta(days=5)).isoformat(),
                datetime.utcnow().isoformat()
            ),
            (
                "test-product-3",
                "https://www.bol.com/nl/nl/p/pokemon-cards/9300000096289/",
                "product",
                987654321,  # Different channel
                987654321,
                60,
                '[]',
                0,  # Inactive
                (datetime.utcnow() - timedelta(days=3)).isoformat(),
                datetime.utcnow().isoformat()
            )
        ]
        
        cursor.executemany(
            """
            INSERT INTO products (
                id, url, url_type, channel_id, guild_id, monitoring_interval,
                role_mentions, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            products
        )
        
        # Add product statuses
        statuses = [
            (
                "test-product-1",
                "Pokemon Scarlet",
                "€59.99",
                "In Stock",
                "10+ available",
                datetime.utcnow().isoformat()
            ),
            (
                "test-product-2",
                "Pokemon Violet",
                "€59.99",
                "Out of Stock",
                "Uitverkocht",
                datetime.utcnow().isoformat()
            ),
            (
                "test-product-3",
                "Pokemon Cards",
                "€9.99",
                "In Stock",
                "5 available",
                datetime.utcnow().isoformat()
            )
        ]
        
        cursor.executemany(
            """
            INSERT INTO product_status (
                product_id, title, price, stock_status, stock_level, last_checked
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            statuses
        )
        
        # Add stock changes
        stock_changes = [
            (
                "test-product-1",
                "Out of Stock",
                "In Stock",
                (datetime.utcnow() - timedelta(hours=12)).isoformat(),
                1  # Notification sent
            ),
            (
                "test-product-2",
                "In Stock",
                "Out of Stock",
                (datetime.utcnow() - timedelta(hours=6)).isoformat(),
                1  # Notification sent
            ),
            (
                "test-product-1",
                "In Stock",
                "Out of Stock",
                (datetime.utcnow() - timedelta(hours=36)).isoformat(),
                1  # Notification sent
            )
        ]
        
        cursor.executemany(
            """
            INSERT INTO stock_changes (
                product_id, previous_status, current_status, timestamp, notification_sent
            ) VALUES (?, ?, ?, ?, ?)
            """,
            stock_changes
        )
        
        # Add monitoring metrics
        metrics = []
        
        # Add successful checks for product 1
        for i in range(20):
            metrics.append((
                "test-product-1",
                100 + i * 5,  # Varying response times
                1,  # Success
                None,
                (datetime.utcnow() - timedelta(hours=i)).isoformat()
            ))
        
        # Add some failed checks for product 1
        for i in range(3):
            metrics.append((
                "test-product-1",
                200,
                0,  # Failure
                "Connection timeout",
                (datetime.utcnow() - timedelta(hours=i * 4)).isoformat()
            ))
        
        # Add successful checks for product 2
        for i in range(15):
            metrics.append((
                "test-product-2",
                120 + i * 3,
                1,  # Success
                None,
                (datetime.utcnow() - timedelta(hours=i)).isoformat()
            ))
        
        # Add some failed checks for product 2
        metrics.append((
            "test-product-2",
            180,
            0,  # Failure
            "HTML parsing error",
            (datetime.utcnow() - timedelta(hours=8)).isoformat()
        ))
        
        cursor.executemany(
            """
            INSERT INTO monitoring_metrics (
                product_id, check_duration_ms, success, error_message, timestamp
            ) VALUES (?, ?, ?, ?, ?)
            """,
            metrics
        )
        
        conn.commit()
        
        return test_db
    
    def test_database_creation(self, test_db):
        """Test that the database is created with tables."""
        conn = test_db.connect()
        cursor = conn.cursor()
        
        # Check that tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row['name'] for row in cursor.fetchall()]
        
        assert "products" in tables
        assert "product_status" in tables
        assert "stock_changes" in tables
        assert "monitoring_metrics" in tables
    
    def test_populated_database(self, populated_db):
        """Test that the database is populated with test data."""
        conn = populated_db.connect()
        cursor = conn.cursor()
        
        # Check products
        cursor.execute("SELECT COUNT(*) as count FROM products")
        assert cursor.fetchone()['count'] == 3
        
        # Check active products
        cursor.execute("SELECT COUNT(*) as count FROM products WHERE is_active = 1")
        assert cursor.fetchone()['count'] == 2
        
        # Check product statuses
        cursor.execute("SELECT COUNT(*) as count FROM product_status")
        assert cursor.fetchone()['count'] == 3
        
        # Check stock changes
        cursor.execute("SELECT COUNT(*) as count FROM stock_changes")
        assert cursor.fetchone()['count'] == 3
        
        # Check metrics
        cursor.execute("SELECT COUNT(*) as count FROM monitoring_metrics")
        assert cursor.fetchone()['count'] == 39  # 20 + 3 + 15 + 1
    
    def test_query_product_by_id(self, populated_db):
        """Test querying a product by ID."""
        conn = populated_db.connect()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM products WHERE id = ?", ("test-product-1",))
        product = cursor.fetchone()
        
        assert product is not None
        assert product['url'] == "https://www.bol.com/nl/nl/p/pokemon-scarlet/9300000096287/"
        assert product['channel_id'] == 123456789
        assert product['is_active'] == 1
    
    def test_query_products_by_channel(self, populated_db):
        """Test querying products by channel."""
        conn = populated_db.connect()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM products WHERE channel_id = ?", (123456789,))
        products = cursor.fetchall()
        
        assert len(products) == 2
        product_ids = [p['id'] for p in products]
        assert "test-product-1" in product_ids
        assert "test-product-2" in product_ids
    
    def test_query_stock_changes(self, populated_db):
        """Test querying stock changes."""
        conn = populated_db.connect()
        cursor = conn.cursor()
        
        # Get recent stock changes for a product
        cursor.execute(
            """
            SELECT * FROM stock_changes 
            WHERE product_id = ? 
            ORDER BY timestamp DESC
            """, 
            ("test-product-1",)
        )
        changes = cursor.fetchall()
        
        assert len(changes) == 2
        assert changes[0]['previous_status'] == "Out of Stock"
        assert changes[0]['current_status'] == "In Stock"
    
    def test_query_monitoring_metrics(self, populated_db):
        """Test querying monitoring metrics."""
        conn = populated_db.connect()
        cursor = conn.cursor()
        
        # Calculate success rate for a product
        cursor.execute(
            """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes
            FROM monitoring_metrics
            WHERE product_id = ?
            """,
            ("test-product-1",)
        )
        result = cursor.fetchone()
        
        total = result['total']
        successes = result['successes']
        success_rate = (successes / total) * 100 if total > 0 else 0
        
        assert total == 23  # 20 successes + 3 failures
        assert successes == 20
        assert success_rate == (20 / 23) * 100
"""