
# Ultra-fast monitoring engine optimizations
class UltraFastMonitoringEngine:
    """Ultra-optimized monitoring engine for maximum speed."""
    
    def __init__(self, config):
        self.config = config
        self.session_pool = []  # Pre-created session pool
        self.executor = ThreadPoolExecutor(max_workers=20)  # Increased workers
        
    async def monitor_products_parallel(self, products: List[ProductConfig]) -> List[ProductData]:
        """Monitor all products in parallel for maximum speed."""
        start_time = time.time()
        
        # Create tasks for all products simultaneously
        tasks = []
        for product in products:
            task = asyncio.create_task(self.monitor_single_product_ultra_fast(product))
            tasks.append(task)
        
        # Execute all monitoring tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful results
        successful_results = [r for r in results if not isinstance(r, Exception)]
        
        elapsed = time.time() - start_time
        self.logger.info(f"ULTRA SPEED: Monitored {len(products)} products in {elapsed:.2f}s")
        
        return successful_results
    
    async def monitor_single_product_ultra_fast(self, product: ProductConfig) -> ProductData:
        """Ultra-fast single product monitoring with minimal overhead."""
        try:
            # Use pre-warmed session
            session = await self.get_fast_session()
            
            # Single request with optimized headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache'
            }
            
            async with session.get(product.url, headers=headers, timeout=3) as response:
                html = await response.text()
                
                # Ultra-fast parsing - extract only what we need
                return await self.extract_product_data_ultra_fast(html, product)
                
        except Exception as e:
            self.logger.error(f"Ultra-fast monitoring failed for {product.url}: {e}")
            return None
    
    async def extract_product_data_ultra_fast(self, html: str, product: ProductConfig) -> ProductData:
        """Ultra-fast data extraction with minimal DOM parsing."""
        # Use regex for speed instead of BeautifulSoup
        import re
        
        # Fast price extraction
        price_patterns = [
            r'"price":\s*"([^"]+)"',
            r'data-test="price"[^>]*>([^<]+)',
            r'class="prijs"[^>]*>([^<]+)',
        ]
        
        price = "Not Available"
        for pattern in price_patterns:
            match = re.search(pattern, html)
            if match:
                price = match.group(1)
                break
        
        # Fast stock status extraction
        stock_patterns = [
            r'"availability":\s*"([^"]+)"',
            r'op voorraad',
            r'niet leverbaar',
            r'Pre-order'
        ]
        
        stock_status = "Unknown"
        if re.search(r'op voorraad|Pre-order', html, re.IGNORECASE):
            stock_status = "In Stock"
        elif re.search(r'niet leverbaar|uitverkocht', html, re.IGNORECASE):
            stock_status = "Out of Stock"
        
        # Fast title extraction
        title_match = re.search(r'<title>([^<]+)</title>', html)
        title = title_match.group(1) if title_match else "Unknown Product"
        
        return ProductData(
            product_id=product.product_id,
            title=title.strip(),
            price=price,
            stock_status=stock_status,
            url=product.url,
            timestamp=time.time()
        )
    
    async def get_fast_session(self) -> aiohttp.ClientSession:
        """Get a pre-warmed, optimized session."""
        if not self.session_pool:
            # Create session pool for reuse
            connector = aiohttp.TCPConnector(
                limit=100,  # High connection limit
                limit_per_host=20,  # High per-host limit
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            
            timeout = aiohttp.ClientTimeout(total=3, connect=1)
            
            for _ in range(5):  # Pool of 5 sessions
                session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                    headers={'Connection': 'keep-alive'}
                )
                self.session_pool.append(session)
        
        return self.session_pool[0]  # Use first available session
