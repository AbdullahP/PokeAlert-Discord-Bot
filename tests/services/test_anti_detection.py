"""
Tests for the anti-detection and stealth measures.
"""
import pytest
import asyncio
import re
from unittest.mock import MagicMock, AsyncMock, patch
import aiohttp

from src.services.anti_detection import AntiDetectionService
from src.services.user_agent_rotator import UserAgentRotator


class TestAntiDetectionService:
    """Test suite for the anti-detection service."""
    
    @pytest.fixture
    def anti_detection_service(self):
        """Create an anti-detection service for testing."""
        service = AntiDetectionService()
        service.user_agent_rotator = UserAgentRotator()
        return service
    
    @pytest.mark.asyncio
    async def test_user_agent_rotation(self, anti_detection_service):
        """Test user agent rotation."""
        # Get multiple user agents
        user_agents = [anti_detection_service.get_random_user_agent() for _ in range(10)]
        
        # Verify we got valid user agents
        for ua in user_agents:
            assert ua is not None
            assert isinstance(ua, str)
            assert len(ua) > 10
        
        # Verify we got at least 3 different user agents (rotation is working)
        unique_agents = set(user_agents)
        assert len(unique_agents) >= 3
    
    @pytest.mark.asyncio
    async def test_realistic_headers(self, anti_detection_service):
        """Test generation of realistic browser headers."""
        headers = anti_detection_service.get_realistic_headers()
        
        # Verify essential headers are present
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Accept-Language" in headers
        assert "Accept-Encoding" in headers
        assert "Connection" in headers
        assert "Referer" in headers
        
        # Verify header values are realistic
        assert "text/html" in headers["Accept"]
        assert "nl" in headers["Accept-Language"] or "en" in headers["Accept-Language"]
        assert "gzip" in headers["Accept-Encoding"]
    
    @pytest.mark.asyncio
    async def test_request_timing_randomization(self, anti_detection_service):
        """Test request timing randomization."""
        # Get multiple delay times
        delays = [anti_detection_service.get_random_delay() for _ in range(10)]
        
        # Verify delays are within expected range
        for delay in delays:
            assert 0.1 <= delay <= 2.0
        
        # Verify we got different delays (randomization is working)
        assert len(set(delays)) > 1
    
    @pytest.mark.asyncio
    async def test_cache_busting_parameters(self, anti_detection_service):
        """Test cache-busting URL parameters."""
        original_url = "https://www.bol.com/nl/nl/p/pokemon-scarlet-nintendo-switch/9300000096287/"
        
        # Get multiple cache-busted URLs
        urls = [anti_detection_service.add_cache_busting_parameters(original_url) for _ in range(5)]
        
        # Verify all URLs are different
        assert len(set(urls)) == 5
        
        # Verify all URLs contain the original URL as a prefix
        for url in urls:
            assert url.startswith(original_url)
            
        # Verify all URLs have a timestamp parameter
        for url in urls:
            assert re.search(r'[?&]_=\d+', url)
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self, anti_detection_service):
        """Test exponential backoff calculation."""
        # Test with different retry counts
        backoff_times = [
            anti_detection_service.calculate_backoff_time(0),
            anti_detection_service.calculate_backoff_time(1),
            anti_detection_service.calculate_backoff_time(2),
            anti_detection_service.calculate_backoff_time(3)
        ]
        
        # Verify backoff times increase exponentially
        for i in range(1, len(backoff_times)):
            assert backoff_times[i] > backoff_times[i-1]
        
        # Verify backoff is capped at maximum
        max_backoff = anti_detection_service.calculate_backoff_time(10)
        assert max_backoff <= anti_detection_service.max_backoff
    
    @pytest.mark.asyncio
    async def test_apply_anti_detection_to_session(self, anti_detection_service):
        """Test applying anti-detection measures to an HTTP session."""
        # Create a mock session
        mock_session = MagicMock()
        mock_session.headers = {}
        
        # Apply anti-detection measures
        anti_detection_service.apply_anti_detection_to_session(mock_session)
        
        # Verify headers were set
        assert "User-Agent" in mock_session.headers
        assert "Accept" in mock_session.headers
        assert "Accept-Language" in mock_session.headers
        assert "Accept-Encoding" in mock_session.headers
        assert "Connection" in mock_session.headers
        assert "Referer" in mock_session.headers
    
    @pytest.mark.asyncio
    async def test_handle_rate_limiting(self, anti_detection_service):
        """Test handling of rate limiting."""
        # Mock sleep function to avoid actual delays
        with patch('asyncio.sleep', AsyncMock()) as mock_sleep:
            # Test with a 429 response
            response = MagicMock()
            response.status = 429
            
            # Handle rate limiting
            await anti_detection_service.handle_rate_limiting(response, "https://www.bol.com/test", 2)
            
            # Verify sleep was called with backoff time
            mock_sleep.assert_called_once()
            backoff_time = mock_sleep.call_args[0][0]
            assert backoff_time > 0
    
    @pytest.mark.asyncio
    async def test_retry_request_with_backoff(self, anti_detection_service):
        """Test retrying requests with backoff."""
        # Create a mock client session
        mock_session = AsyncMock()
        
        # Mock responses - first fails with 429, second succeeds with 200
        mock_response1 = AsyncMock()
        mock_response1.status = 429
        
        mock_response2 = AsyncMock()
        mock_response2.status = 200
        mock_response2.text = AsyncMock(return_value="<html>Success</html>")
        
        # Configure mock session to return the responses in sequence
        mock_session.__aenter__.return_value.get = AsyncMock(side_effect=[mock_response1, mock_response2])
        
        # Mock sleep function to avoid actual delays
        with patch('asyncio.sleep', AsyncMock()), \
             patch('aiohttp.ClientSession', return_value=mock_session):
            
            # Perform request with retry
            url = "https://www.bol.com/test"
            response = await anti_detection_service.fetch_with_retry(url, max_retries=3)
            
            # Verify we got the successful response
            assert response.status == 200
            assert await response.text() == "<html>Success</html>"
            
            # Verify get was called twice (initial + 1 retry)
            assert mock_session.__aenter__.return_value.get.call_count == 2
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, anti_detection_service):
        """Test behavior when max retries are exceeded."""
        # Create a mock client session
        mock_session = AsyncMock()
        
        # Mock responses - all fail with 429
        mock_response = AsyncMock()
        mock_response.status = 429
        
        # Configure mock session to always return 429
        mock_session.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        
        # Mock sleep function to avoid actual delays
        with patch('asyncio.sleep', AsyncMock()), \
             patch('aiohttp.ClientSession', return_value=mock_session):
            
            # Perform request with retry
            url = "https://www.bol.com/test"
            
            # Should raise an exception after max retries
            with pytest.raises(Exception) as excinfo:
                await anti_detection_service.fetch_with_retry(url, max_retries=3)
            
            # Verify the exception message
            assert "Max retries exceeded" in str(excinfo.value)
            
            # Verify get was called the expected number of times (initial + 3 retries)
            assert mock_session.__aenter__.return_value.get.call_count == 4
"""