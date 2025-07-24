"""
Advanced HTTP client with anti-detection and performance optimizations.
"""
import logging
import asyncio
import time
import random
import socket
from typing import Dict, Optional, Any, Tuple
import aiohttp
from urllib.parse import urlparse

from .anti_detection import AntiDetectionManager, ExponentialBackoff, RetryConfig
from .user_agent_rotator import UserAgentRotator

logger = logging.getLogger(__name__)


class HttpClient:
    """
    Advanced HTTP client with anti-detection measures and performance optimizations.
    
    Features:
    - Connection pooling with optimized settings
    - User-agent rotation and realistic browser headers
    - Exponential backoff and retry mechanisms
    - Request timing randomization
    - Rate limiting
    - Cache busting
    """
    
    def __init__(self, anti_detection_manager: AntiDetectionManager, retry_config: RetryConfig):
        """Initialize HTTP client with anti-detection manager and retry configuration."""
        self.anti_detection_manager = anti_detection_manager
        self.retry_config = retry_config
        self.user_agent_rotator = UserAgentRotator()
        self.session = None
        
        # Default connection pool settings
        self.connection_limit = 20
        self.connection_limit_per_host = 5
        self.dns_cache_ttl = 300
        self.keepalive_timeout = 30
        self.request_timeout = 30
        
        # Default request timing settings
        self.min_delay = 0.5
        self.max_delay = 2.0
        self.use_cache_busting = True
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the HTTP client with custom settings."""
        connection_config = config.get('connection_pool', {})
        self.connection_limit = connection_config.get('limit', self.connection_limit)
        self.connection_limit_per_host = connection_config.get('limit_per_host', self.connection_limit_per_host)
        self.dns_cache_ttl = connection_config.get('dns_cache_ttl', self.dns_cache_ttl)
        self.keepalive_timeout = connection_config.get('keepalive_timeout', self.keepalive_timeout)
        self.request_timeout = config.get('request_timeout', self.request_timeout)
        
        anti_detection = config.get('anti_detection', {})
        self.min_delay = anti_detection.get('min_delay', self.min_delay)
        self.max_delay = anti_detection.get('max_delay', self.max_delay)
        self.use_cache_busting = anti_detection.get('use_cache_busting', self.use_cache_busting)
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session with optimized connection pooling."""
        if self.session is None or self.session.closed:
            # Configure advanced connection pooling for better performance
            conn = aiohttp.TCPConnector(
                limit=self.connection_limit,
                limit_per_host=self.connection_limit_per_host,
                ttl_dns_cache=self.dns_cache_ttl,
                keepalive_timeout=self.keepalive_timeout,
                enable_cleanup_closed=True,
                use_dns_cache=True,
                force_close=False,
                family=socket.AF_INET,  # Use IPv4 for better compatibility
                resolver=aiohttp.AsyncResolver()  # Use async DNS resolver for better performance
            )
            
            # Create session with optimized timeout configuration
            timeout = aiohttp.ClientTimeout(
                total=self.request_timeout,
                connect=min(10, self.request_timeout / 2),  # Connect timeout should be shorter
                sock_connect=min(10, self.request_timeout / 2),  # Socket connect timeout
                sock_read=self.request_timeout
            )
            
            # Create trace config for connection monitoring
            trace_config = aiohttp.TraceConfig()
            
            # Add connection monitoring callbacks
            async def on_request_start(session, trace_config_ctx, params):
                trace_config_ctx.start = time.time()
                
            async def on_request_end(session, trace_config_ctx, params):
                duration = time.time() - trace_config_ctx.start
                url = str(params.url)
                domain = self.anti_detection_manager.request_throttler.get_domain_from_url(url)
                self.anti_detection_manager.network_analyzer.record_latency(domain, duration * 1000)
                
            trace_config.on_request_start.append(on_request_start)
            trace_config.on_request_end.append(on_request_end)
            
            self.session = aiohttp.ClientSession(
                connector=conn,
                timeout=timeout,
                headers={'Connection': 'keep-alive'},
                trace_configs=[trace_config],
                cookie_jar=aiohttp.CookieJar(unsafe=True)  # Allow cookies from non-secure connections
            )
        return self.session
    
    def add_cache_busting(self, url: str) -> str:
        """Add cache-busting parameter to URL."""
        if not self.use_cache_busting:
            return url
            
        parsed_url = urlparse(url)
        query = parsed_url.query
        
        # Add timestamp parameter to prevent caching
        timestamp = str(int(time.time() * 1000))
        separator = '&' if query else ''
        new_query = f"{query}{separator}_={timestamp}"
        
        # Reconstruct URL with new query parameters
        parts = list(parsed_url)
        parts[4] = new_query  # index 4 is query
        
        return urlparse('').geturl().join(parts)
    
    async def fetch(self, url: str, method: str = "GET", **kwargs) -> Tuple[Optional[str], int, Dict[str, str]]:
        """
        Fetch a URL with anti-detection measures and retry logic.
        
        Args:
            url: The URL to fetch
            method: HTTP method (GET, POST, etc.)
            **kwargs: Additional arguments to pass to the request
            
        Returns:
            Tuple of (content, status_code, response_headers)
        """
        # Apply rate limiting through the anti-detection manager
        domain = self.anti_detection_manager.request_throttler.get_domain_from_url(url)
        await self.anti_detection_manager.request_throttler.throttle(url)
        
        session = await self.get_session()
        
        # Add cache-busting parameter
        if method.upper() == "GET":
            url = self.add_cache_busting(url)
        
        # Initialize exponential backoff
        backoff = ExponentialBackoff(self.retry_config)
        
        start_time = time.time()
        success = False
        error_message = None
        last_exception = None
        
        # Retry loop with exponential backoff
        for attempt in range(self.retry_config.max_retries + 1):
            try:
                # Get advanced anti-detection headers and proxy
                headers, proxy = await self.anti_detection_manager.prepare_request(url)
                
                # Add randomized delay before request (anti-detection)
                # Use variable delay based on domain analysis
                optimal_params = self.anti_detection_manager.network_analyzer.get_optimal_connection_params(domain)
                min_delay = self.min_delay * (1.0 if attempt == 0 else 1.5)
                max_delay = self.max_delay * (1.0 if attempt == 0 else 2.0)
                delay = random.uniform(min_delay, max_delay)
                await asyncio.sleep(delay)
                
                request_kwargs = {
                    'headers': headers,
                    'allow_redirects': True
                }
                
                # Add proxy if available
                if proxy:
                    request_kwargs['proxy'] = proxy
                
                # Add any additional kwargs
                request_kwargs.update(kwargs)
                
                # Calculate optimal timeout based on network analysis
                timeout = self.anti_detection_manager.network_analyzer.get_optimal_timeout(domain)
                if timeout > 0:
                    request_kwargs['timeout'] = aiohttp.ClientTimeout(total=timeout)
                
                request_start = time.time()
                
                # Make the request with the appropriate method
                request_method = getattr(session, method.lower())
                async with request_method(url, **request_kwargs) as response:
                    request_duration = time.time() - request_start
                    
                    # Update network analyzer with latency data
                    self.anti_detection_manager.network_analyzer.record_latency(domain, request_duration * 1000)
                    
                    # Update cookies from response
                    self.anti_detection_manager.update_from_response(url, response, request_duration)
                    
                    if response.status == 200:
                        content = await response.text()
                        success = True
                        logger.debug(f"Successfully fetched {url} on attempt {attempt + 1}")
                        
                        return content, response.status, dict(response.headers)
                    elif response.status == 429:  # Rate limited
                        error_message = f"Rate limited (HTTP 429)"
                        logger.warning(f"Rate limited fetching {url}, attempt {attempt + 1}")
                        # Longer delay for rate limiting
                        if attempt < self.retry_config.max_retries:
                            delay = backoff.get_delay() * 2  # Double delay for rate limits
                            # Adjust rate limits for this domain
                            self.anti_detection_manager.request_throttler.set_domain_limit(
                                domain, 
                                self.anti_detection_manager.request_throttler.default_rps / 2,  # Reduce rate by half
                                max(1, self.anti_detection_manager.request_throttler.default_burst // 2)   # Reduce burst size
                            )
                            await asyncio.sleep(delay)
                        continue
                    elif response.status in [503, 502, 504]:  # Server errors - retry
                        error_message = f"Server error {response.status}: {response.reason}"
                        logger.warning(f"Server error fetching {url}: {error_message}, attempt {attempt + 1}")
                        if attempt < self.retry_config.max_retries:
                            delay = backoff.get_delay()
                            await asyncio.sleep(delay)
                        continue
                    elif response.status == 403:  # Forbidden - might be blocked
                        error_message = f"Access forbidden (HTTP 403) - possible bot detection"
                        logger.warning(f"Access forbidden for {url}, attempt {attempt + 1}")
                        if attempt < self.retry_config.max_retries:
                            # Longer delay for potential bot detection
                            delay = backoff.get_delay() * 3
                            # Generate new fingerprint to avoid detection
                            self.anti_detection_manager.fingerprint_cache = {}
                            await asyncio.sleep(delay)
                        continue
                    else:
                        error_message = f"HTTP error {response.status}: {response.reason}"
                        logger.error(f"HTTP error fetching {url}: {error_message}")
                        return None, response.status, dict(response.headers)
                        
            except asyncio.TimeoutError as e:
                error_message = "Request timed out"
                last_exception = e
                logger.warning(f"Timeout fetching {url}, attempt {attempt + 1}")
                if attempt < self.retry_config.max_retries:
                    delay = backoff.get_delay()
                    await asyncio.sleep(delay)
                continue
                
            except aiohttp.ClientConnectorError as e:
                error_message = f"Connection error: {str(e)}"
                last_exception = e
                logger.warning(f"Connection error fetching {url}: {e}, attempt {attempt + 1}")
                if attempt < self.retry_config.max_retries:
                    delay = backoff.get_delay()
                    await asyncio.sleep(delay)
                continue
                
            except aiohttp.ClientError as e:
                error_message = f"Client error: {str(e)}"
                last_exception = e
                logger.warning(f"Client error fetching {url}: {e}, attempt {attempt + 1}")
                if attempt < self.retry_config.max_retries:
                    delay = backoff.get_delay()
                    await asyncio.sleep(delay)
                continue
                
            except Exception as e:
                error_message = f"Unexpected error: {str(e)}"
                last_exception = e
                logger.error(f"Unexpected error fetching {url}: {e}", exc_info=True)
                if attempt < self.retry_config.max_retries:
                    delay = backoff.get_delay()
                    await asyncio.sleep(delay)
                continue
        
        # If we get here, all retries failed
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Failed to fetch {url} after {self.retry_config.max_retries + 1} attempts: {error_message}")
        
        if last_exception:
            logger.debug(f"Last exception: {last_exception}")
            
        return None, 0, {}
    
    async def close(self) -> None:
        """Close the HTTP client session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None