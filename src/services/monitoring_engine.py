"""
Minimal monitoring engine for tracking product availability.
"""

import logging
import asyncio
import random
import time
import re
import json
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime, timedelta
import aiohttp
from lxml import html
import urllib.parse
from dataclasses import dataclass

from ..models.interfaces import IMonitoringEngine
from ..models.product_data import (
    ProductData, ProductConfig, StockChange, PriceChange,
    StockStatus, URLType, MonitoringStatus
)
from ..config.config_manager import ConfigManager
from ..database.repository import (
    ProductRepository, ProductStatusRepository, 
    StockChangeRepository, MetricsRepository
)
from ..database.price_threshold_repository import PriceThresholdRepository


class MonitoringEngine(IMonitoringEngine):
    """Minimal monitoring engine implementation."""
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize monitoring engine."""
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        self.product_repo = ProductRepository()
        self.status_repo = ProductStatusRepository()
        self.stock_change_repo = StockChangeRepository()
        self.metrics_repo = MetricsRepository()
        self.price_threshold_repo = PriceThresholdRepository()
        
        self.monitoring_tasks = {}
        self.session = None
        self.running = False
        
        # Callbacks for stock changes
        self.stock_change_callbacks = []
        
        # Load configuration
        monitoring_config = self.config_manager.get_monitoring_config()
        self.default_interval = monitoring_config.get('default_interval', 60)
        self.min_interval = monitoring_config.get('min_interval', 30)
        self.max_concurrent = monitoring_config.get('max_concurrent', 10)
        self.request_timeout = monitoring_config.get('request_timeout', 30)
        
        # Anti-detection settings
        anti_detection = monitoring_config.get('anti_detection', {})
        self.min_delay = anti_detection.get('min_delay', 0.1)
        self.max_delay = anti_detection.get('max_delay', 0.5)
        self.use_cache_busting = anti_detection.get('use_cache_busting', True)
        
        # User agents for rotation
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self.session is None or self.session.closed:
            conn = aiohttp.TCPConnector(
                limit=20,
                limit_per_host=5,
                ttl_dns_cache=300,
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            
            timeout = aiohttp.ClientTimeout(total=self.request_timeout)
            
            self.session = aiohttp.ClientSession(
                connector=conn,
                timeout=timeout,
                headers={'Connection': 'keep-alive'}
            )
        return self.session
    
    def _get_random_user_agent(self) -> str:
        """Get a random user agent."""
        return random.choice(self.user_agents)
    
    def _get_request_headers(self) -> Dict[str, str]:
        """Get request headers."""
        return {
            'User-Agent': self._get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch a web page."""
        try:
            session = await self._get_session()
            headers = self._get_request_headers()
            
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    self.logger.warning(f"HTTP {response.status} for {url}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {e}")
            return None
    
    def _detect_stock_status(self, text: str) -> str:
        """Detect stock status from text."""
        text_lower = text.lower()
        
        # Out of stock patterns
        if any(pattern in text_lower for pattern in [
            'niet leverbaar', 'uitverkocht', 'tijdelijk uitverkocht'
        ]):
            return StockStatus.OUT_OF_STOCK.value
        
        # In stock patterns
        if any(pattern in text_lower for pattern in [
            'op voorraad', 'direct leverbaar', 'pre-order', 'beschikbaar'
        ]):
            return StockStatus.IN_STOCK.value
        
        # Default to in stock
        return StockStatus.IN_STOCK.value
    
    async def monitor_product(self, product_config: ProductConfig) -> Optional[ProductData]:
        """Monitor a single product."""
        try:
            self.logger.info(f"Monitoring product: {product_config.url}")
            
            # Fetch the page
            html_content = await self._fetch_page(product_config.url)
            if not html_content:
                return None
            
            # Parse the page
            if URLType.is_wishlist(product_config.url):
                products = await self._parse_wishlist(html_content, product_config.url)
                return products[0] if products else None
            else:
                return await self._parse_product_page(html_content, product_config.url)
                
        except Exception as e:
            self.logger.error(f"Error monitoring product {product_config.url}: {e}")
            return None
    
    async def _parse_product_page(self, html_content: str, product_url: str) -> ProductData:
        """Parse a single product page."""
        try:
            tree = html.fromstring(html_content)
            
            # Extract product ID from URL
            product_id_match = re.search(r'/([0-9]+)/', product_url)
            product_id = product_id_match.group(1) if product_id_match else "unknown"
            
            # Extract title
            title_elements = tree.xpath('//h1//text() | //span[@data-test="title"]//text()')
            title = ' '.join(title_elements).strip() if title_elements else "Unknown Product"
            
            # Extract price
            price_elements = tree.xpath('//span[@data-test="price"]//text() | //*[contains(@class, "price")]//text()')
            price = "€0.00"
            for price_text in price_elements:
                price_match = re.search(r'€\s*([0-9]+(?:[,.]\d{2})?)', str(price_text))
                if price_match:
                    price = f"€{price_match.group(1)}"
                    break
            
            # Detect stock status
            page_text = tree.text_content()
            stock_status = self._detect_stock_status(page_text)
            
            return ProductData(
                product_id=product_id,
                title=title,
                price=price,
                original_price=price,
                image_url="",
                product_url=product_url,
                uncached_url=product_url,
                stock_status=stock_status,
                stock_level="",
                website="bol.com",
                delivery_info="",
                sold_by_bol=True,
                last_checked=datetime.utcnow()
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing product page: {e}")
            return None
    
    async def _parse_wishlist(self, html_content: str, wishlist_url: str) -> List[ProductData]:
        """Parse wishlist products."""
        try:
            tree = html.fromstring(html_content)
            products = []
            
            # Find product links
            product_links = tree.xpath('//a[contains(@href, "/p/")]')
            
            for link in product_links:  # Process all products
                href = link.get('href', '')
                if not href or '/p/' not in href:
                    continue
                
                # Build full URL
                if href.startswith('/'):
                    product_url = f"https://www.bol.com{href}"
                else:
                    product_url = href
                
                # Extract product ID
                product_id_match = re.search(r'/([0-9]+)/', product_url)
                if not product_id_match:
                    continue
                
                product_id = product_id_match.group(1)
                
                # Extract title from link text
                title = link.text_content().strip() or "Unknown Product"
                
                # Basic price and stock detection
                parent = link.getparent()
                parent_text = parent.text_content() if parent is not None else ""
                
                price = "€0.00"
                price_match = re.search(r'€\s*([0-9]+(?:[,.]\d{2})?)', parent_text)
                if price_match:
                    price = f"€{price_match.group(1)}"
                
                stock_status = self._detect_stock_status(parent_text)
                
                products.append(ProductData(
                    product_id=product_id,
                    title=title,
                    price=price,
                    original_price=price,
                    image_url="",
                    product_url=product_url,
                    uncached_url=product_url,
                    stock_status=stock_status,
                    stock_level="",
                    website="bol.com",
                    delivery_info="",
                    sold_by_bol=True,
                    last_checked=datetime.utcnow()
                ))
            
            return products
            
        except Exception as e:
            self.logger.error(f"Error parsing wishlist: {e}")
            return []
    
    async def start_monitoring(self, products: List[ProductConfig]) -> None:
        """Start monitoring products."""
        self.logger.info(f"Starting monitoring for {len(products)} products")
        self.running = True
        
        # Create monitoring tasks
        for product in products:
            if product.product_id not in self.monitoring_tasks:
                task = asyncio.create_task(self._monitor_product_loop(product))
                self.monitoring_tasks[product.product_id] = task
    
    async def _monitor_product_loop(self, product_config: ProductConfig) -> None:
        """Monitor a product in a loop."""
        loop_count = 0
        while self.running:
            try:
                loop_count += 1
                
                # Get monitoring interval first
                interval = await self._get_monitoring_interval(product_config.url)
                
                self.logger.info(f"🔄 [Loop {loop_count}] Monitoring {product_config.url[:60]}... (interval: {interval}s)")
                
                # Monitor the product or wishlist
                start_time = time.time()
                
                if URLType.is_wishlist(product_config.url):
                    # Monitor wishlist - get all products
                    product_data = await self.monitor_wishlist(product_config.url)
                    end_time = time.time()
                    
                    if product_data:
                        self.logger.info(f"📦 Found {len(product_data)} products in {end_time - start_time:.2f}s")
                        for i, product in enumerate(product_data[:5], 1):  # Show first 5
                            status_emoji = "✅" if product.stock_status == "In Stock" else "❌"
                            self.logger.info(f"   {i:2d}. {status_emoji} {product.title[:45]}... - {product.price}")
                        if len(product_data) > 5:
                            self.logger.info(f"   ... and {len(product_data) - 5} more products")
                        
                        # Check for stock changes for each product
                        for product in product_data:
                            await self._check_stock_changes(product)
                    else:
                        self.logger.warning(f"⚠️ No products found in wishlist")
                else:
                    # Monitor single product
                    product_data = await self.monitor_product(product_config)
                    end_time = time.time()
                    
                    if product_data:
                        status_emoji = "✅" if product_data.stock_status == "In Stock" else "❌"
                        self.logger.info(f"📦 {status_emoji} Product: {product_data.title[:45]}... - {product_data.price} - {product_data.stock_status}")
                        
                        # Check for stock changes
                        await self._check_stock_changes(product_data)
                    else:
                        self.logger.warning(f"⚠️ No product data returned for {product_config.url[:60]}...")
                
                # Wait for next check
                self.logger.info(f"⏰ Waiting {interval}s until next check...")
                await asyncio.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"❌ Error in monitoring loop for {product_config.url}: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def _get_monitoring_interval(self, url: str) -> float:
        """Get monitoring interval for a URL."""
        # Check database for website-specific intervals
        try:
            from ..database.connection import db
            
            domain = self._extract_domain(url)
            cursor = db.execute(
                "SELECT interval_seconds FROM website_intervals WHERE domain = ?",
                (domain,)
            )
            result = cursor.fetchall()
            
            if result:
                return float(result[0][0])
                
        except Exception as e:
            self.logger.error(f"Error getting interval for {url}: {e}")
        
        return self.default_interval
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except:
            return "unknown"
    
    async def _check_stock_changes(self, product_data: ProductData) -> None:
        """Check for stock changes and notify callbacks."""
        try:
            # Get previous status
            previous_status = await self._get_previous_stock_status(product_data.product_id)
            
            if previous_status and previous_status != product_data.stock_status:
                # Stock changed - create change record
                stock_change = StockChange(
                    product_id=product_data.product_id,
                    previous_status=previous_status,
                    current_status=product_data.stock_status,
                    timestamp=datetime.utcnow(),
                    price_change=None
                )
                
                # Save to database
                await self._save_stock_change(stock_change)
                
                # Notify callbacks
                for callback in self.stock_change_callbacks:
                    try:
                        await callback(product_data, stock_change)
                    except Exception as e:
                        self.logger.error(f"Error in stock change callback: {e}")
            
            # Update current status
            await self._save_product_status(product_data)
            
        except Exception as e:
            self.logger.error(f"Error checking stock changes: {e}")
    
    async def _get_previous_stock_status(self, product_id: str) -> Optional[str]:
        """Get previous stock status from database."""
        try:
            from ..database.connection import db
            
            cursor = db.execute(
                "SELECT stock_status FROM product_status WHERE product_id = ?",
                (product_id,)
            )
            result = cursor.fetchall()
            
            return result[0][0] if result else None
            
        except Exception as e:
            self.logger.error(f"Error getting previous status: {e}")
            return None
    
    async def _save_stock_change(self, stock_change: StockChange) -> None:
        """Save stock change to database."""
        try:
            from ..database.connection import db
            
            db.execute(
                """INSERT INTO stock_changes 
                   (product_id, previous_status, current_status, timestamp, notification_sent)
                   VALUES (?, ?, ?, ?, ?)""",
                (stock_change.product_id, stock_change.previous_status, 
                 stock_change.current_status, stock_change.timestamp, False)
            )
            db.commit()
            
        except Exception as e:
            self.logger.error(f"Error saving stock change: {e}")
    
    async def _save_product_status(self, product_data: ProductData) -> None:
        """Save product status to database."""
        try:
            from ..database.connection import db
            
            db.execute(
                """INSERT OR REPLACE INTO product_status 
                   (product_id, title, price, stock_status, product_url, last_checked)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (product_data.product_id, product_data.title, product_data.price,
                 product_data.stock_status, product_data.product_url, product_data.last_checked)
            )
            db.commit()
            
        except Exception as e:
            self.logger.error(f"Error saving product status: {e}")
    
    async def stop_monitoring(self) -> None:
        """Stop monitoring."""
        self.logger.info("Stopping monitoring")
        self.running = False
        
        # Cancel all monitoring tasks
        for task in self.monitoring_tasks.values():
            task.cancel()
        
        self.monitoring_tasks.clear()
        
        # Close session
        if self.session and not self.session.closed:
            await self.session.close()
    


    
    async def detect_stock_changes(self, product_data: ProductData) -> Optional[StockChange]:
        """Detect stock changes for a product."""
        try:
            # Get previous status
            previous_status = await self.status_repo.get_product_status(product_data.product_id)
            
            # If no previous status, no change to detect
            if not previous_status:
                return None
            
            # Check for stock changes
            if previous_status.stock_status != product_data.stock_status:
                # Create stock change
                stock_change = StockChange(
                    product_id=product_data.product_id,
                    previous_status=previous_status.stock_status,
                    current_status=product_data.stock_status,
                    timestamp=datetime.utcnow()
                )
                
                return stock_change
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error detecting stock changes for {product_data.product_id}: {e}")
            return None


    async def _parse_wishlist_products(self, html_content: str, wishlist_url: str) -> List[ProductData]:
        """Parse wishlist products from HTML content."""
        try:
            tree = html.fromstring(html_content)
            
            # Find all product links
            product_links = tree.xpath('//a[contains(@href, "/p/")]')
            self.logger.info(f"Found {len(product_links)} product links in wishlist")
            
            products = []
            for link in product_links:  # Process all products
                href = link.get('href', '')
                if not href or '/p/' not in href:
                    continue
                
                # Normalize URL
                if href.startswith('/'):
                    product_url = f"https://www.bol.com{href}"
                else:
                    product_url = href
                
                # Extract product ID
                product_id_match = re.search(r'/([0-9]+)/', product_url)
                if not product_id_match:
                    continue
                
                product_id = product_id_match.group(1)
                
                # Extract title from link text
                title = link.text_content().strip() or "Unknown Product"
                
                # Basic price and stock detection
                parent = link.getparent()
                parent_text = parent.text_content() if parent is not None else ""
                
                price = "€0.00"
                price_match = re.search(r'€\s*([0-9]+(?:[,.]\d{2})?)', parent_text)
                if price_match:
                    price = f"€{price_match.group(1)}"
                
                stock_status = self._detect_stock_status(parent_text)
                
                products.append(ProductData(
                    product_id=product_id,
                    title=title,
                    price=price,
                    original_price=price,
                    image_url="",
                    product_url=product_url,
                    uncached_url=product_url,
                    stock_status=stock_status,
                    stock_level="",
                    website="bol.com",
                    delivery_info="",
                    sold_by_bol=True,
                    last_checked=datetime.utcnow()
                ))
            
            return products
            
        except Exception as e:
            self.logger.error(f"Error parsing wishlist products: {e}")
            return []

    async def _parse_wishlist_products_parallel(self, html_content: str, wishlist_url: str) -> List[ProductData]:
        """ULTRA-FAST: Parse wishlist products in parallel for maximum speed."""
        start_time = time.time()
        
        try:
            tree = html.fromstring(html_content)
            
            # Find all product links first (this is fast)
            product_links = tree.xpath('//a[contains(@href, "/p/")]')
            self.logger.info(f"Found {len(product_links)} product links in wishlist")
            
            if not product_links:
                return []
            
            # Create tasks for parallel processing
            tasks = []
            processed_urls = set()
            
            for link_element in product_links:
                # Quick URL validation
                href = link_element.get('href', '')
                if not href or '/p/' not in href:
                    continue
                
                # Normalize URL quickly
                if href.startswith('/'):
                    product_url = f"https://www.bol.com{href}"
                else:
                    product_url = href
                
                clean_url = product_url.split('?')[0].split('#')[0]
                if clean_url.endswith('/'):
                    clean_url = clean_url[:-1]
                clean_url += '/'
                
                if clean_url in processed_urls:
                    continue
                processed_urls.add(clean_url)
                
                # Create task for parallel processing
                task = asyncio.create_task(
                    self._process_single_product_ultra_fast(link_element, clean_url, tree)
                )
                tasks.append(task)
            
            # Execute all product processing in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter successful results
            products = []
            for result in results:
                if isinstance(result, Exception):
                    self.logger.error(f"Product processing failed: {result}")
                elif result:
                    products.append(result)
            
            elapsed = time.time() - start_time
            self.logger.info(f"ULTRA SPEED: Processed {len(products)} products in {elapsed:.3f}s")
            
            return products
            
        except Exception as e:
            self.logger.error(f"Error parsing wishlist products in parallel: {e}")
            return []
    
    async def _process_single_product_ultra_fast(self, link_element, product_url: str, tree) -> Optional[ProductData]:
        """Process a single product with maximum speed using minimal DOM queries."""
        try:
            # Extract product ID from URL (fastest method)
            product_id_match = re.search(r'/([0-9]+)/', product_url)
            if not product_id_match:
                return None
            
            url_product_id = product_id_match.group(1)
            
            # Ultra-fast title extraction
            title = await self._extract_title_ultra_fast(link_element)
            
            # Ultra-fast price and stock extraction
            price, stock_status = await self._extract_price_stock_ultra_fast(link_element, url_product_id, tree)
            
            # Extract product image
            image_url = await self._extract_image_ultra_fast(link_element)
            
            # Create uncached URL for direct purchase
            uncached_url = self._create_uncached_url(product_url)
            
            # Create ProductData object
            return ProductData(
                product_id=url_product_id,
                title=title,
                price=price,
                original_price=price,
                image_url=image_url,
                product_url=product_url,
                uncached_url=uncached_url,
                stock_status=stock_status,
                stock_level="",
                website="bol.com",
                delivery_info="",
                sold_by_bol=True,
                last_checked=datetime.utcnow()
            )
            
        except Exception as e:
            self.logger.error(f"Error processing single product {product_url}: {e}")
            return None
    
    async def _extract_title_ultra_fast(self, link_element) -> str:
        """Extract title with minimal processing."""
        # Method 1: Direct link text (fastest)
        link_text = link_element.text_content().strip()
        if link_text and len(link_text) > 5 and not link_text.startswith('http'):
            return link_text
        
        # Method 2: Parent container (still fast)
        parent = link_element.getparent()
        if parent is not None:
            text_elements = parent.xpath('.//text()[normalize-space()]')
            for text in text_elements[:3]:  # Limit to first 3 for speed
                text_content = str(text).strip()
                if (len(text_content) > 10 and 
                    not text_content.startswith('€') and 
                    not text_content.startswith('http') and
                    not text_content.isdigit()):
                    return text_content
        
        return "Unknown Product"
    
    async def _extract_image_ultra_fast(self, link_element) -> str:
        """Extract product image URL with minimal processing."""
        try:
            # Strategy 1: Look for img elements within the link or its parent
            parent = link_element.getparent()
            if parent is not None:
                # Look for image elements in the parent container
                img_selectors = [
                    './/img[@src]',
                    './/img[@data-src]',
                    './/img[@data-lazy-src]'
                ]
                
                for selector in img_selectors:
                    img_elements = parent.xpath(selector)
                    for img in img_elements:
                        # Try different src attributes
                        src_attrs = ['src', 'data-src', 'data-lazy-src', 'data-original']
                        for attr in src_attrs:
                            src = img.get(attr)
                            if src and src.startswith(('http', '//')):
                                # Ensure it's a full URL
                                if src.startswith('//'):
                                    src = f"https:{src}"
                                elif src.startswith('/'):
                                    src = f"https://www.bol.com{src}"
                                
                                # Filter out placeholder/loading images
                                if not any(skip in src.lower() for skip in ['placeholder', 'loading', 'blank', '1x1']):
                                    return src
            
            # Strategy 2: Look within the link element itself
            img_elements = link_element.xpath('.//img[@src]')
            for img in img_elements:
                src = img.get('src')
                if src and src.startswith(('http', '//')):
                    if src.startswith('//'):
                        src = f"https:{src}"
                    elif src.startswith('/'):
                        src = f"https://www.bol.com{src}"
                    
                    if not any(skip in src.lower() for skip in ['placeholder', 'loading', 'blank', '1x1']):
                        return src
            
            return ""  # No image found
            
        except Exception as e:
            self.logger.error(f"Error extracting image: {e}")
            return ""
    
    def _create_uncached_url(self, product_url: str) -> str:
        """Create an uncached URL for direct purchase by adding cache-busting parameters."""
        try:
            import time
            import random
            
            # Add cache-busting parameters
            separator = '&' if '?' in product_url else '?'
            timestamp = int(time.time())
            random_id = random.randint(1000, 9999)
            
            uncached_url = f"{product_url}{separator}t={timestamp}&r={random_id}"
            return uncached_url
            
        except Exception as e:
            self.logger.error(f"Error creating uncached URL: {e}")
            return product_url
    
    async def _extract_price_stock_ultra_fast(self, link_element, product_id: str, tree) -> Tuple[str, str]:
        """Enhanced price and stock status extraction with improved price detection."""
        price = "€0.00"
        stock_status = StockStatus.IN_STOCK.value
        
        try:
            # Use XPath to find price elements near this product
            parent = link_element.getparent()
            if parent is not None:
                # Strategy 1: Look for specific price-related elements with better targeting
                price_selectors = [
                    './/span[contains(@class, "price")]',
                    './/div[contains(@class, "price")]', 
                    './/span[contains(@data-test, "price")]',
                    './/div[contains(@class, "prijs")]',
                    './/span[contains(@class, "amount")]'
                ]
                
                for selector in price_selectors:
                    price_elements = parent.xpath(selector)
                    for element in price_elements:
                        price_text = element.text_content().strip()
                        # Look for Dutch price format: "169,-" or "13,99" or "499,99"
                        price_match = re.search(r'(\d+)(?:[,.](\d{1,2}))?(?:\s*[-,])?', price_text)
                        if price_match:
                            euros = price_match.group(1)
                            cents = price_match.group(2) if price_match.group(2) else "00"
                            
                            # Validate it's a reasonable price (between €1 and €9999)
                            if euros and 1 <= int(euros) <= 9999:
                                if cents and len(cents) == 1:
                                    cents = cents + "0"  # Convert "5" to "50"
                                elif not cents:
                                    cents = "00"
                                
                                price = f"€{euros}.{cents}"
                                break
                    
                    if price != "€0.00":
                        break
                
                # Strategy 2: Look for price patterns in the broader parent text
                if price == "€0.00":
                    all_text = parent.text_content()
                    
                    # Dutch price patterns commonly used on bol.com
                    price_patterns = [
                        r'(\d{1,4}),(\d{2})',           # "13,99" format
                        r'(\d{1,4}),-',                 # "169,-" format  
                        r'€\s*(\d{1,4})[,.](\d{2})',   # "€13,99" or "€13.99"
                        r'€\s*(\d{1,4})[-,]',          # "€169,-"
                        r'(\d{1,4})\s*euro',           # "169 euro"
                    ]
                    
                    for pattern in price_patterns:
                        matches = re.findall(pattern, all_text)
                        if matches:
                            for match in matches:
                                if isinstance(match, tuple):
                                    euros, cents = match[0], match[1] if len(match) > 1 else "00"
                                else:
                                    euros, cents = match, "00"
                                
                                # Validate reasonable price range
                                if euros and euros.isdigit() and 1 <= int(euros) <= 9999:
                                    if not cents or cents == "-":
                                        cents = "00"
                                    elif len(cents) == 1:
                                        cents = cents + "0"
                                    
                                    price = f"€{euros}.{cents}"
                                    break
                            
                            if price != "€0.00":
                                break
                
                # Look for stock status indicators
                stock_elements = parent.xpath('.//text()[contains(., "voorraad") or contains(., "leverbaar")]')
                for stock_text in stock_elements:
                    stock_lower = str(stock_text).lower()
                    if 'niet leverbaar' in stock_lower or 'uitverkocht' in stock_lower:
                        stock_status = StockStatus.OUT_OF_STOCK.value
                        break
                    elif 'op voorraad' in stock_lower or 'pre-order' in stock_lower:
                        stock_status = StockStatus.IN_STOCK.value
                        break
            
            return price, stock_status
            
        except Exception as e:
            self.logger.error(f"Error extracting price/stock for {product_id}: {e}")
            return price, stock_status
    
    # Replace the original method with the parallel version
    async def monitor_wishlist(self, wishlist_url: str) -> List[ProductData]:
        """Ultra-fast wishlist monitoring with parallel processing."""
        start_time = time.time()
        self.logger.info(f"Monitoring wishlist: {wishlist_url}")
        
        # Fetch page (this is already optimized)
        html_content = await self._fetch_page(wishlist_url)
        if not html_content:
            self.logger.error(f"Failed to fetch wishlist: {wishlist_url}")
            return []
        
        # Parse products in parallel (NEW: ultra-fast parallel processing)
        products = await self._parse_wishlist_products_parallel(html_content, wishlist_url)
        
        # Apply price threshold filtering to detect third-party sellers
        filtered_products = self._filter_products_by_price_thresholds(products)
        
        elapsed = time.time() - start_time
        self.logger.info(f"ULTRA SPEED: Wishlist monitoring completed in {elapsed:.3f}s for {len(filtered_products)} products")
        
        return filtered_products


    def _filter_products_by_price_thresholds(self, products: List[ProductData]) -> List[ProductData]:
        """Filter products based on price thresholds to detect third-party sellers."""
        try:
            # Get all price thresholds
            thresholds = self.price_threshold_repo.get_thresholds_dict()
            
            if not thresholds:
                # No thresholds configured, return all products
                return products
            
            filtered_products = []
            
            for product in products:
                # Skip out-of-stock products (they have €0.00 price)
                if product.stock_status != StockStatus.IN_STOCK.value:
                    filtered_products.append(product)
                    continue
                
                # Parse product price
                try:
                    price_str = product.price.replace('€', '').replace(',', '.')
                    product_price = float(price_str)
                except (ValueError, AttributeError):
                    # If we can't parse the price, include the product
                    filtered_products.append(product)
                    continue
                
                # Check if product matches any threshold keyword
                product_matches_threshold = False
                for keyword, max_price in thresholds.items():
                    # Case-insensitive keyword matching in product title
                    if keyword.lower() in product.title.lower():
                        if product_price <= max_price:
                            # Price is within threshold, include product
                            filtered_products.append(product)
                            self.logger.debug(f"Product '{product.title}' (€{product_price}) matches threshold '{keyword}' (€{max_price}) - INCLUDED")
                        else:
                            # Price exceeds threshold, likely third-party seller
                            self.logger.info(f"🚫 FILTERED: '{product.title}' (€{product_price}) exceeds threshold '{keyword}' (€{max_price}) - likely third-party seller")
                        product_matches_threshold = True
                        break
                
                # If product doesn't match any threshold, include it
                if not product_matches_threshold:
                    filtered_products.append(product)
            
            if len(filtered_products) != len(products):
                self.logger.info(f"Price threshold filtering: {len(products)} -> {len(filtered_products)} products (filtered {len(products) - len(filtered_products)} likely third-party sellers)")
            
            return filtered_products
            
        except Exception as e:
            self.logger.error(f"Error filtering products by price thresholds: {e}")
            # On error, return all products to avoid breaking monitoring
            return products

    def register_stock_change_callback(self, callback) -> None:
        """Register a callback function for stock changes."""
        self.stock_change_callbacks.append(callback)
        self.logger.info(f"Registered stock change callback: {callback.__name__}")
