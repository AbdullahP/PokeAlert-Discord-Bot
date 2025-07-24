"""
Base interfaces for the monitoring system components.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from datetime import datetime
from discord import Interaction, Embed

from .product_data import (
    ProductData, ProductConfig, StockChange, 
    MonitoringStatus, DashboardData, Notification,
    NotificationStyle, PriceChange, NotificationDeliveryStatus
)


class IMonitoringEngine(ABC):
    """Interface for monitoring engine implementations."""
    
    @abstractmethod
    async def monitor_wishlist(self, wishlist_url: str) -> List[ProductData]:
        """Monitor a wishlist URL and return product data."""
        pass
    
    @abstractmethod
    async def monitor_product(self, product_url: str) -> ProductData:
        """Monitor a single product URL and return product data."""
        pass
    
    @abstractmethod
    async def detect_stock_changes(self, products: List[ProductData]) -> List[StockChange]:
        """Detect stock changes from product data."""
        pass
    
    @abstractmethod
    async def start_monitoring(self, product_configs: List[ProductConfig]) -> None:
        """Start monitoring for given product configurations."""
        pass
    
    @abstractmethod
    async def stop_monitoring(self, product_id: str) -> None:
        """Stop monitoring for a specific product."""
        pass
    
    @abstractmethod
    def register_stock_change_callback(self, callback) -> None:
        """Register a callback function for stock changes."""
        pass


class IProductManager(ABC):
    """Interface for product management operations."""
    
    @abstractmethod
    async def add_product(self, url: str, channel_id: int, config: ProductConfig) -> str:
        """Add a product for monitoring."""
        pass
    
    @abstractmethod
    async def remove_product(self, product_id: str) -> bool:
        """Remove a product from monitoring."""
        pass
    
    @abstractmethod
    async def update_product(self, product_id: str, config: ProductConfig) -> bool:
        """Update product configuration."""
        pass
    
    @abstractmethod
    async def get_products_by_channel(self, channel_id: int) -> List[ProductConfig]:
        """Get all products assigned to a channel."""
        pass
    
    @abstractmethod
    async def get_monitoring_status(self) -> Dict[str, MonitoringStatus]:
        """Get monitoring status for all products."""
        pass


class IAdminManager(ABC):
    """Interface for admin management operations."""
    
    @abstractmethod
    async def validate_admin_permissions(self, user_id: int, guild_id: int) -> bool:
        """Validate if user has admin permissions."""
        pass
    
    @abstractmethod
    async def process_add_product_command(self, interaction: Interaction) -> None:
        """Process add product admin command."""
        pass
    
    @abstractmethod
    async def process_status_command(self, interaction: Interaction) -> None:
        """Process status admin command."""
        pass
    
    @abstractmethod
    async def get_dashboard_data(self, guild_id: int) -> DashboardData:
        """Get dashboard data for a guild."""
        pass


class INotificationService(ABC):
    """Interface for notification service operations."""
    
    @abstractmethod
    async def create_stock_notification(self, product: ProductData, change: StockChange) -> Embed:
        """Create a stock notification embed."""
        pass
    
    @abstractmethod
    async def send_notification(self, channel_id: int, embed: Embed, mentions: List[str]) -> bool:
        """Send a notification to a Discord channel."""
        pass
    
    @abstractmethod
    async def queue_notification(self, notification: Notification) -> None:
        """Queue a notification for delivery."""
        pass
    
    @abstractmethod
    async def process_notification_queue(self) -> None:
        """Process queued notifications."""
        pass
    
    @abstractmethod
    async def create_styled_notification(self, product: ProductData, change: StockChange, 
                                        style: Optional[NotificationStyle] = None) -> Embed:
        """Create a styled notification embed with customization options."""
        pass
    
    @abstractmethod
    async def create_price_change_notification(self, product: ProductData, price_change: PriceChange,
                                              channel_id: int, role_mentions: List[str] = None,
                                              style: Optional[NotificationStyle] = None) -> Notification:
        """Create a notification specifically for price changes."""
        pass
    
    @abstractmethod
    async def schedule_notification(self, notification: Notification, delay_seconds: int = 0) -> str:
        """Schedule a notification for future delivery."""
        pass
    
    @abstractmethod
    async def create_notification_batch(self, channel_id: int, batch_window: int = None) -> str:
        """Create a new notification batch for grouping multiple notifications."""
        pass
    
    @abstractmethod
    async def add_to_batch(self, batch_id: str, notification: Notification) -> bool:
        """Add a notification to an existing batch."""
        pass
    
    @abstractmethod
    async def get_delivery_status(self, notification_id: str) -> Optional[NotificationDeliveryStatus]:
        """Get delivery status for a notification."""
        pass
    
    @abstractmethod
    async def get_notification_history(self, product_id: str) -> List[NotificationDeliveryStatus]:
        """Get notification history for a product."""
        pass
    
    @abstractmethod
    async def should_send_notification(self, product_id: str) -> bool:
        """Check if a notification should be sent based on cooldown settings."""
        pass


class IDiscordBotClient(ABC):
    """Interface for Discord bot client operations."""
    
    @abstractmethod
    async def setup_commands(self) -> None:
        """Set up Discord slash commands."""
        pass
    
    @abstractmethod
    async def handle_admin_command(self, interaction: Interaction) -> None:
        """Handle admin commands."""
        pass
    
    @abstractmethod
    async def send_notification(self, channel_id: int, embed: Embed) -> bool:
        """Send notification to Discord channel."""
        pass
    
    @abstractmethod
    async def validate_permissions(self, user_id: int, guild_id: int) -> bool:
        """Validate user permissions."""
        pass


class IErrorHandler(ABC):
    """Interface for error handling operations."""
    
    @abstractmethod
    async def handle_network_error(self, error: Exception, product_id: str) -> None:
        """Handle network-related errors."""
        pass
    
    @abstractmethod
    async def handle_discord_error(self, error: Exception, notification: Notification) -> None:
        """Handle Discord API errors."""
        pass
    
    @abstractmethod
    async def handle_database_error(self, error: Exception, operation: str) -> None:
        """Handle database errors."""
        pass
    
    @abstractmethod
    async def handle_parsing_error(self, error: Exception, html_content: str) -> None:
        """Handle HTML parsing errors."""
        pass


class IConfigManager(ABC):
    """Interface for configuration management."""
    
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        pass
    
    @abstractmethod
    def load_config(self, config_path: str) -> None:
        """Load configuration from file."""
        pass
    
    @abstractmethod
    def save_config(self, config_path: str) -> None:
        """Save configuration to file."""
        pass