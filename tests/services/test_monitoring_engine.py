"""
Unit tests for the monitoring engine.
"""
import pytest
import asyncio
import aiohttp
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from src.services.monitoring_engine import MonitoringEngine
from src.models.product_data import ProductData, ProductConfig, StockChange, StockStatus, URLType
from src.config.config_manager import ConfigManager


@pytest.fixture
def config_manager():
    """Create a mock config manager."""
    config = ConfigManager()
    config.set('monitoring.default_interval', 60)
    config.set('monitoring.min_interval', 30)
    config.set('monitoring.max_concurrent', 5)
    config.set('monitoring.request_timeout', 10)
    config.set('monitoring.anti_detection.min_delay', 0.1)  # Short delay for tests
    config.set('monitoring.anti_detection.max_delay', 0.2)  # Short delay for tests
    return config


@pytest.fixture
def monitoring_engine(config_manager):
    """Create a monitoring engine with mocked repositories."""
    engine = MonitoringEngine(config_manager)
    
    # Mock repositories
    engine.product_repo = MagicMock()
    engine.status_repo = MagicMock()
    engine.stock_change_repo = MagicMock()
    engine.metrics_repo = MagicMock()
    
    return engine


class TestMonitoringEngine:
    """Test suite for the monitoring engine."""
    
    @pytest.mark.asyncio
    async def test_detect_stock_status(self, monitoring_engine):
        """Test detecting stock status from Dutch text."""
        # Test in-stock detection
        assert monitoring_engine._detect_stock_status("Op voorraad") == StockStatus.IN_STOCK.value
        assert monitoring_engine._detect_stock_status("Vandaag besteld, morgen in huis") == StockStatus.IN_STOCK.value
        
        # Test out-of-stock detection
        assert monitoring_engine._detect_stock_status("Tijdelijk uitverkocht") == StockStatus.OUT_OF_STOCK.value
        assert monitoring_engine._detect_stock_status("Niet op voorraad") == StockStatus.OUT_OF_STOCK.value
        
        # Test pre-order detection
        assert monitoring_engine._detect_stock_status("Nog niet verschenen") == StockStatus.PRE_ORDER.value
        assert monitoring_engine._detect_stock_status("Pre-order") == StockStatus.PRE_ORDER.value
        assert monitoring_engine._detect_stock_status("Binnenkort verwacht") == StockStatus.PRE_ORDER.value
        
        # Test unknown status
        assert monitoring_engine._detect_stock_status("Some random text") == StockStatus.UNKNOWN.value
    
    @pytest.mark.asyncio
    async def test_add_cache_busting(self, monitoring_engine):
        """Test adding cache-busting parameters to URLs."""
        url = "https://www.bol.com/nl/p/pokemon-sword/9200000115093148/"
        result = monitoring_engine._add_cache_busting(url)
        
        assert "_=" in result
        assert url in result
    
    @pytest.mark.asyncio
    async def test_get_request_headers(self, monitoring_engine):
        """Test generating request headers with anti-detection measures."""
        headers = monitoring_engine._get_request_headers()
        
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Accept-Language" in headers
        assert "Referer" in headers
        assert "nl-NL" in headers["Accept-Language"]  # Dutch language for bol.com
    
    @pytest.mark.asyncio
    async def test_generate_product_id(self, monitoring_engine):
        """Test generating product IDs from URLs."""
        url = "https://www.bol.com/nl/p/pokemon-sword/9200000115093148/"
        product_id = monitoring_engine._generate_product_id(url)
        
        assert product_id == "bol-9200000115093148"
        
        # Test with URL that doesn't match pattern
        url = "https://www.bol.com/nl/pokemon/"
        product_id = monitoring_engine._generate_product_id(url)
        
        assert product_id.startswith("bol-")
    
    @pytest.mark.asyncio
    async def test_calculate_price_difference(self, monitoring_engine):
        """Test calculating price differences."""
        assert monitoring_engine._calculate_price_difference("€10.00", "€15.00") == "+€5.00"
        assert monitoring_engine._calculate_price_difference("€20.00", "€15.00") == "-€5.00"
        assert monitoring_engine._calculate_price_difference("€10", "€15") == "+€5.00"
        assert monitoring_engine._calculate_price_difference("invalid", "€15.00") == "€0.00"
    
    @pytest.mark.asyncio
    async def test_calculate_price_percentage(self, monitoring_engine):
        """Test calculating price change percentages."""
        assert monitoring_engine._calculate_price_percentage("€10.00", "€15.00") == 50.0
        assert monitoring_engine._calculate_price_percentage("€20.00", "€15.00") == -25.0
        assert monitoring_engine._calculate_price_percentage("€0.00", "€15.00") == 0.0
        assert monitoring_engine._calculate_price_percentage("invalid", "€15.00") == 0.0
    
    @pytest.mark.asyncio
    async def test_parse_product_page(self, monitoring_engine):
        """Test parsing product page HTML."""
        # Mock HTML content
        html_content = """
        <html>
            <head><title>Test Product</title></head>
            <body>
                <h1 data-test="title">Pokemon Sword</h1>
                <span data-test="price">€59.99</span>
                <del data-test="list-price">€69.99</del>
                <img data-test="product-image" src="https://example.com/image.jpg">
                <div class="buy-block__delivery">Op voorraad</div>
                <div class="buy-block__delivery-message">Vandaag besteld, morgen in huis</div>
                <div class="buy-block__seller">Verkoop door bol.com</div>
            </body>
        </html>
        """
        
        product_url = "https://www.bol.com/nl/p/pokemon-sword/9200000115093148/"
        product = await monitoring_engine._parse_product_page(html_content, product_url)
        
        assert product.title == "Pokemon Sword"
        assert product.price == "€59.99"
        assert product.original_price == "€69.99"
        assert product.image_url == "https://example.com/image.jpg"
        assert product.stock_status == StockStatus.IN_STOCK.value
        assert product.delivery_info == "Vandaag besteld, morgen in huis"
        assert product.sold_by_bol is True
        assert product.product_id == "bol-9200000115093148"
    
    @pytest.mark.asyncio
    async def test_parse_wishlist_page(self, monitoring_engine):
        """Test parsing wishlist page HTML."""
        # Mock HTML content
        html_content = """
        <html>
            <body>
                <a class="product-title" href="/nl/p/pokemon-sword/9200000115093148/">Pokemon Sword</a>
                <a href="/nl/p/pokemon-shield/9200000115093149/">Pokemon Shield</a>
                <a href="/nl/c/games/">Games Category</a>
            </body>
        </html>
        """
        
        wishlist_url = "https://www.bol.com/nl/wl/12345/"
        product_urls = await monitoring_engine._parse_wishlist_page(html_content, wishlist_url)
        
        assert len(product_urls) == 2
        assert "https://www.bol.com/nl/p/pokemon-sword/9200000115093148/" in product_urls
        assert "https://www.bol.com/nl/p/pokemon-shield/9200000115093149/" in product_urls
    
    @pytest.mark.asyncio
    async def test_monitor_product(self, monitoring_engine):
        """Test monitoring a single product."""
        product_url = "https://www.bol.com/nl/p/pokemon-sword/9200000115093148/"
        
        # Mock fetch_page to return HTML content
        html_content = """
        <html>
            <head><title>Test Product</title></head>
            <body>
                <h1 data-test="title">Pokemon Sword</h1>
                <span data-test="price">€59.99</span>
                <div class="buy-block__delivery">Op voorraad</div>
            </body>
        </html>
        """
        
        with patch.object(monitoring_engine, '_fetch_page', AsyncMock(return_value=html_content)):
            product = await monitoring_engine.monitor_product(product_url)
            
            assert product.title == "Pokemon Sword"
            assert product.price == "€59.99"
            assert product.stock_status == StockStatus.IN_STOCK.value
            assert product.product_id == "bol-9200000115093148"
    
    @pytest.mark.asyncio
    async def test_monitor_wishlist(self, monitoring_engine):
        """Test monitoring a wishlist."""
        wishlist_url = "https://www.bol.com/nl/wl/12345/"
        
        # Mock fetch_page to return HTML content for wishlist
        wishlist_html = """
        <html>
            <body>
                <a class="product-title" href="/nl/p/pokemon-sword/9200000115093148/">Pokemon Sword</a>
                <a href="/nl/p/pokemon-shield/9200000115093149/">Pokemon Shield</a>
            </body>
        </html>
        """
        
        # Mock monitor_product to return product data
        async def mock_monitor_product(url):
            if "sword" in url:
                return ProductData(
                    title="Pokemon Sword",
                    price="€59.99",
                    original_price="€59.99",
                    image_url="",
                    product_url=url,
                    uncached_url=url,
                    stock_status=StockStatus.IN_STOCK.value,
                    stock_level="",
                    website="bol.com",
                    delivery_info="",
                    sold_by_bol=True,
                    last_checked=datetime.utcnow(),
                    product_id="bol-9200000115093148"
                )
            else:
                return ProductData(
                    title="Pokemon Shield",
                    price="€59.99",
                    original_price="€59.99",
                    image_url="",
                    product_url=url,
                    uncached_url=url,
                    stock_status=StockStatus.OUT_OF_STOCK.value,
                    stock_level="",
                    website="bol.com",
                    delivery_info="",
                    sold_by_bol=True,
                    last_checked=datetime.utcnow(),
                    product_id="bol-9200000115093149"
                )
        
        with patch.object(monitoring_engine, '_fetch_page', AsyncMock(return_value=wishlist_html)), \
             patch.object(monitoring_engine, 'monitor_product', AsyncMock(side_effect=mock_monitor_product)):
            
            products = await monitoring_engine.monitor_wishlist(wishlist_url)
            
            assert len(products) == 2
            assert products[0].title == "Pokemon Sword"
            assert products[0].stock_status == StockStatus.IN_STOCK.value
            assert products[1].title == "Pokemon Shield"
            assert products[1].stock_status == StockStatus.OUT_OF_STOCK.value
    
    @pytest.mark.asyncio
    async def test_detect_stock_changes(self, monitoring_engine):
        """Test detecting stock changes."""
        # Create test products
        products = [
            ProductData(
                title="Pokemon Sword",
                price="€59.99",
                original_price="€59.99",
                image_url="",
                product_url="https://www.bol.com/nl/p/pokemon-sword/9200000115093148/",
                uncached_url="https://www.bol.com/nl/p/pokemon-sword/9200000115093148/",
                stock_status=StockStatus.IN_STOCK.value,
                stock_level="",
                website="bol.com",
                delivery_info="",
                sold_by_bol=True,
                last_checked=datetime.utcnow(),
                product_id="bol-9200000115093148"
            ),
            ProductData(
                title="Pokemon Shield",
                price="€54.99",  # Price changed
                original_price="€59.99",
                image_url="",
                product_url="https://www.bol.com/nl/p/pokemon-shield/9200000115093149/",
                uncached_url="https://www.bol.com/nl/p/pokemon-shield/9200000115093149/",
                stock_status=StockStatus.IN_STOCK.value,  # Status changed
                stock_level="",
                website="bol.com",
                delivery_info="",
                sold_by_bol=True,
                last_checked=datetime.utcnow(),
                product_id="bol-9200000115093149"
            )
        ]
        
        # Mock previous product data
        previous_sword = ProductData(
            title="Pokemon Sword",
            price="€59.99",
            original_price="€59.99",
            image_url="",
            product_url="https://www.bol.com/nl/p/pokemon-sword/9200000115093148/",
            uncached_url="https://www.bol.com/nl/p/pokemon-sword/9200000115093148/",
            stock_status=StockStatus.IN_STOCK.value,  # Same status
            stock_level="",
            website="bol.com",
            delivery_info="",
            sold_by_bol=True,
            last_checked=datetime.utcnow(),
            product_id="bol-9200000115093148"
        )
        
        previous_shield = ProductData(
            title="Pokemon Shield",
            price="€59.99",  # Different price
            original_price="€59.99",
            image_url="",
            product_url="https://www.bol.com/nl/p/pokemon-shield/9200000115093149/",
            uncached_url="https://www.bol.com/nl/p/pokemon-shield/9200000115093149/",
            stock_status=StockStatus.OUT_OF_STOCK.value,  # Different status
            stock_level="",
            website="bol.com",
            delivery_info="",
            sold_by_bol=True,
            last_checked=datetime.utcnow(),
            product_id="bol-9200000115093149"
        )
        
        # Mock repository methods
        monitoring_engine.status_repo.get_product_status = AsyncMock(
            side_effect=lambda product_id: previous_sword if product_id == "bol-9200000115093148" else previous_shield
        )
        monitoring_engine.status_repo.update_product_status = AsyncMock(return_value=True)
        monitoring_engine.stock_change_repo.add_stock_change = AsyncMock(return_value=1)
        
        # Test stock change detection
        changes = await monitoring_engine.detect_stock_changes(products)
        
        # Only Shield should have a stock change
        assert len(changes) == 1
        assert changes[0].product_id == "bol-9200000115093149"
        assert changes[0].previous_status == StockStatus.OUT_OF_STOCK.value
        assert changes[0].current_status == StockStatus.IN_STOCK.value
        assert changes[0].price_change is not None
        assert changes[0].price_change.previous_price == "€59.99"
        assert changes[0].price_change.current_price == "€54.99"
    
    @pytest.mark.asyncio
    async def test_start_and_stop_monitoring(self, monitoring_engine):
        """Test starting and stopping monitoring tasks."""
        # Create test product configs
        configs = [
            ProductConfig(
                product_id="bol-9200000115093148",
                url="https://www.bol.com/nl/p/pokemon-sword/9200000115093148/",
                url_type=URLType.PRODUCT.value,
                channel_id=123456789,
                guild_id=987654321,
                monitoring_interval=60
            ),
            ProductConfig(
                product_id="bol-wishlist-12345",
                url="https://www.bol.com/nl/wl/12345/",
                url_type=URLType.WISHLIST.value,
                channel_id=123456789,
                guild_id=987654321,
                monitoring_interval=120
            )
        ]
        
        # Mock _monitor_task to prevent actual monitoring
        with patch.object(monitoring_engine, '_monitor_task', AsyncMock()):
            # Start monitoring
            await monitoring_engine.start_monitoring(configs)
            
            # Check that tasks were created
            assert len(monitoring_engine.monitoring_tasks) == 2
            assert "bol-9200000115093148" in monitoring_engine.monitoring_tasks
            assert "bol-wishlist-12345" in monitoring_engine.monitoring_tasks
            
            # Stop monitoring for one product
            await monitoring_engine.stop_monitoring("bol-9200000115093148")
            
            # Check that task was removed
            assert len(monitoring_engine.monitoring_tasks) == 1
            assert "bol-9200000115093148" not in monitoring_engine.monitoring_tasks
            assert "bol-wishlist-12345" in monitoring_engine.monitoring_tasks
            
            # Stop all monitoring
            await monitoring_engine.stop_all_monitoring()
            
            # Check that all tasks were removed
            assert len(monitoring_engine.monitoring_tasks) == 0
            assert not monitoring_engine.running