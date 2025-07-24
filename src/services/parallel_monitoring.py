"""
Parallel monitoring implementation for maximum speed.
"""
import asyncio
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
import re
from datetime import datetime

from ..models.product_data import ProductData, StockStatus
from ..models.interfaces import IMonitoringEngine

class ParallelMonitoring:
    """Parallel monitoring implementation for maximum speed."""
    
    def __init__(self, monitoring_engine: IMonitoringEngine):
        """Initialize with reference to the main monitoring engine."""
        self.monitoring_engine = monitoring_engine
        self.logger = logging.getLogger(__name__)
    
    async def monitor_wishlist_parallel(self, wishlist_url: str) -> List[ProductData]:
        """Monitor wishlist with parallel processing for maximum speed."""
        start_time = time.time()
        self.logger.info(f"ULTRA SPEED: Monitoring wishlist: {wishlist_url}")
        
        # Fetch page using the monitoring engine's method
        html_content = await self.monitoring_engine._fetch_page(wishlist_url)
        if not html_content:
            self.logger.error(f"Failed to fetch wishlist: {wishlist_url}")
            return []
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all product links
        product_links = soup.select('a[href*="/p/"]')
        self.logger.info(f"Found {len(product_links)} product links in wishlist")
        
        if not product_links:
            return []
        
        # Create tasks for parallel processing
        tasks = []
        processed_urls = set()
        
        for link in product_links:
            # Quick URL validation
            href = link.get('href', '')
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
            task = asyncio.create_task(self.monitoring_engine._fetch_page(clean_url))
            tasks.append((clean_url, task))
        
        # Execute all fetches in parallel
        products = []
        for url, task in tasks:
            try:
                html = await task
                if html:
                    # Process product HTML using the monitoring engine's method
                    product_data = await self.monitoring_engine._parse_product_html(html, url)
                    if product_data:
                        products.append(product_data)
            except Exception as e:
                self.logger.error(f"Error processing product {url}: {e}")
        
        elapsed = time.time() - start_time
        self.logger.info(f"ULTRA SPEED: Processed {len(products)} products in {elapsed:.3f}s")
        
        return products