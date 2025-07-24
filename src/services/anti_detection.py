"""
Anti-detection and performance optimization utilities for the monitoring engine.

This module provides comprehensive anti-detection measures and performance optimizations
for the monitoring engine, including user-agent rotation, connection pooling,
exponential backoff, and rate limiting.
"""
import random
import time
import logging
import asyncio
from typing import Dict, List, Optional, Tuple, Any
import aiohttp
import platform
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class RetryConfig:
    """Configuration for retry mechanisms."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_second: float = 2.0
    burst_size: int = 5
    window_size: int = 60


class RateLimiter:
    """Token bucket rate limiter implementation."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.tokens = config.burst_size
        self.last_update = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self.lock:
            now = time.time()
            
            # Add tokens based on time elapsed
            time_passed = now - self.last_update
            tokens_to_add = time_passed * self.config.requests_per_second
            self.tokens = min(self.config.burst_size, self.tokens + tokens_to_add)
            self.last_update = now
            
            # If no tokens available, wait
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.config.requests_per_second
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1


class ExponentialBackoff:
    """Exponential backoff implementation with jitter."""
    
    def __init__(self, config: RetryConfig):
        self.config = config
        self.attempt = 0
    
    def reset(self) -> None:
        """Reset the backoff counter."""
        self.attempt = 0
    
    def get_delay(self) -> float:
        """Get the delay for the current attempt."""
        if self.attempt >= self.config.max_retries:
            return self.config.max_delay
        
        # Calculate exponential delay
        delay = self.config.base_delay * (self.config.exponential_base ** self.attempt)
        delay = min(delay, self.config.max_delay)
        
        # Add jitter to prevent thundering herd
        if self.config.jitter:
            jitter = random.uniform(0, delay * 0.1)
            delay += jitter
        
        self.attempt += 1
        return delay


@dataclass
class ProxyConfig:
    """Configuration for proxy rotation."""
    enabled: bool = False
    proxies: List[str] = None
    max_consecutive_uses: int = 5
    rotation_interval: int = 300  # seconds


class ProxyRotator:
    """Proxy rotation implementation for anti-detection."""
    
    def __init__(self, config: ProxyConfig):
        self.config = config
        self.current_proxy_index = 0
        self.proxy_use_count = 0
        self.last_rotation = time.time()
        self.proxies = config.proxies or []
        
    def get_current_proxy(self) -> Optional[str]:
        """Get the current proxy from the rotation."""
        if not self.config.enabled or not self.proxies:
            return None
            
        # Check if we need to rotate based on use count or time
        current_time = time.time()
        if (self.proxy_use_count >= self.config.max_consecutive_uses or
                current_time - self.last_rotation >= self.config.rotation_interval):
            self._rotate_proxy()
            
        self.proxy_use_count += 1
        return self.proxies[self.current_proxy_index] if self.proxies else None
        
    def _rotate_proxy(self) -> None:
        """Rotate to the next proxy in the list."""
        if not self.proxies:
            return
            
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        self.proxy_use_count = 0
        self.last_rotation = time.time()
        logger.debug(f"Rotated to proxy #{self.current_proxy_index}")


class CookieManager:
    """Cookie management for maintaining realistic browser behavior."""
    
    def __init__(self):
        self.cookies_by_domain: Dict[str, Dict[str, str]] = {}
        self.last_cleared = datetime.now()
        self.clear_interval = timedelta(hours=4)  # Clear cookies every 4 hours
        
    def store_cookies(self, domain: str, cookies: Dict[str, str]) -> None:
        """Store cookies for a domain."""
        if domain not in self.cookies_by_domain:
            self.cookies_by_domain[domain] = {}
            
        self.cookies_by_domain[domain].update(cookies)
        
    def get_cookies(self, domain: str) -> Dict[str, str]:
        """Get stored cookies for a domain."""
        self._check_clear_cookies()
        return self.cookies_by_domain.get(domain, {})
        
    def _check_clear_cookies(self) -> None:
        """Periodically clear cookies to prevent tracking."""
        now = datetime.now()
        if now - self.last_cleared > self.clear_interval:
            self.cookies_by_domain = {}
            self.last_cleared = now
            logger.debug("Cleared cookie store")


class BrowserFingerprintGenerator:
    """Generate realistic browser fingerprints to avoid detection."""
    
    def __init__(self):
        self.os_platforms = [
            # Windows platforms
            "Windows NT 10.0; Win64; x64",
            "Windows NT 10.0; WOW64",
            "Windows NT 11.0; Win64; x64",  # Future-proofing
            "Windows NT 10.0; Win64; x64; rv:109.0",
            # macOS platforms
            "Macintosh; Intel Mac OS X 10_15_7",
            "Macintosh; Intel Mac OS X 11_2_3",
            "Macintosh; Intel Mac OS X 12_6_0",
            "Macintosh; Intel Mac OS X 13_1_0",
            # Linux platforms
            "X11; Linux x86_64",
            "X11; Ubuntu; Linux x86_64",
            "X11; Fedora; Linux x86_64",
            # Mobile platforms (for variety)
            "iPhone; CPU iPhone OS 16_5 like Mac OS X",
            "iPad; CPU OS 16_5 like Mac OS X",
            "Linux; Android 13; SM-S908B"
        ]
        
        self.browser_versions = {
            "chrome": ["120.0.0.0", "119.0.0.0", "118.0.0.0", "117.0.0.0", "121.0.0.0", "122.0.0.0"],
            "firefox": ["121.0", "120.0", "119.0", "118.0", "122.0", "123.0"],
            "safari": ["17.1", "16.6", "15.6", "14.1", "17.2", "17.3"],
            "edge": ["120.0.0.0", "119.0.0.0", "118.0.0.0", "121.0.0.0", "122.0.0.0"],
            "opera": ["106.0.0.0", "105.0.0.0", "104.0.0.0"],
            "samsung": ["22.0.0.0", "21.0.0.0", "20.0.0.0"]
        }
        
        self.languages = [
            "en-US,en;q=0.9",
            "en-GB,en;q=0.9",
            "nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7",
            "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
            "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
            "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
            "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        ]
        
        self.color_depths = ["24", "30", "48", "32", "16"]
        self.screen_resolutions = [
            # Desktop resolutions
            "1920x1080", "2560x1440", "1366x768", 
            "1440x900", "1536x864", "3840x2160",
            "1680x1050", "1280x720", "1600x900",
            "3440x1440", "2560x1080", "1920x1200",
            # Mobile resolutions
            "390x844", "414x896", "375x812",
            "360x780", "412x915", "360x800"
        ]
        
        # Additional fingerprinting parameters
        self.fonts = [
            "Arial", "Helvetica", "Times New Roman", "Times", "Courier New", 
            "Courier", "Verdana", "Georgia", "Palatino", "Garamond", "Bookman", 
            "Comic Sans MS", "Trebuchet MS", "Arial Black", "Impact", "Tahoma"
        ]
        
        self.plugins = [
            "PDF Viewer", "Chrome PDF Viewer", "Chromium PDF Viewer", 
            "Microsoft Edge PDF Viewer", "WebKit built-in PDF", 
            "Native Client"
        ]
        
    def generate_fingerprint(self, browser_type: str = None) -> Dict[str, Any]:
        """Generate a realistic browser fingerprint."""
        if not browser_type:
            browser_type = random.choice(["chrome", "firefox", "safari", "edge", "opera", "samsung"])
            
        # Select appropriate OS platform based on browser type
        if browser_type == "safari":
            # Safari typically runs on Apple devices
            os_platforms = [p for p in self.os_platforms if "Mac" in p or "iPhone" in p or "iPad" in p]
            os_platform = random.choice(os_platforms) if os_platforms else random.choice(self.os_platforms)
        elif browser_type == "samsung":
            # Samsung browser runs on Android
            os_platforms = [p for p in self.os_platforms if "Android" in p]
            os_platform = random.choice(os_platforms) if os_platforms else "Linux; Android 13; SM-S908B"
        else:
            os_platform = random.choice(self.os_platforms)
            
        browser_version = random.choice(self.browser_versions.get(browser_type, ["120.0.0.0"]))
        
        # Determine if this is a mobile device
        is_mobile = any(mobile_indicator in os_platform for mobile_indicator in ["iPhone", "iPad", "Android"])
        
        # Select appropriate screen resolution based on device type
        if is_mobile:
            mobile_resolutions = [r for r in self.screen_resolutions if int(r.split('x')[0]) < 500]
            resolution = random.choice(mobile_resolutions) if mobile_resolutions else "390x844"
        else:
            desktop_resolutions = [r for r in self.screen_resolutions if int(r.split('x')[0]) >= 500]
            resolution = random.choice(desktop_resolutions) if desktop_resolutions else "1920x1080"
        
        # Generate a more comprehensive fingerprint
        fingerprint = {
            "user_agent": self._generate_user_agent(browser_type, os_platform, browser_version),
            "accept_language": random.choice(self.languages),
            "color_depth": random.choice(self.color_depths),
            "resolution": resolution,
            "timezone_offset": random.randint(-720, 720),  # -12 to +12 hours in minutes
            "session_storage": random.choice([True, True, True, False]),  # 75% chance of being true
            "local_storage": random.choice([True, True, True, False]),
            "indexed_db": random.choice([True, True, False]),
            "cpu_cores": random.randint(2, 16) if not is_mobile else random.randint(2, 8),
            "device_memory": random.choice([2, 4, 8, 16, 32]) if not is_mobile else random.choice([2, 4, 8]),
            "hardware_concurrency": random.randint(2, 16) if not is_mobile else random.randint(2, 8),
            "platform": self._get_platform_from_os(os_platform),
            "do_not_track": random.choice(["1", "0", None]),
            "plugins": random.sample(self.plugins, k=random.randint(0, min(5, len(self.plugins)))),
            "fonts": random.sample(self.fonts, k=random.randint(5, min(10, len(self.fonts)))),
            "canvas_fingerprint": self._generate_canvas_fingerprint(),
            "webgl_vendor": self._get_webgl_vendor(browser_type, os_platform),
            "webgl_renderer": self._get_webgl_renderer(browser_type, os_platform),
            "touch_support": is_mobile or random.random() < 0.3,  # Mobile or 30% chance for desktop
            "orientation_type": "portrait-primary" if is_mobile and random.random() < 0.7 else "landscape-primary"
        }
        
        return fingerprint
        
    def _generate_canvas_fingerprint(self) -> str:
        """Generate a random canvas fingerprint hash."""
        # Simulate a canvas fingerprint hash
        return ''.join(random.choices('0123456789abcdef', k=32))
        
    def _get_webgl_vendor(self, browser_type: str, os_platform: str) -> str:
        """Get a realistic WebGL vendor string based on platform."""
        if "Windows" in os_platform:
            return random.choice([
                "Google Inc. (NVIDIA)",
                "Google Inc. (Intel)",
                "Google Inc. (AMD)",
                "Microsoft",
                "Intel Inc."
            ])
        elif "Mac" in os_platform:
            return random.choice([
                "Apple Inc.",
                "Apple GPU",
                "Intel Inc."
            ])
        elif "Linux" in os_platform:
            return random.choice([
                "Mesa/X.org",
                "Mesa/X.org (NVIDIA)",
                "Mesa/X.org (Intel)",
                "Mesa/X.org (AMD)"
            ])
        elif "Android" in os_platform:
            return random.choice([
                "Google Inc.",
                "Qualcomm",
                "ARM",
                "Samsung"
            ])
        else:
            return "Unknown"
            
    def _get_webgl_renderer(self, browser_type: str, os_platform: str) -> str:
        """Get a realistic WebGL renderer string based on platform."""
        if "Windows" in os_platform:
            return random.choice([
                "ANGLE (NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0)",
                "ANGLE (Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)",
                "ANGLE (AMD Radeon RX 6800 XT Direct3D11 vs_5_0 ps_5_0)",
                "ANGLE (Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0)"
            ])
        elif "Mac" in os_platform:
            return random.choice([
                "Apple M1",
                "Apple M1 Pro",
                "Apple M1 Max",
                "Apple M2",
                "Intel Iris Pro",
                "AMD Radeon Pro 5500M"
            ])
        elif "Linux" in os_platform:
            return random.choice([
                "Mesa Intel(R) UHD Graphics 630 (CFL GT2)",
                "Mesa DRI Intel(R) HD Graphics 520 (SKL GT2)",
                "Mesa DRI NVIDIA GeForce GTX 1660",
                "Mesa DRI AMD Radeon RX 580"
            ])
        elif "Android" in os_platform:
            return random.choice([
                "Adreno (TM) 650",
                "Mali-G78 MP14",
                "PowerVR Rogue GE8320",
                "Exynos 2200"
            ])
        else:
            return "Unknown"
        
    def _generate_user_agent(self, browser_type: str, os_platform: str, browser_version: str) -> str:
        """Generate a realistic user agent string."""
        if browser_type == "chrome":
            return f"Mozilla/5.0 ({os_platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{browser_version} Safari/537.36"
        elif browser_type == "firefox":
            return f"Mozilla/5.0 ({os_platform}; rv:{browser_version}) Gecko/20100101 Firefox/{browser_version}"
        elif browser_type == "safari" and "Mac" in os_platform:
            return f"Mozilla/5.0 ({os_platform}) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{browser_version} Safari/605.1.15"
        elif browser_type == "edge":
            return f"Mozilla/5.0 ({os_platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{browser_version} Safari/537.36 Edg/{browser_version}"
        else:
            # Default to Chrome
            return f"Mozilla/5.0 ({os_platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{browser_version} Safari/537.36"
            
    def _get_platform_from_os(self, os_platform: str) -> str:
        """Extract platform name from OS string."""
        if "Windows" in os_platform:
            return "Windows"
        elif "Mac" in os_platform:
            return "MacIntel"
        elif "Linux" in os_platform:
            return "Linux x86_64"
        else:
            return "Unknown"


class RequestThrottler:
    """Advanced request throttling with domain-specific rate limits."""
    
    def __init__(self):
        self.domain_limits: Dict[str, Tuple[float, int]] = {}  # domain -> (requests_per_second, burst)
        self.domain_tokens: Dict[str, float] = {}  # domain -> current tokens
        self.domain_last_update: Dict[str, float] = {}  # domain -> last update timestamp
        self.lock = asyncio.Lock()
        
        # Default rate limits
        self.default_rps = 2.0  # requests per second
        self.default_burst = 5  # burst size
        
    def set_domain_limit(self, domain: str, requests_per_second: float, burst_size: int) -> None:
        """Set rate limit for a specific domain."""
        self.domain_limits[domain] = (requests_per_second, burst_size)
        self.domain_tokens[domain] = burst_size
        self.domain_last_update[domain] = time.time()
        
    def get_domain_from_url(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            # Fallback to simple splitting
            if "://" in url:
                url = url.split("://")[1]
            return url.split("/")[0]
            
    async def throttle(self, url: str) -> None:
        """Throttle request based on domain-specific rate limits."""
        domain = self.get_domain_from_url(url)
        
        async with self.lock:
            # Get domain-specific limits or use defaults
            rps, burst = self.domain_limits.get(domain, (self.default_rps, self.default_burst))
            
            # Initialize if this is the first request to this domain
            if domain not in self.domain_tokens:
                self.domain_tokens[domain] = burst
                self.domain_last_update[domain] = time.time()
                
            # Calculate token refill based on time elapsed
            now = time.time()
            time_passed = now - self.domain_last_update[domain]
            tokens_to_add = time_passed * rps
            
            # Update tokens and timestamp
            self.domain_tokens[domain] = min(burst, self.domain_tokens[domain] + tokens_to_add)
            self.domain_last_update[domain] = now
            
            # If not enough tokens, calculate wait time
            if self.domain_tokens[domain] < 1:
                wait_time = (1 - self.domain_tokens[domain]) / rps
                await asyncio.sleep(wait_time)
                self.domain_tokens[domain] = 0
            else:
                self.domain_tokens[domain] -= 1


class NetworkAnalyzer:
    """Analyze network conditions to optimize request patterns."""
    
    def __init__(self):
        self.domain_latency: Dict[str, List[float]] = {}  # domain -> list of recent latencies
        self.max_samples = 10  # Number of samples to keep per domain
        
    def record_latency(self, domain: str, latency: float) -> None:
        """Record latency for a domain."""
        if domain not in self.domain_latency:
            self.domain_latency[domain] = []
            
        self.domain_latency[domain].append(latency)
        
        # Keep only the most recent samples
        if len(self.domain_latency[domain]) > self.max_samples:
            self.domain_latency[domain] = self.domain_latency[domain][-self.max_samples:]
            
    def get_average_latency(self, domain: str) -> float:
        """Get average latency for a domain."""
        if domain not in self.domain_latency or not self.domain_latency[domain]:
            return 0.0
            
        return sum(self.domain_latency[domain]) / len(self.domain_latency[domain])
        
    def get_optimal_timeout(self, domain: str) -> float:
        """Calculate optimal timeout based on latency history."""
        avg_latency = self.get_average_latency(domain)
        if avg_latency <= 0:
            return 30.0  # Default timeout
            
        # Base timeout on average latency with a safety factor
        return max(10.0, min(60.0, avg_latency * 3))
        
    def get_optimal_connection_params(self, domain: str) -> Dict[str, Any]:
        """Get optimal connection parameters based on network analysis."""
        avg_latency = self.get_average_latency(domain)
        
        # Default parameters
        params = {
            "limit_per_host": 5,
            "keepalive_timeout": 30,
            "force_close": False,
        }
        
        # Adjust based on latency
        if avg_latency > 0:
            if avg_latency < 100:  # Fast connection
                params["limit_per_host"] = 8
                params["keepalive_timeout"] = 60
            elif avg_latency > 500:  # Slow connection
                params["limit_per_host"] = 3
                params["keepalive_timeout"] = 15
                
        return params


class AntiDetectionManager:
    """Centralized manager for all anti-detection measures."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Initialize components
        proxy_config = ProxyConfig(
            enabled=self.config.get("use_proxies", False),
            proxies=self.config.get("proxies", []),
            max_consecutive_uses=self.config.get("proxy_max_uses", 5),
            rotation_interval=self.config.get("proxy_rotation_interval", 300)
        )
        
        self.proxy_rotator = ProxyRotator(proxy_config)
        self.cookie_manager = CookieManager()
        self.fingerprint_generator = BrowserFingerprintGenerator()
        self.request_throttler = RequestThrottler()
        self.network_analyzer = NetworkAnalyzer()
        
        # Configure domain-specific rate limits
        for domain, limits in self.config.get("domain_rate_limits", {}).items():
            rps = limits.get("requests_per_second", 2.0)
            burst = limits.get("burst_size", 5)
            self.request_throttler.set_domain_limit(domain, rps, burst)
            
        # Default browser distribution (can be configured)
        self.browser_distribution = self.config.get("browser_distribution", {
            "chrome": 0.65,  # 65% chance of Chrome
            "firefox": 0.20,  # 20% chance of Firefox
            "safari": 0.10,   # 10% chance of Safari
            "edge": 0.05      # 5% chance of Edge
        })
        
        # Cache for generated fingerprints
        self.fingerprint_cache = {}
        self.last_fingerprint_rotation = time.time()
        self.fingerprint_rotation_interval = self.config.get("fingerprint_rotation_interval", 3600)  # 1 hour
        
    def get_browser_type(self) -> str:
        """Get a browser type based on configured distribution."""
        r = random.random()
        cumulative = 0
        for browser, probability in self.browser_distribution.items():
            cumulative += probability
            if r <= cumulative:
                return browser
        return "chrome"  # Default fallback
        
    def get_fingerprint(self) -> Dict[str, Any]:
        """Get a browser fingerprint, rotating periodically."""
        current_time = time.time()
        
        # Check if we need to generate a new fingerprint
        if (not self.fingerprint_cache or 
                current_time - self.last_fingerprint_rotation >= self.fingerprint_rotation_interval):
            browser_type = self.get_browser_type()
            self.fingerprint_cache = self.fingerprint_generator.generate_fingerprint(browser_type)
            self.last_fingerprint_rotation = current_time
            
        return self.fingerprint_cache
        
    def get_request_headers(self) -> Dict[str, str]:
        """Get request headers with anti-detection measures."""
        fingerprint = self.get_fingerprint()
        
        headers = {
            "User-Agent": fingerprint["user_agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": fingerprint["accept_language"],
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }
        
        # Add browser-specific headers based on user agent
        if "Chrome" in fingerprint["user_agent"]:
            headers.update({
                "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": f'"{fingerprint["platform"]}"',
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "none",
                "sec-fetch-user": "?1",
            })
        elif "Firefox" in fingerprint["user_agent"]:
            headers.update({
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "none",
                "sec-fetch-user": "?1",
            })
            
        # Randomize some header values
        if random.random() < 0.3:  # 30% chance to add DNT
            headers["DNT"] = "1"
            
        if random.random() < 0.8:  # 80% chance to add a referer
            referers = [
                "https://www.google.nl/",
                "https://www.google.com/",
                "https://www.bing.com/",
                "https://duckduckgo.com/",
                "https://www.reddit.com/",
                "https://www.youtube.com/",
                "https://www.facebook.com/",
                "https://twitter.com/",
            ]
            headers["Referer"] = random.choice(referers)
            
        return headers
        
    async def prepare_request(self, url: str) -> Tuple[Dict[str, str], Optional[str]]:
        """Prepare request with headers and proxy."""
        # Apply rate limiting
        await self.request_throttler.throttle(url)
        
        # Get headers and proxy
        headers = self.get_request_headers()
        proxy = self.proxy_rotator.get_current_proxy()
        
        # Get domain for cookie management
        domain = self.request_throttler.get_domain_from_url(url)
        
        # Add cookies if available
        cookies = self.cookie_manager.get_cookies(domain)
        if cookies:
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            headers["Cookie"] = cookie_str
            
        return headers, proxy
        
    def update_from_response(self, url: str, response: aiohttp.ClientResponse, duration: float) -> None:
        """Update anti-detection data from response."""
        domain = self.request_throttler.get_domain_from_url(url)
        
        # Record latency
        self.network_analyzer.record_latency(domain, duration)
        
        # Store cookies
        if response.cookies:
            cookies = {key: value.value for key, value in response.cookies.items()}
            self.cookie_manager.store_cookies(domain, cookies)