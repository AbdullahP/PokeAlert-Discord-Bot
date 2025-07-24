"""
Tests for the UserAgentRotator class.
"""
import pytest
from src.services.user_agent_rotator import UserAgentRotator


class TestUserAgentRotator:
    """Test the user agent rotator implementation."""
    
    def test_get_random_user_agent(self):
        """Test that rotator returns a user agent."""
        rotator = UserAgentRotator()
        user_agent = rotator.get_random_user_agent()
        
        assert isinstance(user_agent, str)
        assert len(user_agent) > 0
    
    def test_get_browser_type(self):
        """Test browser type detection from user agent."""
        rotator = UserAgentRotator()
        
        chrome_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        firefox_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
        safari_ua = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
        edge_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
        
        assert rotator.get_browser_type(chrome_ua) == 'chrome'
        assert rotator.get_browser_type(firefox_ua) == 'firefox'
        assert rotator.get_browser_type(safari_ua) == 'safari'
        assert rotator.get_browser_type(edge_ua) == 'edge'
    
    def test_get_realistic_headers(self):
        """Test that realistic headers are generated."""
        rotator = UserAgentRotator()
        user_agent = rotator.get_random_user_agent()
        headers = rotator.get_realistic_headers(user_agent)
        
        assert isinstance(headers, dict)
        assert headers['User-Agent'] == user_agent
        assert 'Accept' in headers
        assert 'Accept-Language' in headers
        
        # Test browser-specific headers
        chrome_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        chrome_headers = rotator.get_realistic_headers(chrome_ua)
        assert 'sec-ch-ua' in chrome_headers
        
        firefox_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
        firefox_headers = rotator.get_realistic_headers(firefox_ua)
        assert 'sec-fetch-dest' in firefox_headers
        
        # Test platform-specific headers
        mac_ua = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        mac_headers = rotator.get_realistic_headers(mac_ua)
        if 'sec-ch-ua-platform' in mac_headers:
            assert mac_headers['sec-ch-ua-platform'] == '"macOS"'
        
        mobile_ua = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1'
        mobile_headers = rotator.get_realistic_headers(mobile_ua)
        if 'sec-ch-ua-mobile' in mobile_headers:
            assert mobile_headers['sec-ch-ua-mobile'] == '?1'