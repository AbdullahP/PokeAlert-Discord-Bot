"""
Integration between monitoring engine and notification service.
"""
import logging
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..models.product_data import (
    ProductData, StockChange, Notification, NotificationStyle,
    StockStatus
)
from ..services.notification_service import NotificationService
from ..database.repository import ProductRepository
from ..database.notification_repository import NotificationRepository
from ..utils.notification_filter import notification_filter


class MonitoringNotificationIntegration:
    """Integration between monitoring engine and notification service."""
    
    def __init__(self, notification_service: NotificationService):
        """Initialize integration."""
        self.notification_service = notification_service
        self.product_repo = ProductRepository()
        self.notification_repo = NotificationRepository()
        self.logger = logging.getLogger(__name__)
        
        # Notification style cache
        self.style_cache = {}
    
    async def handle_stock_change(self, product: ProductData, change: StockChange) -> None:
        """
        Handle stock change event by sending appropriate notifications.
        Only notifies when products come IN STOCK.
        """
        try:
            # Check if we should send a notification (only for IN STOCK)
            if not notification_filter.should_send_notification(
                product.product_id, 
                change.previous_status, 
                change.current_status
            ):
                return
            
            # Get product configuration
            product_config = await self.product_repo.get_product(product.product_id)
            
            if not product_config:
                self.logger.warning(f"Product config not found for {product.product_id}")
                return
                
            # Check notification cooldown
            if not await self.notification_service.should_send_notification(product.product_id):
                self.logger.info(f"Notification for {product.title} skipped due to service cooldown")
                return
            
            # Get notification style for product
            style = await self._get_notification_style(product.product_id)
            
            # Create IN STOCK notification with dynamic role pinging
            await self._handle_in_stock_notification(product, change, product_config, style)
                
        except Exception as e:
            self.logger.error(f"Error handling stock change: {e}")
    
    async def _find_matching_roles(self, product_title: str, guild_id: int) -> List[str]:
        """
        Find Discord roles that match keywords from the product title.
        
        Args:
            product_title: The product title to extract keywords from
            guild_id: The Discord guild ID to search for roles
            
        Returns:
            List of role mentions that match the product title
        """
        try:
            # Get the Discord client from notification service
            discord_client = self.notification_service.discord_client
            guild = discord_client.get_guild(guild_id)
            
            if not guild:
                self.logger.warning(f"Guild {guild_id} not found")
                return []
            
            # Extract keywords from product title
            keywords = self._extract_keywords_from_title(product_title)
            
            matching_roles = []
            
            # Search for roles that match any of the keywords
            for role in guild.roles:
                # Skip @everyone and managed roles
                if role.name == "@everyone" or role.managed:
                    continue
                    
                # Check if role name matches any keyword (case-insensitive)
                role_name_lower = role.name.lower()
                for keyword in keywords:
                    if keyword.lower() in role_name_lower or role_name_lower in keyword.lower():
                        matching_roles.append(f"<@&{role.id}>")
                        self.logger.info(f"Found matching role: {role.name} for keyword: {keyword}")
                        break  # Don't add the same role multiple times
            
            return matching_roles
            
        except Exception as e:
            self.logger.error(f"Error finding matching roles: {e}")
            return []
    
    def _extract_keywords_from_title(self, title: str) -> List[str]:
        """
        Extract relevant keywords from product title for role matching.
        
        Args:
            title: The product title
            
        Returns:
            List of keywords to search for in role names
        """
        # Common keywords to look for in Pokemon product titles
        keywords = []
        
        # Split title into words and clean them
        words = title.replace("-", " ").replace("_", " ").split()
        
        # Look for specific Pokemon set names and product types
        pokemon_sets = [
            "Surging Sparks", "Prismatic Evolutions", "Temporal Forces", 
            "Twilight Masquerade", "Shrouded Fable", "Stellar Crown",
            "Paldean Fates", "Paradox Rift", "Obsidian Flames",
            "Paldea Evolved", "Scarlet & Violet", "Crown Zenith",
            "Silver Tempest", "Lost Origin", "Astral Radiance",
            "Brilliant Stars", "Fusion Strike", "Evolving Skies",
            "Chilling Reign", "Battle Styles", "Shining Fates",
            "Vivid Voltage", "Champion's Path", "Darkness Ablaze",
            "Rebel Clash", "Sword & Shield", "Cosmic Eclipse",
            "Hidden Fates", "Unified Minds", "Unbroken Bonds",
            "Team Up", "Lost Thunder", "Dragon Majesty",
            "Celestial Storm", "Forbidden Light", "Ultra Prism",
            "Crimson Invasion", "Shining Legends", "Burning Shadows",
            "Guardians Rising", "Sun & Moon", "Evolutions",
            "Steam Siege", "Fates Collide", "Generations",
            "BREAKpoint", "BREAKthrough", "Ancient Origins",
            "Roaring Skies", "Double Crisis", "Primal Clash",
            "Phantom Forces", "Furious Fists", "Flashfire",
            "XY", "Legendary Treasures", "Plasma Blast",
            "Plasma Freeze", "Plasma Storm", "Boundaries Crossed",
            "Dragon Vault", "Dragons Exalted", "Dark Explorers",
            "Next Destinies", "Noble Victories", "Emerging Powers",
            "Black & White"
        ]
        
        product_types = [
            "Elite Trainer Box", "ETB", "Booster Box", "Booster Pack",
            "Booster Bundle", "Mini Tin", "Collection Box", "Premium Collection",
            "Battle Deck", "Theme Deck", "Starter Deck", "Build & Battle",
            "Tin", "Box", "Bundle", "Blister", "Display", "Case"
        ]
        
        # Check for multi-word set names first
        title_lower = title.lower()
        for pokemon_set in pokemon_sets:
            if pokemon_set.lower() in title_lower:
                keywords.append(pokemon_set)
        
        # Check for product types
        for product_type in product_types:
            if product_type.lower() in title_lower:
                keywords.append(product_type)
        
        # Add individual significant words (length > 3, not common words)
        common_words = {
            "pokemon", "pokémon", "kaarten", "trading", "cards", "card",
            "the", "and", "with", "for", "from", "pack", "packs"
        }
        
        for word in words:
            clean_word = word.strip("()[]{}.,!?-_").lower()
            if len(clean_word) > 3 and clean_word not in common_words:
                # Capitalize first letter for better matching
                keywords.append(clean_word.capitalize())
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for keyword in keywords:
            if keyword.lower() not in seen:
                seen.add(keyword.lower())
                unique_keywords.append(keyword)
        
        return unique_keywords[:5]  # Limit to top 5 keywords to avoid spam

    async def _handle_in_stock_notification(self, product: ProductData, change: StockChange, 
                                          product_config: Any, style: Optional[NotificationStyle]) -> None:
        """Handle IN STOCK notification with dynamic role mention."""
        try:
            # Create notification embed
            embed = await self.notification_service.create_styled_notification(product, change, style)
            
            # Find matching roles based on product title
            dynamic_roles = await self._find_matching_roles(product.title, product_config.guild_id)
            
            # Combine configured role mentions with dynamic roles
            configured_roles = getattr(product_config, 'role_mentions', [])
            if isinstance(configured_roles, str):
                configured_roles = [configured_roles] if configured_roles else []
            
            # Merge all role mentions (remove duplicates)
            all_roles = list(set(configured_roles + dynamic_roles))
            
            # If no roles found, don't ping anyone (avoid @everyone spam)
            if not all_roles:
                self.logger.info(f"No matching roles found for '{product.title}', sending without mentions")
            else:
                self.logger.info(f"Found {len(all_roles)} role(s) to mention for '{product.title}': {all_roles}")
            
            # Create notification object with role mentions
            notification = Notification(
                product_id=product.product_id,
                channel_id=product_config.channel_id,
                embed_data=embed.to_dict(),
                role_mentions=all_roles,
                timestamp=datetime.utcnow(),
                product_url=product.product_url,
                uncached_url=product.uncached_url,
                retry_count=0,
                max_retries=3
            )
            
            # Queue for immediate delivery
            await self.notification_service.queue_notification(notification)
            self.logger.info(f"🔔 IN STOCK notification queued for {product.title}")
            
        except Exception as e:
            self.logger.error(f"Error handling IN STOCK notification: {e}")
    async def _handle_status_change(self, product: ProductData, change: StockChange, 
                                   product_config: Any, style: Optional[NotificationStyle]) -> None:
        """Handle stock status change notification."""
        try:
            # Create notification with high priority
            embed = await self.notification_service.create_styled_notification(product, change, style)
            
            # Create notification object
            notification = Notification(
                product_id=product.product_id,
                channel_id=product_config.channel_id,
                embed_data=embed.to_dict(),
                role_mentions=product_config.role_mentions,
                timestamp=datetime.utcnow(),
                priority=1,  # High priority for stock changes
                style=style
            )
            
            # Queue for immediate delivery
            await self.notification_service.queue_notification(notification)
            self.logger.info(f"Stock change notification queued for {product.title}")
        except Exception as e:
            self.logger.error(f"Error handling status change notification: {e}")
    
    async def _handle_price_change(self, product: ProductData, change: StockChange,
                                  product_config: Any, style: Optional[NotificationStyle]) -> None:
        """Handle price change notification."""
        try:
            # Check if price change is significant enough to notify
            if not change.price_change:
                return
                
            # Create price change notification with medium priority
            notification = await self.notification_service.create_price_change_notification(
                product, 
                change.price_change,
                product_config.channel_id,
                product_config.role_mentions,
                style
            )
            
            # Check if we should batch price change notifications
            batch_window = self.notification_service.config_manager.get('notifications.batch_window', 60)
            if batch_window > 0:
                # Create or get existing batch for this channel
                batch_id = await self._get_or_create_batch(product_config.channel_id, batch_window)
                
                # Add to batch
                await self.notification_service.add_to_batch(batch_id, notification)
                self.logger.info(f"Price change notification added to batch {batch_id} for {product.title}")
            else:
                # Queue for immediate delivery
                await self.notification_service.queue_notification(notification)
                self.logger.info(f"Price change notification queued for {product.title}")
        except Exception as e:
            self.logger.error(f"Error handling price change notification: {e}")
    
    async def _get_notification_style(self, product_id: str) -> Optional[NotificationStyle]:
        """Get notification style for a product."""
        # Check cache first
        if product_id in self.style_cache:
            return self.style_cache[product_id]
            
        # Get from database
        style_info = await self.notification_repo.get_product_style(product_id)
        
        if style_info:
            _, style = style_info
            self.style_cache[product_id] = style
            return style
            
        return None
    
    async def _get_or_create_batch(self, channel_id: int, batch_window: int) -> str:
        """Get existing batch or create a new one for the channel."""
        # Check if there's an active batch for this channel
        for batch_id, batch_info in self.notification_service.batch_queue.items():
            if (batch_info["channel_id"] == channel_id and 
                not batch_info["processing"] and
                (datetime.utcnow() - batch_info["created_at"]).total_seconds() < batch_info["window"]):
                return batch_id
                
        # Create new batch
        return await self.notification_service.create_notification_batch(channel_id, batch_window)
    
    async def register_with_monitoring_engine(self, monitoring_engine) -> None:
        """Register callback with monitoring engine."""
        monitoring_engine.register_stock_change_callback(self.handle_stock_change)
        self.logger.info("Registered stock change callback with monitoring engine")
        
    async def process_pending_notifications(self) -> None:
        """Process any pending notifications from previous runs."""
        try:
            # Get pending stock changes that need notifications
            pending_changes = self.notification_repo.get_pending_scheduled_notifications()
            
            # Check if it's a coroutine and await it
            if hasattr(pending_changes, '__await__'):
                pending_changes = await pending_changes
            
            if not pending_changes:
                self.logger.info("No pending notifications found")
                return
                
            self.logger.info(f"Processing {len(pending_changes)} pending notifications")
            
            # Process each pending notification
            for notification in pending_changes:
                try:
                    # Queue notification for delivery
                    await self.notification_service.queue_notification(notification)
                    
                    # Mark as processed
                    await self.notification_repo.mark_scheduled_notification_processed(notification.notification_id)
                except Exception as e:
                    self.logger.error(f"Error processing pending notification {notification.notification_id}: {e}")
            
            self.logger.info("Finished processing pending notifications")
        except Exception as e:
            self.logger.error(f"Error processing pending notifications: {e}")