"""
Product management system for the Pokemon Discord Bot.
Handles CRUD operations, URL validation, and monitoring status tracking.
"""
import re
import logging
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse, parse_qs
from datetime import datetime

from ..models.interfaces import IProductManager
from ..models.product_data import (
    ProductConfig, ProductData, MonitoringStatus, 
    DashboardData, StockChange, URLType
)
from ..database.repository import (
    ProductRepository, ProductStatusRepository, 
    StockChangeRepository, MetricsRepository
)


class ProductManager(IProductManager):
    """Product management system with CRUD operations and validation."""
    
    def __init__(self, monitoring_engine=None, notification_service=None):
        """Initialize product manager with repositories."""
        self.logger = logging.getLogger(__name__)
        self.product_repo = ProductRepository()
        self.status_repo = ProductStatusRepository()
        self.change_repo = StockChangeRepository()
        self.metrics_repo = MetricsRepository()
        self.monitoring_engine = monitoring_engine
        self.notification_service = notification_service
        
        # URL validation patterns
        self.bol_product_pattern = re.compile(
            r'https?://www\.bol\.com/[a-z]{2}/[a-z]{2}/p/[^/]+/(\d+)/?'
        )
        self.bol_wishlist_pattern = re.compile(
            r'https?://www\.bol\.com/[a-z]{2}/[a-z]{2}/(verlanglijstje|rnwy/account/wenslijst)/([a-f0-9\-]+)/?'
        )
    
    async def add_product(self, url: str, channel_id: int, guild_id: int, monitoring_interval: int = None) -> str:
        """
        Add a product for monitoring.
        
        Args:
            url: Product or wishlist URL to monitor
            channel_id: Discord channel ID for notifications
            guild_id: Discord guild ID
            monitoring_interval: Optional monitoring interval in seconds
            
        Returns:
            Product ID if successful, empty string if failed
            
        Requirements: 1.1, 1.2, 1.5
        """
        try:
            # Validate URL and determine type
            url_type, validated_url = self._validate_and_normalize_url(url)
            if not url_type:
                self.logger.error(f"Invalid URL format: {url}")
                return ""
            
            # Create product configuration
            config = ProductConfig.create_new(
                url=validated_url,
                url_type=url_type.value,
                channel_id=channel_id,
                guild_id=guild_id
            )
            
            # Set monitoring interval if provided
            if monitoring_interval is not None:
                config.monitoring_interval = monitoring_interval
            
            # Check for duplicate URLs in the same channel
            existing_products = await self.get_products_by_channel(channel_id)
            for existing in existing_products:
                if existing.url == validated_url:
                    self.logger.warning(f"Product already exists in channel: {validated_url}")
                    return existing.product_id
            
            # Add to database
            if self.product_repo.add_product(config):
                self.logger.info(f"Added product {config.product_id} for monitoring: {validated_url}")
                
                # Start monitoring the new product
                await self.add_product_to_monitoring(config.product_id)
                
                return config.product_id
            else:
                self.logger.error(f"Failed to add product to database: {validated_url}")
                return ""
                
        except Exception as e:
            self.logger.error(f"Error adding product: {e}")
            return ""
    
    async def remove_product(self, product_id: str) -> bool:
        """
        Remove a product from monitoring.
        
        Args:
            product_id: Product ID to remove
            
        Returns:
            True if successful, False otherwise
            
        Requirements: 2.2
        """
        try:
            # Verify product exists
            config = self.product_repo.get_product(product_id)
            if not config:
                self.logger.warning(f"Product not found for removal: {product_id}")
                return False
            
            # Remove from database (cascade will handle related records)
            if self.product_repo.delete_product(product_id):
                self.logger.info(f"Removed product {product_id} from monitoring")
                return True
            else:
                self.logger.error(f"Failed to remove product from database: {product_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error removing product: {e}")
            return False
    
    async def update_product(self, product_id: str, config: ProductConfig) -> bool:
        """
        Update product configuration.
        
        Args:
            product_id: Product ID to update
            config: New product configuration
            
        Returns:
            True if successful, False otherwise
            
        Requirements: 2.1, 2.4
        """
        try:
            # Verify product exists
            existing_config = self.product_repo.get_product(product_id)
            if not existing_config:
                self.logger.warning(f"Product not found for update: {product_id}")
                return False
            
            # Validate new configuration
            if not config.validate():
                self.logger.error(f"Invalid product configuration: {config}")
                return False
            
            # Validate URL if changed
            if config.url != existing_config.url:
                url_type, validated_url = self._validate_and_normalize_url(config.url)
                if not url_type:
                    self.logger.error(f"Invalid URL format: {config.url}")
                    return False
                config.url = validated_url
                config.url_type = url_type.value
            
            # Update in database
            if self.product_repo.update_product(config):
                self.logger.info(f"Updated product configuration: {product_id}")
                return True
            else:
                self.logger.error(f"Failed to update product in database: {product_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating product: {e}")
            return False
    
    async def get_products_by_channel(self, channel_id: int) -> List[ProductConfig]:
        """
        Get all products assigned to a channel.
        
        Args:
            channel_id: Discord channel ID
            
        Returns:
            List of product configurations for the channel
            
        Requirements: 2.1
        """
        try:
            products = self.product_repo.get_products_by_channel(channel_id)
            self.logger.debug(f"Retrieved {len(products)} products for channel {channel_id}")
            return products
        except Exception as e:
            self.logger.error(f"Error getting products by channel: {e}")
            return []
    
    async def get_products_by_guild(self, guild_id: int) -> List[ProductConfig]:
        """
        Get all products for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            List of product configurations for the guild
        """
        try:
            products = self.product_repo.get_products_by_guild(guild_id)
            self.logger.debug(f"Retrieved {len(products)} products for guild {guild_id}")
            return products
        except Exception as e:
            self.logger.error(f"Error getting products by guild: {e}")
            return []
    
    async def get_all_active_products(self) -> List[ProductConfig]:
        """
        Get all active products for monitoring.
        
        Returns:
            List of all active product configurations
        """
        try:
            products = self.product_repo.get_all_active_products()
            self.logger.debug(f"Retrieved {len(products)} active products")
            return products
        except Exception as e:
            self.logger.error(f"Error getting active products: {e}")
            return []
    
    async def get_monitoring_status(self) -> Dict[str, MonitoringStatus]:
        """
        Get monitoring status for all products.
        
        Returns:
            Dictionary mapping product IDs to monitoring status
            
        Requirements: 5.1, 5.2
        """
        try:
            status_dict = {}
            active_products = await self.get_all_active_products()
            
            for product in active_products:
                status = self.metrics_repo.get_monitoring_status(product.product_id)
                status_dict[product.product_id] = status
            
            self.logger.debug(f"Retrieved monitoring status for {len(status_dict)} products")
            return status_dict
        except Exception as e:
            self.logger.error(f"Error getting monitoring status: {e}")
            return {}
    
    async def get_product_config(self, product_id: str) -> Optional[ProductConfig]:
        """
        Get product configuration by ID.
        
        Args:
            product_id: Product ID
            
        Returns:
            Product configuration if found, None otherwise
        """
        try:
            return self.product_repo.get_product(product_id)
        except Exception as e:
            self.logger.error(f"Error getting product config: {e}")
            return None
    
    async def get_dashboard_data(self, guild_id: int) -> DashboardData:
        """
        Get dashboard data for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Dashboard data with metrics and recent changes
            
        Requirements: 5.1, 5.2, 5.5
        """
        try:
            # Get product counts
            guild_products = await self.get_products_by_guild(guild_id)
            total_products = len(guild_products)
            active_products = len([p for p in guild_products if p.is_active])
            
            # Get total checks today
            total_checks_today = self.metrics_repo.get_total_checks_today()
            
            # Calculate overall success rate
            success_rate = await self._calculate_guild_success_rate(guild_id)
            
            # Get recent stock changes
            recent_changes = self.change_repo.get_recent_changes(hours=24)
            guild_changes = [
                change for change in recent_changes
                if any(p.product_id == change.product_id for p in guild_products)
            ]
            
            # Get error summary
            error_summary = await self._get_error_summary(guild_id)
            
            return DashboardData(
                total_products=total_products,
                active_products=active_products,
                total_checks_today=total_checks_today,
                success_rate=success_rate,
                recent_stock_changes=guild_changes[:10],  # Last 10 changes
                error_summary=error_summary
            )
        except Exception as e:
            self.logger.error(f"Error getting dashboard data: {e}")
            return DashboardData(
                total_products=0,
                active_products=0,
                total_checks_today=0,
                success_rate=0.0,
                recent_stock_changes=[],
                error_summary={}
            )
    
    async def set_product_active(self, product_id: str, is_active: bool) -> bool:
        """
        Set product active/inactive status.
        
        Args:
            product_id: Product ID
            is_active: Active status
            
        Returns:
            True if successful, False otherwise
        """
        try:
            config = self.product_repo.get_product(product_id)
            if not config:
                return False
            
            config.is_active = is_active
            config.updated_at = datetime.utcnow()
            
            return self.product_repo.update_product(config)
        except Exception as e:
            self.logger.error(f"Error setting product active status: {e}")
            return False
    
    async def update_channel_assignment(self, product_id: str, new_channel_id: int) -> bool:
        """
        Update channel assignment for a product.
        
        Args:
            product_id: Product ID
            new_channel_id: New Discord channel ID
            
        Returns:
            True if successful, False otherwise
            
        Requirements: 2.1, 2.3
        """
        try:
            config = self.product_repo.get_product(product_id)
            if not config:
                return False
            
            config.channel_id = new_channel_id
            config.updated_at = datetime.utcnow()
            
            return self.product_repo.update_product(config)
        except Exception as e:
            self.logger.error(f"Error updating channel assignment: {e}")
            return False
    
    async def update_role_mentions(self, product_id: str, role_mentions: List[str]) -> bool:
        """
        Update role mentions for a product.
        
        Args:
            product_id: Product ID
            role_mentions: List of role IDs to mention
            
        Returns:
            True if successful, False otherwise
        """
        try:
            config = self.product_repo.get_product(product_id)
            if not config:
                return False
            
            config.role_mentions = role_mentions
            config.updated_at = datetime.utcnow()
            
            return self.product_repo.update_product(config)
        except Exception as e:
            self.logger.error(f"Error updating role mentions: {e}")
            return False
    
    def _validate_and_normalize_url(self, url: str) -> Tuple[Optional[URLType], str]:
        """
        Validate and normalize a bol.com URL.
        
        Args:
            url: URL to validate
            
        Returns:
            Tuple of (URLType, normalized_url) or (None, url) if invalid
            
        Requirements: 1.1, 1.2
        """
        try:
            # Clean up URL
            url = url.strip()
            
            # Check for product URL
            product_match = self.bol_product_pattern.match(url)
            if product_match:
                # Normalize product URL
                product_id = product_match.group(1)
                normalized_url = f"https://www.bol.com/nl/nl/p/{product_id}/"
                return URLType.PRODUCT, normalized_url
            
            # Check for wishlist URL
            wishlist_match = self.bol_wishlist_pattern.match(url)
            if wishlist_match:
                # Normalize wishlist URL - use the original format for verlanglijstje
                wishlist_type = wishlist_match.group(1)
                wishlist_id = wishlist_match.group(2)
                if wishlist_type == "verlanglijstje":
                    normalized_url = f"https://www.bol.com/nl/nl/verlanglijstje/{wishlist_id}/"
                else:
                    normalized_url = f"https://www.bol.com/nl/nl/rnwy/account/wenslijst/{wishlist_id}/"
                return URLType.WISHLIST, normalized_url
            
            # Check if it's a generic bol.com URL that might be valid
            parsed = urlparse(url)
            if parsed.netloc == 'www.bol.com' and '/p/' in parsed.path:
                # Try to extract product ID from path
                path_parts = parsed.path.split('/')
                if len(path_parts) >= 4 and path_parts[-2].isdigit():
                    product_id = path_parts[-2]
                    normalized_url = f"https://www.bol.com/nl/nl/p/{product_id}/"
                    return URLType.PRODUCT, normalized_url
            
            self.logger.warning(f"URL does not match bol.com patterns: {url}")
            return None, url
            
        except Exception as e:
            self.logger.error(f"Error validating URL: {e}")
            return None, url
    
    async def _calculate_guild_success_rate(self, guild_id: int) -> float:
        """Calculate overall success rate for a guild's products."""
        try:
            guild_products = await self.get_products_by_guild(guild_id)
            if not guild_products:
                return 0.0
            
            total_success_rate = 0.0
            product_count = 0
            
            for product in guild_products:
                status = self.metrics_repo.get_monitoring_status(product.product_id)
                total_success_rate += status.success_rate
                product_count += 1
            
            return total_success_rate / product_count if product_count > 0 else 0.0
        except Exception as e:
            self.logger.error(f"Error calculating guild success rate: {e}")
            return 0.0
    
    async def _get_error_summary(self, guild_id: int) -> Dict[str, int]:
        """Get error summary for a guild's products."""
        try:
            guild_products = await self.get_products_by_guild(guild_id)
            error_summary = {}
            
            for product in guild_products:
                status = self.metrics_repo.get_monitoring_status(product.product_id)
                if status.error_count > 0 and status.last_error:
                    error_type = status.last_error.split(':')[0] if ':' in status.last_error else 'Unknown'
                    error_summary[error_type] = error_summary.get(error_type, 0) + 1
            
            return error_summary
        except Exception as e:
            self.logger.error(f"Error getting error summary: {e}")
            return {}
    
    def validate_url(self, url: str) -> bool:
        """
        Validate if a URL is a supported bol.com URL.
        
        Args:
            url: URL to validate
            
        Returns:
            True if valid, False otherwise
        """
        url_type, _ = self._validate_and_normalize_url(url)
        return url_type is not None
    
    def extract_product_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract product ID from a bol.com URL.
        
        Args:
            url: bol.com URL
            
        Returns:
            Product ID if found, None otherwise
        """
        try:
            product_match = self.bol_product_pattern.match(url)
            if product_match:
                return product_match.group(1)
            
            # Try generic extraction
            parsed = urlparse(url)
            if parsed.netloc == 'www.bol.com' and '/p/' in parsed.path:
                path_parts = parsed.path.split('/')
                if len(path_parts) >= 4 and path_parts[-2].isdigit():
                    return path_parts[-2]
            
            return None
        except Exception as e:
            self.logger.error(f"Error extracting product ID: {e}")
            return None
    
    def extract_wishlist_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract wishlist ID from a bol.com wishlist URL.
        
        Args:
            url: bol.com wishlist URL
            
        Returns:
            Wishlist ID if found, None otherwise
        """
        try:
            wishlist_match = self.bol_wishlist_pattern.match(url)
            if wishlist_match:
                return wishlist_match.group(2)  # Group 2 contains the wishlist ID
            return None
        except Exception as e:
            self.logger.error(f"Error extracting wishlist ID: {e}")
            return None
    
    def get_monitoring_interval_for_product(self, product_id: str) -> int:
        """
        Get monitoring interval for a product based on its URL domain.
        
        Args:
            product_id: Product ID
            
        Returns:
            Monitoring interval in seconds (default: 10)
        """
        try:
            from ..database.website_interval_repository import WebsiteIntervalRepository
            
            # Get product configuration
            config = self.product_repo.get_product(product_id)
            if not config:
                self.logger.warning(f"Product not found: {product_id}")
                return 10  # Default interval
            
            # Get interval for the product's URL domain
            website_repo = WebsiteIntervalRepository()
            interval = website_repo.get_interval_for_url(config.url, default_interval=10)
            
            self.logger.debug(f"Product {product_id} monitoring interval: {interval}s")
            return interval
            
        except Exception as e:
            self.logger.error(f"Error getting monitoring interval for product {product_id}: {e}")
            return 10  # Default interval
    
    def get_monitoring_interval_for_url(self, url: str) -> int:
        """
        Get monitoring interval for a URL based on its domain.
        
        Args:
            url: Product or wishlist URL
            
        Returns:
            Monitoring interval in seconds (default: 10)
        """
        try:
            from ..database.website_interval_repository import WebsiteIntervalRepository
            
            website_repo = WebsiteIntervalRepository()
            interval = website_repo.get_interval_for_url(url, default_interval=10)
            
            self.logger.debug(f"URL {url} monitoring interval: {interval}s")
            return interval
            
        except Exception as e:
            self.logger.error(f"Error getting monitoring interval for URL {url}: {e}")
            return 10  # Default interval
    
    async def add_product_to_monitoring(self, product_id: str) -> None:
        """Add a product to monitoring after it's been added to the database."""
        try:
            # Get the product config
            product = self.product_repo.get_product(product_id)
            if not product:
                self.logger.warning(f"Product {product_id} not found in database")
                return
                
            # Start monitoring this product if monitoring engine is available
            if self.monitoring_engine:
                self.logger.info(f"Adding new product to monitoring: {product.url}")
                await self.monitoring_engine.start_monitoring([product])
                
                # Send initial status notification for the new product
                if self.notification_service:
                    from .initial_status_notifier import InitialStatusNotifier
                    initial_status_notifier = InitialStatusNotifier(
                        self.notification_service,
                        self,
                        self.monitoring_engine
                    )
                    await initial_status_notifier._send_product_initial_status(product)
            else:
                self.logger.warning("Monitoring engine not available, product will be monitored on next restart")
                
        except Exception as e:
            self.logger.error(f"Error adding product {product_id} to monitoring: {e}")