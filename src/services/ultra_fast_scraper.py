
class UltraFastScraper:
    """Ultra-fast web scraping with minimal overhead."""
    
    def __init__(self):
        self.session_pool = []
        self.dns_cache = {}  # DNS caching for speed
        
    async def scrape_ultra_fast(self, urls: List[str]) -> List[Dict]:
        """Scrape multiple URLs in parallel with maximum speed."""
        # Pre-resolve DNS for all domains
        await self.warm_dns_cache(urls)
        
        # Create tasks for all URLs
        tasks = []
        for url in urls:
            task = asyncio.create_task(self.scrape_single_ultra_fast(url))
            tasks.append(task)
        
        # Execute all scraping in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return [r for r in results if not isinstance(r, Exception)]
    
    async def scrape_single_ultra_fast(self, url: str) -> Dict:
        """Scrape single URL with minimal overhead."""
        try:
            # Use optimized session
            session = await self.get_optimized_session()
            
            # Minimal headers for speed
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html',
                'Connection': 'keep-alive'
            }
            
            # Fast request with short timeout
            async with session.get(url, headers=headers, timeout=2) as response:
                if response.status == 200:
                    html = await response.text()
                    return self.extract_data_ultra_fast(html, url)
                else:
                    return {'url': url, 'error': f'HTTP {response.status}'}
                    
        except Exception as e:
            return {'url': url, 'error': str(e)}
    
    def extract_data_ultra_fast(self, html: str, url: str) -> Dict:
        """Extract data using fastest possible methods."""
        import re
        
        # Use regex instead of BeautifulSoup for speed
        data = {'url': url}
        
        # Fast price extraction
        price_match = re.search(r'"price":\s*"([^"]+)"|data-test="price"[^>]*>([^<]+)', html)
        if price_match:
            data['price'] = price_match.group(1) or price_match.group(2)
        
        # Fast stock extraction
        if re.search(r'op voorraad|Pre-order', html, re.IGNORECASE):
            data['stock'] = 'In Stock'
        elif re.search(r'niet leverbaar|uitverkocht', html, re.IGNORECASE):
            data['stock'] = 'Out of Stock'
        else:
            data['stock'] = 'Unknown'
        
        # Fast title extraction
        title_match = re.search(r'<title>([^<]+)</title>', html)
        if title_match:
            data['title'] = title_match.group(1).strip()
        
        return data
    
    async def get_optimized_session(self) -> aiohttp.ClientSession:
        """Get ultra-optimized session for maximum speed."""
        if not self.session_pool:
            # Create optimized connector
            connector = aiohttp.TCPConnector(
                limit=200,  # Very high connection limit
                limit_per_host=50,  # High per-host limit
                keepalive_timeout=60,
                enable_cleanup_closed=True,
                use_dns_cache=True,
                ttl_dns_cache=300
            )
            
            # Ultra-short timeouts for speed
            timeout = aiohttp.ClientTimeout(total=2, connect=0.5)
            
            session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={'Connection': 'keep-alive'}
            )
            
            self.session_pool.append(session)
        
        return self.session_pool[0]
    
    async def warm_dns_cache(self, urls: List[str]) -> None:
        """Pre-resolve DNS for all domains to avoid lookup delays."""
        import socket
        from urllib.parse import urlparse
        
        domains = set()
        for url in urls:
            domain = urlparse(url).netloc
            domains.add(domain)
        
        # Pre-resolve all domains
        for domain in domains:
            try:
                socket.gethostbyname(domain)
                self.dns_cache[domain] = True
            except:
                pass
