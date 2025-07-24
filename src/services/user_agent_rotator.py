"""
User agent rotation and browser fingerprinting for anti-detection.
"""
import random
from typing import Dict, List


class UserAgentRotator:
    """Advanced user agent rotation with browser fingerprinting."""
    
    def __init__(self):
        # More comprehensive user agent list with recent versions
        self.user_agents = [
            # Chrome on Windows
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            
            # Chrome on macOS
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            
            # Firefox on Windows
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
            
            # Firefox on macOS
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
            
            # Safari on macOS
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15',
            
            # Edge on Windows
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
            
            # Mobile Chrome
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/120.0.6099.119 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            
            # Mobile Safari
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
        ]
        
        # Browser-specific header templates
        self.browser_headers = {
            'chrome': {
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'none',
                'sec-fetch-user': '?1',
            },
            'firefox': {
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'none',
                'sec-fetch-user': '?1',
            },
            'safari': {
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'none',
            }
        }
        
        self.referers = [
            'https://www.google.nl/',
            'https://www.google.com/',
            'https://www.bing.com/',
            'https://duckduckgo.com/',
            'https://www.reddit.com/',
            'https://www.youtube.com/',
            'https://www.facebook.com/',
            'https://twitter.com/',
        ]
    
    def get_random_user_agent(self) -> str:
        """Get a random user agent."""
        return random.choice(self.user_agents)
    
    def get_browser_type(self, user_agent: str) -> str:
        """Detect browser type from user agent."""
        if 'Chrome' in user_agent and 'Edg' not in user_agent:
            return 'chrome'
        elif 'Firefox' in user_agent:
            return 'firefox'
        elif 'Safari' in user_agent and 'Chrome' not in user_agent:
            return 'safari'
        elif 'Edg' in user_agent:
            return 'edge'
        else:
            return 'chrome'  # Default to Chrome
    
    def get_realistic_headers(self, user_agent: str) -> Dict[str, str]:
        """Get realistic headers for the given user agent."""
        browser_type = self.get_browser_type(user_agent)
        
        # Base headers
        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
        
        # Add browser-specific headers
        if browser_type in self.browser_headers:
            headers.update(self.browser_headers[browser_type])
        
        # Randomize some header values
        if random.random() < 0.7:  # 70% chance to add DNT
            headers['DNT'] = '1'
        
        if random.random() < 0.8:  # 80% chance to add referer
            headers['Referer'] = random.choice(self.referers)
        
        # Adjust platform in sec-ch-ua-platform based on user agent
        if 'sec-ch-ua-platform' in headers:
            if 'Macintosh' in user_agent:
                headers['sec-ch-ua-platform'] = '"macOS"'
            elif 'Linux' in user_agent:
                headers['sec-ch-ua-platform'] = '"Linux"'
            elif 'Android' in user_agent:
                headers['sec-ch-ua-platform'] = '"Android"'
            elif 'iPhone' in user_agent or 'iPad' in user_agent:
                headers['sec-ch-ua-platform'] = '"iOS"'
        
        # Adjust mobile flag
        if 'sec-ch-ua-mobile' in headers:
            if 'Android' in user_agent or 'iPhone' in user_agent or 'iPad' in user_agent:
                headers['sec-ch-ua-mobile'] = '?1'
        
        return headers