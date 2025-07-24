"""
Comprehensive tests for the monitoring engine including performance testing.
"""
import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from src.services.monitoring_engine import MonitoringEngine
from src.models.product_data import ProductConfig, ProductData, StockStatus, URLType


class TestMonitoringEngineComprehensive:
    """Comprehensive test suite for the monitoring engine."""
    
    @pytest.mark.asyncio
    async def test_monitor_product_performance(self, monitoring_engine, mock_http_client, performance_monitor):
        """Test monitoring product performance."""
        # Configure mock response with product data
        html_content = """
        <html>
            <head><title>Pokemon Scarlet - bol.com</title></head>
            <body>
                <div class="product-title">Pokemon Scarlet</div>
                <div class="product-price">€59.99</div>
                <div class="product-image"><img src="https://example.com/image.jpg"></div>
                <div class="product-stock">Op voorraad</div>
                <div class="product-delivery">Bezorging binnen 24 uur</div>
            </body>
        </html>
        """
        mock_http_client.get.return_value.text = AsyncMock(return_value=html_content)
        
        # Create product config
        product_config = ProductConfig(
            product_id="test-product-123",
            url="https://bol.com/product/123",
            url_type=URLType.PRODUCT.value,
            channel_id=123456789,
            guild_id=987654321,
            monitoring_interval=60,
            role_mentions=[],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Monitor product
        start_time = time.time()
        product_data = await monitoring_engine.monitor_product(product_config.url)
        end_time = time.time()
        
        # Verify product data
        assert product_data is not None
        assert product_data.title == "Pokemon Scarlet"
        assert product_data.price == "€59.99"
        assert product_data.stock_status == StockStatus.IN_STOCK.value
        
        # Verify performance metrics were recorded
        assert len(performance_monitor.metrics.response_times) == 1
        
        # Verify monitoring duration is reasonable (less than 1 second for a mock)
        duration_ms = (end_time - start_time) * 1000
        assert duration_ms < 1000
    
    @pytest.mark.asyncio
    async def test_concurrent_monitoring_performance(self, monitoring_engine, mock_http_client, performance_monitor):
        """Test performance of concurrent monitoring."""
        # Configure mock response with product data
        html_content = """
        <html>
            <head><title>Pokemon Product - bol.com</title></head>
            <body>
                <div class="product-title">Pokemon Product</div>
                <div class="product-price">€59.99</div>
                <div class="product-image"><img src="https://example.com/image.jpg"></div>
                <div class="product-stock">Op voorraad</div>
                <div class="product-delivery">Bezorging binnen 24 uur</div>
            </body>
        </html>
        """
        mock_http_client.get.return_value.text = AsyncMock(return_value=html_content)
        
        # Create multiple product configs
        product_configs = []
        for i in range(10):  # Monitor 10 products concurrently
            product_configs.append(
                ProductConfig(
                    product_id=f"test-product-{i}",
                    url=f"https://bol.com/product/{i}",
                    url_type=URLType.PRODUCT.value,
                    channel_id=123456789,
                    guild_id=987654321,
                    monitoring_interval=60,
                    role_mentions=[],
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
        
        # Monitor products concurrently
        start_time = time.time()
        tasks = [monitoring_engine.monitor_product(config.url) for config in product_configs]
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Verify all products were monitored
        assert len(results) == 10
        for product_data in results:
            assert product_data is not None
            assert product_data.title == "Pokemon Product"
            assert product_data.stock_status == StockStatus.IN_STOCK.value
        
        # Verify performance metrics were recorded
        assert len(performance_monitor.metrics.response_times) == 10
        
        # Verify total duration is reasonable (should be much less than monitoring 10 products sequentially)
        total_duration_ms = (end_time - start_time) * 1000
        assert total_duration_ms < 1000  # Should be fast with mocks
    
    @pytest.mark.asyncio
    async def test_detect_stock_changes(self, monitoring_engine, performance_monitor):
        """Test stock change detection performance."""
        # Create previous product data (out of stock)
        previous_data = ProductData(
            title="Pokemon Scarlet",
            price="€59.99",
            original_price="€69.99",
            image_url="https://example.com/image.jpg",
            product_url="https://bol.com/product/123",
            uncached_url="https://bol.com/product/123?t=12345",
            stock_status=StockStatus.OUT_OF_STOCK.value,
            stock_level="Uitverkocht",
            website="bol.com",
            delivery_info="Niet leverbaar",
            sold_by_bol=True,
            last_checked=datetime.utcnow(),
            product_id="test-product-123"
        )
        
        # Create current product data (in stock)
        current_data = ProductData(
            title="Pokemon Scarlet",
            price="€59.99",
            original_price="€69.99",
            image_url="https://example.com/image.jpg",
            product_url="https://bol.com/product/123",
            uncached_url="https://bol.com/product/123?t=12345",
            stock_status=StockStatus.IN_STOCK.value,
            stock_level="Op voorraad",
            website="bol.com",
            delivery_info="Bezorging binnen 24 uur",
            sold_by_bol=True,
            last_checked=datetime.utcnow(),
            product_id="test-product-123"
        )
        
        # Mock the get_product_status method
        monitoring_engine.status_repo = AsyncMock()
        monitoring_engine.status_repo.get_product_status = AsyncMock(return_value=previous_data)
        
        # Detect stock changes
        start_time = time.time()
        changes = await monitoring_engine.detect_stock_changes([current_data])
        end_time = time.time()
        
        # Verify stock change was detected
        assert len(changes) == 1
        assert changes[0].product_id == "test-product-123"
        assert changes[0].previous_status == StockStatus.OUT_OF_STOCK.value
        assert changes[0].current_status == StockStatus.IN_STOCK.value
        
        # Verify detection duration is reasonable
        duration_ms = (end_time - start_time) * 1000
        assert duration_ms < 100  # Should be very fast
    
    @pytest.mark.asyncio
    async def test_monitoring_with_rate_limiting(self, monitoring_engine, mock_http_client, performance_monitor):
        """Test monitoring with rate limiting."""
        # Configure mock response with product data
        html_content = """
        <html>
            <head><title>Pokemon Product - bol.com</title></head>
            <body>
                <div class="product-title">Pokemon Product</div>
                <div class="product-price">€59.99</div>
                <div class="product-image"><img src="https://example.com/image.jpg"></div>
                <div class="product-stock">Op voorraad</div>
                <div class="product-delivery">Bezorging binnen 24 uur</div>
            </body>
        </html>
        """
        mock_http_client.get.return_value.text = AsyncMock(return_value=html_content)
        
        # Create product configs
        product_configs = []
        for i in range(5):
            product_configs.append(
                ProductConfig(
                    product_id=f"test-product-{i}",
                    url=f"https://bol.com/product/{i}",
                    url_type=URLType.PRODUCT.value,
                    channel_id=123456789,
                    guild_id=987654321,
                    monitoring_interval=60,
                    role_mentions=[],
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
        
        # Set rate limiting configuration
        monitoring_engine.rate_limit_delay = 0.1  # 100ms between requests
        
        # Monitor products with rate limiting
        start_time = time.time()
        await monitoring_engine.monitor_products(product_configs)
        end_time = time.time()
        
        # Verify rate limiting was applied
        total_duration_ms = (end_time - start_time) * 1000
        
        # With 5 products and 100ms delay, should take at least 400ms (4 delays)
        assert total_duration_ms >= 400
        
        # Verify all products were monitored
        assert mock_http_client.get.call_count == 5
    
    @pytest.mark.asyncio
    async def test_monitoring_with_error_handling(self, monitoring_engine, mock_http_client):
        """Test monitoring with error handling."""
        # Configure mock to raise an exception on the third request
        original_get = mock_http_client.get
        call_count = 0
        
        async def mock_get_with_error(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise Exception("Simulated network error")
            return await original_get(*args, **kwargs)
        
        mock_http_client.get = mock_get_with_error
        
        # Configure successful response for other requests
        html_content = """
        <html>
            <head><title>Pokemon Product - bol.com</title></head>
            <body>
                <div class="product-title">Pokemon Product</div>
                <div class="product-price">€59.99</div>
                <div class="product-image"><img src="https://example.com/image.jpg"></div>
                <div class="product-stock">Op voorraad</div>
                <div class="product-delivery">Bezorging binnen 24 uur</div>
            </body>
        </html>
        """
        mock_http_client.get.return_value.text = AsyncMock(return_value=html_content)
        
        # Create product configs
        product_configs = []
        for i in range(5):
            product_configs.append(
                ProductConfig(
                    product_id=f"test-product-{i}",
                    url=f"https://bol.com/product/{i}",
                    url_type=URLType.PRODUCT.value,
                    channel_id=123456789,
                    guild_id=987654321,
                    monitoring_interval=60,
                    role_mentions=[],
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
        
        # Mock error handler
        monitoring_engine.error_handler = AsyncMock()
        
        # Monitor products with one error
        results = await monitoring_engine.monitor_products(product_configs)
        
        # Verify 4 out of 5 products were successfully monitored
        assert len([r for r in results if r is not None]) == 4
        assert len([r for r in results if r is None]) == 1
        
        # Verify error was handled
        assert monitoring_engine.error_handler.handle_network_error.call_count == 1
"""