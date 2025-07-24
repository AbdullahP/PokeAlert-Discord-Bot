"""
Unit tests for ProductManager class.
"""
import pytest
import asyncio
import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.services.product_manager import ProductManager
from src.models.product_data import ProductConfig, URLType, MonitoringStatus, DashboardData
from src.database.connection import DatabaseConnection


class TestProductManager:
    """Test cases for ProductManager."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_file.close()
        
        db = DatabaseConnection(temp_file.name)
        db.create_tables()
        
        yield db
        
        # Cleanup
        db.close()
        os.unlink(temp_file.name)
    
    @pytest.fixture
    def product_manager(self, temp_db):
        """Create ProductManager instance with test database."""
        manager = ProductManager()
        
        # Replace repositories with ones using test database
        manager.product_repo.db = temp_db
        manager.status_repo.db = temp_db
        manager.change_repo.db = temp_db
        manager.metrics_repo.db = temp_db
        
        return manager
    
    @pytest.fixture
    def sample_product_config(self):
        """Create a sample product configuration."""
        return ProductConfig.create_new(
            url="https://www.bol.com/nl/nl/p/pokemon-test/123456/",
            url_type=URLType.PRODUCT.value,
            channel_id=123456789,
            guild_id=987654321,
            monitoring_interval=60
        )
    
    def test_init(self):
        """Test ProductManager initialization."""
        manager = ProductManager()
        
        assert manager.product_repo is not None
        assert manager.status_repo is not None
        assert manager.change_repo is not None
        assert manager.metrics_repo is not None
        assert manager.logger is not None
    
    @pytest.mark.asyncio
    async def test_add_product_valid_product_url(self, product_manager):
        """Test adding a valid product URL."""
        url = "https://www.bol.com/nl/nl/p/pokemon-cards-booster-pack/9200000123456789/"
        channel_id = 123456789
        guild_id = 987654321
        
        product_id = await product_manager.add_product(url, channel_id, guild_id)
        
        assert product_id != ""
        assert len(product_id) > 0
        
        # Verify product was added to database
        config = await product_manager.get_product_config(product_id)
        assert config is not None
        assert config.url == "https://www.bol.com/nl/nl/p/9200000123456789/"
        assert config.url_type == URLType.PRODUCT.value
        assert config.channel_id == channel_id
        assert config.guild_id == guild_id
    
    @pytest.mark.asyncio
    async def test_add_product_valid_wishlist_url(self, product_manager):
        """Test adding a valid wishlist URL."""
        url = "https://www.bol.com/nl/nl/rnwy/account/wenslijst/pokemon-wishlist/123456/"
        channel_id = 123456789
        guild_id = 987654321
        
        product_id = await product_manager.add_product(url, channel_id, guild_id)
        
        assert product_id != ""
        
        # Verify product was added to database
        config = await product_manager.get_product_config(product_id)
        assert config is not None
        assert config.url == "https://www.bol.com/nl/nl/rnwy/account/wenslijst/123456/"
        assert config.url_type == URLType.WISHLIST.value
    
    @pytest.mark.asyncio
    async def test_add_product_invalid_url(self, product_manager):
        """Test adding an invalid URL."""
        url = "https://www.example.com/invalid-url"
        channel_id = 123456789
        guild_id = 987654321
        
        product_id = await product_manager.add_product(url, channel_id, guild_id)
        
        assert product_id == ""
    
    @pytest.mark.asyncio
    async def test_add_product_duplicate_url(self, product_manager):
        """Test adding a duplicate URL returns existing product ID."""
        url = "https://www.bol.com/nl/nl/p/pokemon-cards/123456/"
        channel_id = 123456789
        guild_id = 987654321
        
        # Add product first time
        product_id1 = await product_manager.add_product(url, channel_id, guild_id)
        assert product_id1 != ""
        
        # Add same product again
        product_id2 = await product_manager.add_product(url, channel_id, guild_id)
        assert product_id2 == product_id1
    
    @pytest.mark.asyncio
    async def test_add_product_minimum_interval(self, product_manager):
        """Test that monitoring interval is enforced to minimum 30 seconds."""
        url = "https://www.bol.com/nl/nl/p/pokemon-cards/123456/"
        channel_id = 123456789
        guild_id = 987654321
        
        product_id = await product_manager.add_product(url, channel_id, guild_id, monitoring_interval=10)
        
        config = await product_manager.get_product_config(product_id)
        assert config.monitoring_interval == 30  # Should be enforced to minimum
    
    @pytest.mark.asyncio
    async def test_remove_product_existing(self, product_manager, sample_product_config):
        """Test removing an existing product."""
        # Add product first
        product_manager.product_repo.add_product(sample_product_config)
        
        # Remove product
        result = await product_manager.remove_product(sample_product_config.product_id)
        
        assert result is True
        
        # Verify product was removed
        config = await product_manager.get_product_config(sample_product_config.product_id)
        assert config is None
    
    @pytest.mark.asyncio
    async def test_remove_product_nonexistent(self, product_manager):
        """Test removing a non-existent product."""
        result = await product_manager.remove_product("nonexistent-id")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_update_product_existing(self, product_manager, sample_product_config):
        """Test updating an existing product."""
        # Add product first
        product_manager.product_repo.add_product(sample_product_config)
        
        # Update configuration
        sample_product_config.monitoring_interval = 120
        sample_product_config.role_mentions = ["role1", "role2"]
        
        result = await product_manager.update_product(sample_product_config.product_id, sample_product_config)
        
        assert result is True
        
        # Verify update
        updated_config = await product_manager.get_product_config(sample_product_config.product_id)
        assert updated_config.monitoring_interval == 120
        assert updated_config.role_mentions == ["role1", "role2"]
    
    @pytest.mark.asyncio
    async def test_update_product_nonexistent(self, product_manager, sample_product_config):
        """Test updating a non-existent product."""
        result = await product_manager.update_product("nonexistent-id", sample_product_config)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_update_product_invalid_config(self, product_manager, sample_product_config):
        """Test updating with invalid configuration."""
        # Add product first
        product_manager.product_repo.add_product(sample_product_config)
        
        # Create invalid config
        invalid_config = sample_product_config
        invalid_config.monitoring_interval = 10  # Below minimum
        
        result = await product_manager.update_product(sample_product_config.product_id, invalid_config)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_products_by_channel(self, product_manager):
        """Test getting products by channel."""
        channel_id = 123456789
        guild_id = 987654321
        
        # Add multiple products to the same channel
        config1 = ProductConfig.create_new(
            url="https://www.bol.com/nl/nl/p/111111/",
            url_type=URLType.PRODUCT.value,
            channel_id=channel_id,
            guild_id=guild_id
        )
        config2 = ProductConfig.create_new(
            url="https://www.bol.com/nl/nl/p/222222/",
            url_type=URLType.PRODUCT.value,
            channel_id=channel_id,
            guild_id=guild_id
        )
        
        product_manager.product_repo.add_product(config1)
        product_manager.product_repo.add_product(config2)
        
        # Add product to different channel
        config3 = ProductConfig.create_new(
            url="https://www.bol.com/nl/nl/p/333333/",
            url_type=URLType.PRODUCT.value,
            channel_id=999999999,
            guild_id=guild_id
        )
        product_manager.product_repo.add_product(config3)
        
        products = await product_manager.get_products_by_channel(channel_id)
        
        assert len(products) == 2
        assert all(p.channel_id == channel_id for p in products)
    
    @pytest.mark.asyncio
    async def test_get_products_by_guild(self, product_manager):
        """Test getting products by guild."""
        guild_id = 987654321
        
        # Add products to the guild
        config1 = ProductConfig.create_new(
            url="https://www.bol.com/nl/nl/p/111111/",
            url_type=URLType.PRODUCT.value,
            channel_id=123456789,
            guild_id=guild_id
        )
        config2 = ProductConfig.create_new(
            url="https://www.bol.com/nl/nl/p/222222/",
            url_type=URLType.PRODUCT.value,
            channel_id=987654321,
            guild_id=guild_id
        )
        
        product_manager.product_repo.add_product(config1)
        product_manager.product_repo.add_product(config2)
        
        products = await product_manager.get_products_by_guild(guild_id)
        
        assert len(products) == 2
        assert all(p.guild_id == guild_id for p in products)
    
    @pytest.mark.asyncio
    async def test_get_all_active_products(self, product_manager):
        """Test getting all active products."""
        # Add active product
        config1 = ProductConfig.create_new(
            url="https://www.bol.com/nl/nl/p/111111/",
            url_type=URLType.PRODUCT.value,
            channel_id=123456789,
            guild_id=987654321
        )
        config1.is_active = True
        
        # Add inactive product
        config2 = ProductConfig.create_new(
            url="https://www.bol.com/nl/nl/p/222222/",
            url_type=URLType.PRODUCT.value,
            channel_id=123456789,
            guild_id=987654321
        )
        config2.is_active = False
        
        product_manager.product_repo.add_product(config1)
        product_manager.product_repo.add_product(config2)
        
        active_products = await product_manager.get_all_active_products()
        
        assert len(active_products) == 1
        assert active_products[0].product_id == config1.product_id
        assert active_products[0].is_active is True
    
    @pytest.mark.asyncio
    async def test_get_monitoring_status(self, product_manager):
        """Test getting monitoring status for all products."""
        # Add test product
        config = ProductConfig.create_new(
            url="https://www.bol.com/nl/nl/p/111111/",
            url_type=URLType.PRODUCT.value,
            channel_id=123456789,
            guild_id=987654321
        )
        product_manager.product_repo.add_product(config)
        
        # Add some metrics
        product_manager.metrics_repo.add_metric(config.product_id, 1000, True)
        product_manager.metrics_repo.add_metric(config.product_id, 1200, True)
        product_manager.metrics_repo.add_metric(config.product_id, 800, False, "Network error")
        
        status_dict = await product_manager.get_monitoring_status()
        
        assert config.product_id in status_dict
        status = status_dict[config.product_id]
        assert isinstance(status, MonitoringStatus)
        assert status.product_id == config.product_id
        assert status.success_rate > 0
        assert status.error_count > 0
    
    @pytest.mark.asyncio
    async def test_get_dashboard_data(self, product_manager):
        """Test getting dashboard data for a guild."""
        guild_id = 987654321
        
        # Add test products
        config1 = ProductConfig.create_new(
            url="https://www.bol.com/nl/nl/p/111111/",
            url_type=URLType.PRODUCT.value,
            channel_id=123456789,
            guild_id=guild_id
        )
        config2 = ProductConfig.create_new(
            url="https://www.bol.com/nl/nl/p/222222/",
            url_type=URLType.PRODUCT.value,
            channel_id=123456789,
            guild_id=guild_id
        )
        config2.is_active = False
        
        product_manager.product_repo.add_product(config1)
        product_manager.product_repo.add_product(config2)
        
        # Add metrics
        product_manager.metrics_repo.add_metric(config1.product_id, 1000, True)
        product_manager.metrics_repo.add_metric(config2.product_id, 1200, True)
        
        dashboard = await product_manager.get_dashboard_data(guild_id)
        
        assert isinstance(dashboard, DashboardData)
        assert dashboard.total_products == 2
        assert dashboard.active_products == 1
        assert dashboard.success_rate >= 0
        assert isinstance(dashboard.recent_stock_changes, list)
        assert isinstance(dashboard.error_summary, dict)
    
    @pytest.mark.asyncio
    async def test_set_product_active(self, product_manager, sample_product_config):
        """Test setting product active status."""
        # Add product
        product_manager.product_repo.add_product(sample_product_config)
        
        # Set inactive
        result = await product_manager.set_product_active(sample_product_config.product_id, False)
        assert result is True
        
        # Verify status
        config = await product_manager.get_product_config(sample_product_config.product_id)
        assert config.is_active is False
        
        # Set active again
        result = await product_manager.set_product_active(sample_product_config.product_id, True)
        assert result is True
        
        config = await product_manager.get_product_config(sample_product_config.product_id)
        assert config.is_active is True
    
    @pytest.mark.asyncio
    async def test_update_channel_assignment(self, product_manager, sample_product_config):
        """Test updating channel assignment."""
        # Add product
        product_manager.product_repo.add_product(sample_product_config)
        
        new_channel_id = 999999999
        result = await product_manager.update_channel_assignment(
            sample_product_config.product_id, new_channel_id
        )
        
        assert result is True
        
        # Verify update
        config = await product_manager.get_product_config(sample_product_config.product_id)
        assert config.channel_id == new_channel_id
    
    @pytest.mark.asyncio
    async def test_update_role_mentions(self, product_manager, sample_product_config):
        """Test updating role mentions."""
        # Add product
        product_manager.product_repo.add_product(sample_product_config)
        
        new_roles = ["role1", "role2", "role3"]
        result = await product_manager.update_role_mentions(
            sample_product_config.product_id, new_roles
        )
        
        assert result is True
        
        # Verify update
        config = await product_manager.get_product_config(sample_product_config.product_id)
        assert config.role_mentions == new_roles
    
    def test_validate_url_valid_product(self, product_manager):
        """Test URL validation for valid product URLs."""
        valid_urls = [
            "https://www.bol.com/nl/nl/p/pokemon-cards/9200000123456789/",
            "https://www.bol.com/nl/nl/p/test-product/123456/",
            "https://www.bol.com/be/be/p/pokemon-booster/987654321/"
        ]
        
        for url in valid_urls:
            assert product_manager.validate_url(url) is True
    
    def test_validate_url_valid_wishlist(self, product_manager):
        """Test URL validation for valid wishlist URLs."""
        valid_urls = [
            "https://www.bol.com/nl/nl/rnwy/account/wenslijst/pokemon-wishlist/123456/",
            "https://www.bol.com/be/be/rnwy/account/wenslijst/my-list/987654/"
        ]
        
        for url in valid_urls:
            assert product_manager.validate_url(url) is True
    
    def test_validate_url_invalid(self, product_manager):
        """Test URL validation for invalid URLs."""
        invalid_urls = [
            "https://www.example.com/product/123",
            "https://www.amazon.com/dp/B123456",
            "not-a-url",
            "",
            "https://www.bol.com/invalid-path"
        ]
        
        for url in invalid_urls:
            assert product_manager.validate_url(url) is False
    
    def test_validate_and_normalize_url_product(self, product_manager):
        """Test URL validation and normalization for product URLs."""
        test_cases = [
            (
                "https://www.bol.com/nl/nl/p/pokemon-cards-booster-pack/9200000123456789/",
                URLType.PRODUCT,
                "https://www.bol.com/nl/nl/p/9200000123456789/"
            ),
            (
                "https://www.bol.com/be/be/p/test-product/123456/?param=value",
                URLType.PRODUCT,
                "https://www.bol.com/nl/nl/p/123456/"
            )
        ]
        
        for input_url, expected_type, expected_url in test_cases:
            url_type, normalized_url = product_manager._validate_and_normalize_url(input_url)
            assert url_type == expected_type
            assert normalized_url == expected_url
    
    def test_validate_and_normalize_url_wishlist(self, product_manager):
        """Test URL validation and normalization for wishlist URLs."""
        test_cases = [
            (
                "https://www.bol.com/nl/nl/rnwy/account/wenslijst/pokemon-wishlist/123456/",
                URLType.WISHLIST,
                "https://www.bol.com/nl/nl/rnwy/account/wenslijst/123456/"
            ),
            (
                "https://www.bol.com/be/be/rnwy/account/wenslijst/my-list/987654/?param=value",
                URLType.WISHLIST,
                "https://www.bol.com/nl/nl/rnwy/account/wenslijst/987654/"
            )
        ]
        
        for input_url, expected_type, expected_url in test_cases:
            url_type, normalized_url = product_manager._validate_and_normalize_url(input_url)
            assert url_type == expected_type
            assert normalized_url == expected_url
    
    def test_extract_product_id_from_url(self, product_manager):
        """Test extracting product ID from URLs."""
        test_cases = [
            ("https://www.bol.com/nl/nl/p/pokemon-cards/9200000123456789/", "9200000123456789"),
            ("https://www.bol.com/be/be/p/test-product/123456/", "123456"),
            ("https://www.example.com/product/123", None),
            ("invalid-url", None)
        ]
        
        for url, expected_id in test_cases:
            result = product_manager.extract_product_id_from_url(url)
            assert result == expected_id
    
    def test_extract_wishlist_id_from_url(self, product_manager):
        """Test extracting wishlist ID from URLs."""
        test_cases = [
            ("https://www.bol.com/nl/nl/rnwy/account/wenslijst/pokemon-wishlist/123456/", "123456"),
            ("https://www.bol.com/be/be/rnwy/account/wenslijst/my-list/987654/", "987654"),
            ("https://www.bol.com/nl/nl/p/product/123456/", None),
            ("invalid-url", None)
        ]
        
        for url, expected_id in test_cases:
            result = product_manager.extract_wishlist_id_from_url(url)
            assert result == expected_id


if __name__ == "__main__":
    pytest.main([__file__])