"""
Tests for the HTTP client with anti-detection and performance optimizations.
"""
import pytest
import asyncio
import aiohttp
import time
from unittest.mock import patch, MagicMock, AsyncMock

from src.services.http_client import HttpClient
from src.services.anti_detection import AntiDetectionManager, RetryConfig


@pytest.fixture
def anti_detection_manager():
    """Create a mock anti-detection manager."""
    manager = MagicMock(spec=AntiDetectionManager)
    manager.request_throttler = MagicMock()
    manager.request_throttler.get_domain_from_url.return_value = "example.com"
    manager.request_throttler.throttle = AsyncMock()
    manager.request_throttler.default_rps = 2.0
    manager.request_throttler.default_burst = 5
    manager.network_analyzer = MagicMock()
    manager.network_analyzer.get_optimal_connection_params.return_value = {}
    manager.network_analyzer.get_optimal_timeout.return_value = 30.0
    manager.network_analyzer.record_latency = MagicMock()
    manager.prepare_request = AsyncMock(return_value=({}, None))
    manager.update_from_response = MagicMock()
    return manager


@pytest.fixture
def retry_config():
    """Create a retry configuration."""
    return RetryConfig(
        max_retries=2,
        base_delay=0.1,
        max_delay=0.5,
        exponential_base=2.0,
        jitter=False
    )


@pytest.fixture
def http_client(anti_detection_manager, retry_config):
    """Create an HTTP client with mocked dependencies."""
    client = HttpClient(anti_detection_manager, retry_config)
    client.min_delay = 0.01  # Short delay for tests
    client.max_delay = 0.02  # Short delay for tests
    return client


class TestHttpClient:
    """Test the HTTP client implementation."""
    
    @pytest.mark.asyncio
    async def test_get_session(self, http_client):
        """Test that session is created with correct parameters."""
        with patch('aiohttp.TCPConnector') as mock_connector, \
             patch('aiohttp.ClientSession') as mock_session:
            
            await http_client.get_session()
            
            # Verify connector was created with correct parameters
            mock_connector.assert_called_once()
            connector_args = mock_connector.call_args[1]
            assert connector_args['limit'] == http_client.connection_limit
            assert connector_args['limit_per_host'] == http_client.connection_limit_per_host
            assert connector_args['ttl_dns_cache'] == http_client.dns_cache_ttl
            assert connector_args['keepalive_timeout'] == http_client.keepalive_timeout
            assert connector_args['enable_cleanup_closed'] is True
            assert connector_args['use_dns_cache'] is True
            
            # Verify session was created with correct parameters
            mock_session.assert_called_once()
            session_kwargs = mock_session.call_args[1]
            assert 'timeout' in session_kwargs
            assert 'headers' in session_kwargs
            assert session_kwargs['headers']['Connection'] == 'keep-alive'
    
    def test_add_cache_busting(self, http_client):
        """Test that cache busting parameters are added to URLs."""
        url = "https://www.example.com/product"
        busted_url = http_client.add_cache_busting(url)
        
        assert url in busted_url
        assert "_=" in busted_url
        
        # Test with existing query parameters
        url_with_query = "https://www.example.com/product?id=123"
        busted_url_with_query = http_client.add_cache_busting(url_with_query)
        
        assert url_with_query in busted_url_with_query
        assert "&_=" in busted_url_with_query
    
    @pytest.mark.asyncio
    async def test_fetch_success(self, http_client):
        """Test successful fetch with anti-detection measures."""
        url = "https://www.example.com/product"
        
        # Mock session response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<html>Test content</html>")
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        # Mock session get method
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        
        with patch.object(http_client, 'get_session', return_value=mock_session):
            content, status, headers = await http_client.fetch(url)
            
            # Verify content was returned
            assert content == "<html>Test content</html>"
            assert status == 200
            assert headers == {"Content-Type": "text/html"}
            
            # Verify anti-detection measures were applied
            http_client.anti_detection_manager.request_throttler.throttle.assert_called_once()
            http_client.anti_detection_manager.prepare_request.assert_called_once()
            http_client.anti_detection_manager.update_from_response.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fetch_retry_on_rate_limit(self, http_client):
        """Test retry behavior with rate limiting."""
        url = "https://www.example.com/product"
        
        # Mock responses for rate limiting then success
        mock_response_429 = AsyncMock()
        mock_response_429.status = 429
        mock_response_429.reason = "Too Many Requests"
        mock_response_429.headers = {}
        mock_response_429.cookies = {}
        mock_response_429.__aenter__ = AsyncMock(return_value=mock_response_429)
        mock_response_429.__aexit__ = AsyncMock(return_value=None)
        
        mock_response_200 = AsyncMock()
        mock_response_200.status = 200
        mock_response_200.text = AsyncMock(return_value="<html>Success</html>")
        mock_response_200.headers = {"Content-Type": "text/html"}
        mock_response_200.cookies = {}
        mock_response_200.__aenter__ = AsyncMock(return_value=mock_response_200)
        mock_response_200.__aexit__ = AsyncMock(return_value=None)
        
        # Mock session with rate limit then success
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=[mock_response_429, mock_response_200])
        
        with patch.object(http_client, 'get_session', return_value=mock_session), \
             patch('asyncio.sleep', AsyncMock()):
            
            content, status, headers = await http_client.fetch(url)
            
            # Verify content was returned after retry
            assert content == "<html>Success</html>"
            assert status == 200
            
            # Verify session.get was called twice
            assert mock_session.get.call_count == 2
            
            # Verify rate limit handling
            http_client.anti_detection_manager.request_throttler.set_domain_limit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fetch_retry_on_server_error(self, http_client):
        """Test retry behavior with server errors."""
        url = "https://www.example.com/product"
        
        # Mock responses for server error then success
        mock_response_503 = AsyncMock()
        mock_response_503.status = 503
        mock_response_503.reason = "Service Unavailable"
        mock_response_503.headers = {}
        mock_response_503.cookies = {}
        mock_response_503.__aenter__ = AsyncMock(return_value=mock_response_503)
        mock_response_503.__aexit__ = AsyncMock(return_value=None)
        
        mock_response_200 = AsyncMock()
        mock_response_200.status = 200
        mock_response_200.text = AsyncMock(return_value="<html>Success</html>")
        mock_response_200.headers = {"Content-Type": "text/html"}
        mock_response_200.cookies = {}
        mock_response_200.__aenter__ = AsyncMock(return_value=mock_response_200)
        mock_response_200.__aexit__ = AsyncMock(return_value=None)
        
        # Mock session with server error then success
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=[mock_response_503, mock_response_200])
        
        with patch.object(http_client, 'get_session', return_value=mock_session), \
             patch('asyncio.sleep', AsyncMock()):
            
            content, status, headers = await http_client.fetch(url)
            
            # Verify content was returned after retry
            assert content == "<html>Success</html>"
            assert status == 200
            
            # Verify session.get was called twice
            assert mock_session.get.call_count == 2
    
    @pytest.mark.asyncio
    async def test_fetch_retry_on_timeout(self, http_client):
        """Test retry behavior with timeouts."""
        url = "https://www.example.com/product"
        
        # Mock session with timeout then success
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=[
            asyncio.TimeoutError(),  # First call: timeout
            AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
                status=200,
                text=AsyncMock(return_value="<html>Success</html>"),
                headers={"Content-Type": "text/html"},
                cookies={}
            )))
        ])
        
        with patch.object(http_client, 'get_session', return_value=mock_session), \
             patch('asyncio.sleep', AsyncMock()):
            
            content, status, headers = await http_client.fetch(url)
            
            # Verify content was returned after retry
            assert content == "<html>Success</html>"
            assert status == 200
            
            # Verify session.get was called twice
            assert mock_session.get.call_count == 2
    
    @pytest.mark.asyncio
    async def test_fetch_max_retries_exceeded(self, http_client):
        """Test behavior when max retries are exceeded."""
        url = "https://www.example.com/product"
        
        # Mock session with persistent failures
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=[
            asyncio.TimeoutError(),  # First attempt
            asyncio.TimeoutError(),  # Second attempt
            asyncio.TimeoutError()   # Third attempt (exceeds max_retries=2)
        ])
        
        with patch.object(http_client, 'get_session', return_value=mock_session), \
             patch('asyncio.sleep', AsyncMock()):
            
            content, status, headers = await http_client.fetch(url)
            
            # Verify failure response
            assert content is None
            assert status == 0
            assert headers == {}
            
            # Verify session.get was called for each retry attempt
            assert mock_session.get.call_count == 3  # Initial + 2 retries
    
    @pytest.mark.asyncio
    async def test_close(self, http_client):
        """Test closing the HTTP client session."""
        mock_session = AsyncMock()
        mock_session.closed = False
        http_client.session = mock_session
        
        await http_client.close()
        
        # Verify session was closed
        mock_session.close.assert_called_once()
        assert http_client.session is None