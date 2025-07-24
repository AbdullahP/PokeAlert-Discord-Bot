"""
Initial status notification service for showing current state of all monitored products.
"""
import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime

from ..models.product_data import ProductData, StockChange
from ..services.notification_service import NotificationService
from ..services.product_manager import ProductManager
from ..services.monitoring_engine import MonitoringEngine


class InitialStatusNotifier:
    """Service for sending initial status notifications on bot startup."""
    
    def __init__(self, notification_service: NotificationService, 
                 product_manager: ProductManager, 
                 monitoring_engine: MonitoringEngine):
        """Initialize the initial status notifier."""
        self.notification_service = notification_service
        self.product_manager = product_manager
        self.monitoring_engine = monitoring_engine
        self.logger = logging.getLogger(__name__)
    
    async def send_initial_status_notifications(self) -> None:
        """Send initial status notifications for all monitored products."""
        self.logger.info("🚀 Sending initial status notifications for all monitored products...")
        
        try:
            # Get all monitored products
            product_configs = await self.product_manager.get_all_active_products()
            
            if not product_configs:
                self.logger.info("No products are currently being monitored")
                return
            
            self.logger.info(f"Found {len(product_configs)} products to check initial status")
            
            # Check current status of each product
            for config in product_configs:
                try:
                    await self._send_product_initial_status(config)
                    # Small delay to avoid overwhelming Discord
                    await asyncio.sleep(0.5)
                except Exception as e:
                    self.logger.error(f"Error sending initial status for product {config.product_id}: {e}")
            
            self.logger.info("✅ Initial status notifications completed")
            
        except Exception as e:
            self.logger.error(f"Error sending initial status notifications: {e}")
    
    async def _send_product_initial_status(self, config) -> None:
        """Send initial status notification for a single product."""
        try:
            self.logger.info(f"📊 Checking initial status for product: {config.url}")
            
            # Get current product data by scraping
            # Handle both enum and string values for url_type
            url_type_value = config.url_type.value if hasattr(config.url_type, 'value') else config.url_type
            
            # Check for wishlist (case insensitive)
            if url_type_value.upper() == "WISHLIST":
                self.logger.info(f"🔍 Processing wishlist with {config.url}")
                products = await self.monitoring_engine.monitor_wishlist(config.url)
                if products:
                    in_stock_count = sum(1 for p in products if p.stock_status == "In Stock")
                    out_of_stock_count = len(products) - in_stock_count
                    self.logger.info(f"📦 Found {len(products)} products in wishlist: {in_stock_count} in stock, {out_of_stock_count} out of stock")
                    self.logger.info(f"📢 Will send initial notifications for {in_stock_count} in-stock products only")
                    
                    # For wishlist, send status for each product (but only in-stock ones will actually send)
                    for i, product in enumerate(products, 1):
                        self.logger.info(f"📊 Processing product {i}/{len(products)}: {product.title}")
                        await self._create_and_send_initial_notification(product, config)
                        await asyncio.sleep(0.5)  # Small delay between products
                else:
                    self.logger.warning("No products found in wishlist")
            else:
                # Single product
                self.logger.info(f"🔍 Processing single product: {config.url}")
                product = await self.monitoring_engine.monitor_product(config.url)
                await self._create_and_send_initial_notification(product, config)
                
        except Exception as e:
            self.logger.error(f"Error checking initial status for {config.url}: {e}")
            # Send error notification
            await self._send_error_notification(config, str(e))
    
    async def _create_and_send_initial_notification(self, product: ProductData, config) -> None:
        """Create and send an initial status notification."""
        try:
            # Only send initial notifications for products that are In Stock
            if product.stock_status != "In Stock":
                self.logger.info(f"⏭️ Skipping initial notification for out-of-stock product: {product.title} - {product.stock_status}")
                return
            
            # Create a "status check" stock change to trigger notification
            initial_change = StockChange(
                product_id=product.product_id,
                previous_status="Checking...",
                current_status=product.stock_status,
                timestamp=datetime.utcnow()
            )
            
            # Find dynamic roles based on product title
            dynamic_roles = await self._find_matching_roles(product.title, config.guild_id)
            
            # Combine configured role mentions with dynamic roles
            configured_roles = getattr(config, 'role_mentions', [])
            if isinstance(configured_roles, str):
                configured_roles = [configured_roles] if configured_roles else []
            
            # Merge all role mentions (remove duplicates)
            all_roles = list(set(configured_roles + dynamic_roles))
            
            # Log role finding results
            if not all_roles:
                self.logger.info(f"No matching roles found for '{product.title}', sending without mentions")
            else:
                self.logger.info(f"Found {len(all_roles)} role(s) to mention for '{product.title}': {all_roles}")
            
            # Use the notification service's create_and_queue_notification method
            # This will ensure proper embed creation and button handling
            await self.notification_service.create_and_queue_notification(
                product=product,
                change=initial_change,
                channel_id=config.channel_id,
                role_mentions=all_roles  # Use dynamic + configured roles
            )
            
            self.logger.info(f"✅ Sent initial status for IN STOCK product: {product.title} - {product.stock_status}")
            
        except Exception as e:
            self.logger.error(f"Error creating initial notification for {product.title}: {e}")
    
    async def _create_initial_status_embed(self, product: ProductData, change: StockChange):
        """Create a custom embed for initial status notification matching the desired format."""
        from discord import Embed, Color
        
        # Determine display status - treat Pre-order as In Stock since it's purchasable
        display_status = "In Stock" if product.stock_status in ["In Stock", "Pre-order"] else product.stock_status
        
        # Use green color for In Stock and Pre-order (both purchasable)
        if product.stock_status in ["In Stock", "Pre-order"]:
            color = Color.green()
        elif product.stock_status == "Out of Stock":
            color = Color.red()
        else:
            color = Color.light_grey()
        
        # Create embed with clean format like the example
        embed = Embed(
            title=product.title,
            color=color,
            timestamp=datetime.utcnow()
        )
        
        # Create description with price, status, and website info
        description_parts = []
        
        # Add price
        if product.price and product.price != "€0.00":
            # Clean up price formatting
            clean_price = product.price.replace('\n', '').replace('  ', '').strip()
            if not clean_price.startswith('€'):
                clean_price = f"€{clean_price}"
            description_parts.append(f"**Price:** {clean_price}")
        
        # Add status
        description_parts.append(f"**Status:** {display_status}")
        
        # Add website and timestamp
        timestamp_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S:%f")[:-3]  # Format like your example
        description_parts.append(f"**Website:** bol.com | **Last updated:** {timestamp_str}")
        
        embed.description = "\n".join(description_parts)
        
        # Add product image as thumbnail (right side like in your example)
        if product.image_url:
            embed.set_thumbnail(url=product.image_url)
        
        return embed
    
    async def _send_error_notification(self, config, error_message: str) -> None:
        """Send error notification for products that couldn't be checked."""
        try:
            from discord import Embed, Color
            
            embed = Embed(
                title="⚠️ Initial Status Check Error",
                description=f"Could not check initial status for monitored product",
                color=Color.red(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="🔗 Product URL",
                value=config.url,
                inline=False
            )
            
            embed.add_field(
                name="❌ Error",
                value=error_message[:500] + "..." if len(error_message) > 500 else error_message,
                inline=False
            )
            
            embed.set_footer(text="🤖 Pokemon Monitor Bot - Status Check Error")
            
            await self.notification_service.send_notification(
                channel_id=config.channel_id,
                embed=embed,
                mentions=[]
            )
            
        except Exception as e:
            self.logger.error(f"Error sending error notification: {e}")
    
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
            self.logger.info(f"Extracted keywords from '{product_title}': {keywords}")
            
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
                        self.logger.info(f"🎯 Found matching role: '{role.name}' (ID: {role.id}) for keyword: '{keyword}'")
                        break  # Don't add the same role multiple times
            
            if not matching_roles:
                self.logger.info(f"No matching roles found for keywords: {keywords}")
                # Log all available roles for debugging
                available_roles = [role.name for role in guild.roles if not role.managed and role.name != "@everyone"]
                self.logger.info(f"Available roles in guild: {available_roles}")
            
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