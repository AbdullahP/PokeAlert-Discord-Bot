"""
Integration tests for anti-detection and performance optimizations.
"""
import pytest
import asyncio
import aiohttp
import time
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from src.services.monitoring_engine import MonitoringEngine
from src.services.anti_detection import AntiDetectionManager
from src.models.product_data import ProductData, ProductConfig, StockChange, StockStatus, URLType
from src.config.config_manager import ConfigManager


@pytest.fixture
def config_manager():
    """Create a config manager with test settings."""
    config = ConfigManager()
    config.set('monitoring.default_interval', 60)
    config.set('monitoring.min_interval', 30)
    config.set('monitoring.max_concurrent', 5)
    config.set('monitoring.request_timeout', 10)
    
    # Anti-detection settings
    config.set('monitoring.anti_detection.min_delay', 0.1)  # Short delay for tests
    config.set('monitoring.anti_detection.max_delay', 0.2)  # Short delay for tests
    config.set('monitoring.anti_detection.use_cache_busting', True)
    config.set('monitoring.anti_detection.use_proxies', False)
    config.set('monitoring.anti_detection.browser_distribution', {
        'chrome': 0.65,
        'firefox': 0.20,
        'safari': 0.10,
        'edge': 0.05
    })
    config.set('monitoring.anti_detection.fingerprint_rotation_interval', 60)  # Short interval for tests
    
    # Retry settings
    config.set('monitoring.retry.max_retries', 2)
    config.set('monitoring.retry.base_delay', 0.1)
    config.set('monitoring.retry.max_delay', 0.5)
    config.set('monitoring.retry.jitter', True)
    
    # Rate limit settings
    config.set('monitoring.rate_limit.requests_per_second', 5.0)  # Higher for tests
    config.set('monitoring.rate_limit.burst_size', 3)
    
    # Connection pool settings
    config.set('monitoring.connection_pool.limit', 10)
    config.set('monitoring.connection_pool.limit_per_host', 5)
    config.set('monitoring.connection_pool.dns_cache_ttl', 60)
    config.set('monitoring.connection_pool.keepalive_timeout', 15)
    
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


class TestAntiDetectionIntegration:
    """Integration tests for anti-detection measures."""
    
    @pytest.mark.asyncio
    async def test_fetch_with_anti_detection(self, monitoring_engine):
        """Test fetching a page with anti-detection measures."""
        url = "https://www.bol.com/nl/p/pokemon-scarlet-nintendo-switch/9300000096287848/"
        
        # Mock session response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<html><body>Test content</body></html>")
        mock_response.cookies = {}
        
        # Mock session get method
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        
        with patch.object(monitoring_engine, '_get_session', return_value=mock_session):
            html_content = await monitoring_engine._fetch_page(url)
            
            # Verify content was returned
            assert html_content == "<html><body>Test content</body></html>"
            
            # Verify session.get was called with anti-detection measures
            mock_session.get.assert_called_once()
            call_args = mock_session.get.call_args[1]
            
            # Check headers were included
            assert 'headers' in call_args
            headers = call_args['headers']
            assert 'User-Agent' in headers
            assert 'Accept' in headers
            assert 'Accept-Language' in headers
            
            # Check cache busting was applied
            assert '_=' in mock_session.get.call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_retry_with_rate_limiting(self, monitoring_engine):
        """Test retry behavior with rate limiting."""
        url = "https://www.bol.com/nl/p/pokemon-scarlet-nintendo-switch/9300000096287848/"
        
        # Mock responses for rate limiting then success
        mock_response_429 = AsyncMock()
        mock_response_429.status = 429
        mock_response_429.reason = "Too Many Requests"
        mock_response_429.cookies = {}
        
        mock_response_200 = AsyncMock()
        mock_response_200.status = 200
        mock_response_200.text = AsyncMock(return_value="<html><body>Success</body></html>")
        mock_response_200.cookies = {}
        
        # Mock session with rate limit then success
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=[
            mock_response_429,  # First call: rate limited
            mock_response_200   # Second call: success
        ])
        
        with patch.object(monitoring_engine, '_get_session', return_value=mock_session), \
             patch.object(monitoring_engine, '_extract_product_id_from_url', return_value="bol-9300000096287848"), \
             patch.object(monitoring_engine, '_log_metrics', AsyncMock()):
            
            html_content = await monitoring_engine._fetch_page(url)
            
            # Verify content was returned after retry
            assert html_content == "<html><body>Success</body></html>"
            
            # Verify session.get was called twice
            assert mock_session.get.call_count == 2
            
            # Verify metrics were logged
            monitoring_engine._log_metrics.assert_called_once()
            call_args = monitoring_engine._log_metrics.call_args[0]
            assert call_args[0] == "bol-9300000096287848"  # product_id
            assert call_args[2] is True  # success
    
    @pytest.mark.asyncio
    async def test_connection_pooling(self, monitoring_engine):
        """Test connection pooling configuration."""
        with patch('aiohttp.TCPConnector') as mock_connector, \
             patch('aiohttp.ClientSession') as mock_session:
            
            await monitoring_engine._get_session()
            
            # Verify connector was created with correct parameters
            mock_connector.assert_called_once()
            connector_args = mock_connector.call_args[1]
            
            # Check connection pooling parameters
            assert connector_args['limit'] == monitoring_engine.connection_limit
            assert connector_args['limit_per_host'] == monitoring_engine.connection_limit_per_host
            assert connector_args['ttl_dns_cache'] == monitoring_engine.dns_cache_ttl
            assert connector_args['keepalive_timeout'] == monitoring_engine.keepalive_timeout
            assert connector_args['enable_cleanup_closed'] is True
            assert connector_args['use_dns_cache'] is True
    
    @pytest.mark.asyncio
    async def test_anti_detection_manager_integration(self, monitoring_engine):
        """Test integration with anti-detection manager."""
        # Test that the anti-detection manager is properly initialized
        assert monitoring_engine.anti_detection_manager is not None
        
        # Test preparing a request
        url = "https://www.bol.com/nl/p/pokemon-scarlet-nintendo-switch/9300000096287848/"
        headers, proxy = await monitoring_engine.anti_detection_manager.prepare_request(url)
        
        # Verify headers
        assert isinstance(headers, dict)
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Accept-Language" in headers
        
        # Test browser fingerprint generation
        fingerprint = monitoring_engine.anti_detection_manager.get_fingerprint()
        assert "user_agent" in fingerprint
        assert "accept_language" in fingerprint
        assert "resolution" in fingerprint
        
        # Test domain rate limiting
        domain = "www.bol.com"
        await monitoring_engine.anti_detection_manager.request_throttler.throttle(f"https://{domain}/test")
        
        # Test cookie management
        monitoring_engine.anti_detection_manager.cookie_manager.store_cookies(domain, {"session": "test123"})
        cookies = monitoring_engine.anti_detection_manager.cookie_manager.get_cookies(domain)
        assert cookies == {"session": "test123"}


class TestPerformanceOptimizations:
    """Tests for performance optimizations."""
    
    @pytest.mark.asyncio
    async def test_concurrent_monitoring(self, monitoring_engine):
        """Test concurrent monitoring of multiple products."""
        # Create test product URLs
        urls = [
            "https://www.bol.com/nl/p/pokemon-scarlet-nintendo-switch/9300000096287848/",
            "https://www.bol.com/nl/p/pokemon-violet-nintendo-switch/9300000096287849/",
            "https://www.bol.com/nl/p/pokemon-legends-arceus-nintendo-switch/9300000041782736/"
        ]
        
        # Mock fetch_page to return HTML content
        html_content = "<html><body><h1 data-test='title'>Pokemon Game</h1><span data-test='price'>€59.99</span></body></html>"
        
        with patch.object(monitoring_engine, '_fetch_page', AsyncMock(return_value=html_content)):
            # Monitor products concurrently
            tasks = [monitoring_engine.monitor_product(url) for url in urls]
            products = await asyncio.gather(*tasks)
            
            # Verify all products were monitored
            assert len(products) == 3
            assert all(isinstance(p, ProductData) for p in products)
            assert all(p.title == "Pokemon Game" for p in products)
            
            # Verify fetch_page was called for each URL
            assert monitoring_engine._fetch_page.call_count == 3
    
    @pytest.mark.asyncio
    async def test_wishlist_monitoring_performance(self, monitoring_engine):
        """Test performance of wishlist monitoring."""
        wishlist_url = "https://www.bol.com/nl/wl/12345/"
        
        # Mock wishlist HTML with multiple products
        wishlist_html = """
        <html><body>
            <a class="product-title" href="/nl/p/product1/9300000096287848/">Product 1</a>
            <a class="product-title" href="/nl/p/product2/9300000096287849/">Product 2</a>
            <a class="product-title" href="/nl/p/product3/9300000041782736/">Product 3</a>
        </body></html>
        """
        
        # Mock product HTML
        product_html = "<html><body><h1 data-test='title'>Pokemon Game</h1><span data-test='price'>€59.99</span></body></html>"
        
        with patch.object(monitoring_engine, '_fetch_page', AsyncMock(side_effect=[
                wishlist_html,  # First call for wishlist
                product_html,   # Product 1
                product_html,   # Product 2
                product_html    # Product 3
            ])), \
             patch.object(monitoring_engine, '_parse_wishlist_page', AsyncMock(return_value=[
                "https://www.bol.com/nl/p/product1/9300000096287848/",
                "https://www.bol.com/nl/p/product2/9300000096287849/",
                "https://www.bol.com/nl/p/product3/9300000041782736/"
            ])):
            
            # Monitor wishlist
            start_time = time.time()
            products = await monitoring_engine.monitor_wishlist(wishlist_url)
            duration = time.time() - start_time
            
            # Verify products were monitored
            assert len(products) == 3
            
            # Verify monitoring was done concurrently (should be faster than sequential)
            # This is a rough check since test environment timing can vary
            assert duration < 1.0  # Should be very quick in test environment with mocks
            
            # Verify fetch_page was called for wishlist and each product
            assert monitoring_engine._fetch_page.call_count == 4
"""