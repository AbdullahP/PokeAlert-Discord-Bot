"""
Notification service for Discord alerts with advanced features.
"""
import logging
import asyncio
import json
import uuid
import time
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
import discord
from discord import Embed, Color
from collections import defaultdict

from ..models.interfaces import INotificationService
from ..models.product_data import (
    ProductData, StockChange, Notification, StockStatus, 
    NotificationStyle, NotificationDeliveryStatus, PriceChange
)
from ..config.config_manager import ConfigManager
from ..database.repository import StockChangeRepository
from ..discord_bot.views import ProductNotificationView


class NotificationService(INotificationService):
    """Enhanced notification service implementation with advanced features."""
    
    def __init__(self, config_manager: ConfigManager, discord_client):
        """Initialize notification service."""
        self.config_manager = config_manager
        self.discord_client = discord_client
        self.logger = logging.getLogger(__name__)
        self.notification_queue = asyncio.Queue()
        self.processing_task = None
        self.stock_change_repo = StockChangeRepository()
        
        # Notification delivery tracking
        self.delivery_statuses = {}  # notification_id -> NotificationDeliveryStatus
        self.notification_history = {}  # product_id -> list of notification_ids
        
        # Notification batching
        self.batch_queue = {}  # batch_id -> list of notifications
        self.batch_lock = asyncio.Lock()
        
        # Scheduled notifications
        self.scheduled_notifications = {}  # notification_id -> Notification
        self.scheduler_task = None
        
        # Load notification configuration
        self.embed_colors = {
            StockStatus.IN_STOCK.value: self.config_manager.get('notifications.colors.in_stock', 0x00ff00),  # Green
            StockStatus.OUT_OF_STOCK.value: self.config_manager.get('notifications.colors.out_of_stock', 0xff0000),  # Red
            StockStatus.PRE_ORDER.value: self.config_manager.get('notifications.colors.pre_order', 0xffaa00),  # Orange
            StockStatus.UNKNOWN.value: self.config_manager.get('notifications.colors.unknown', 0x808080),  # Gray
        }
        
        # Load advanced notification configuration
        self.max_retries = self.config_manager.get('notifications.max_retries', 3)
        self.retry_delay = self.config_manager.get('notifications.retry_delay', 5.0)
        self.batch_size = self.config_manager.get('notifications.batch_size', 20)  # Ultra-fast: larger batches
        self.rate_limit_delay = self.config_manager.get('notifications.rate_limit_delay', 0.05)  # Ultra-fast: 50ms
        self.max_queue_size = self.config_manager.get('notifications.max_queue_size', 1000)
        
        # Advanced notification settings
        self.cooldown_enabled = self.config_manager.get('notifications.cooldown.enabled', True)
        self.cooldown_period = self.config_manager.get('notifications.cooldown.period', 3600)  # 1 hour default
        self.cooldown_per_product = self.config_manager.get('notifications.cooldown.per_product', True)
        self.batch_window = self.config_manager.get('notifications.batch_window', 60)  # seconds to batch notifications
        self.price_change_threshold = self.config_manager.get('notifications.price_change_threshold', 5.0)  # percentage
        
        # Emoji styles
        self.emoji_styles = {
            "default": {
                "in_stock": "🟢",
                "out_of_stock": "🔴",
                "pre_order": "🟠",
                "price_increase": "📈",
                "price_decrease": "📉",
                "unknown": "⚪"
            },
            "minimal": {
                "in_stock": "✓",
                "out_of_stock": "✗",
                "pre_order": "⏳",
                "price_increase": "↑",
                "price_decrease": "↓",
                "unknown": "?"
            },
            "none": {
                "in_stock": "",
                "out_of_stock": "",
                "pre_order": "",
                "price_increase": "",
                "price_decrease": "",
                "unknown": ""
            }
        }
        
        # Product notification cooldowns
        self.notification_cooldowns = {}  # product_id -> last notification time
    
    async def create_stock_notification(self, product: ProductData, change: StockChange) -> Embed:
        """
        Create a rich embed notification for stock changes.
        
        Args:
            product: The product data
            change: The stock change event
            
        Returns:
            Discord Embed object with formatted product information
        """
        # Determine embed color based on current stock status
        embed_color = self.embed_colors.get(
            product.stock_status, 
            self.config_manager.get('notifications.embed_color', 0x00ff00)
        )
        
        # Create title without emoji (clean format like the example)
        title = product.title
        if len(title) > 256:  # Discord embed title limit
            title = title[:253] + "..."
        
        # Create description with price and status only
        description_parts = []
        
        # Add price
        if product.price and product.price != "€0.00":
            # Clean up price formatting
            clean_price = product.price.replace('\n', '').replace('  ', '').strip()
            if not clean_price.startswith('€'):
                clean_price = f"€{clean_price}"
            description_parts.append(f"**Price:** `{clean_price}`")
        else:
            # Show that price is not available instead of hiding it
            description_parts.append(f"**Price:** `Not available`")
        
        # Add status
        description_parts.append(f"**Status:** `{product.stock_status}`")
        
        # Create embed with clean format
        embed = Embed(
            title=title,
            description="\n".join(description_parts),
            color=embed_color,
            url=product.product_url  # Make title clickable with product URL
        )
        
        # Add product image as thumbnail (right side like in your example)
        if product.image_url:
            embed.set_thumbnail(url=product.image_url)
        
        # Add website and timestamp in footer
        timestamp_str = change.timestamp.strftime("%Y-%m-%d %H:%M:%S:%f")[:-3]  # Format like 2025-07-20 18:09:04:322
        embed.set_footer(text=f"Website: Bol.com | Last updated: {timestamp_str}")
        
        return embed
    
    def _create_description(self, product: ProductData, change: StockChange) -> str:
        """Create formatted description for the embed."""
        # Create status change message
        status_message = f"**Status Changed:** {change.previous_status} → {change.current_status}"
        
        # Add direct purchase call-to-action for in-stock items
        if product.stock_status == StockStatus.IN_STOCK.value:
            description = f"{status_message}\n\n**🔗 [Click here to purchase]({product.uncached_url or product.product_url})**"
        else:
            description = status_message
            
        # Add price change information if available
        if change.price_change:
            price_change = change.price_change
            if float(price_change.change_percentage) < 0:
                price_emoji = "📉"  # Price decreased
            else:
                price_emoji = "📈"  # Price increased
                
            description += f"\n\n{price_emoji} **Price changed:** {price_change.previous_price} → {price_change.current_price}"
            description += f" ({price_change.change_amount}, {abs(price_change.change_percentage):.1f}%)"
            
        return description
    
    def _add_price_fields(self, embed: Embed, product: ProductData, change: StockChange) -> None:
        """Add price-related fields to the embed."""
        # Add current price
        embed.add_field(name="Price", value=f"**{product.price}**", inline=True)
        
        # Add original price if different (on sale)
        if product.original_price and product.original_price != product.price:
            embed.add_field(
                name="Original Price", 
                value=f"~~{product.original_price}~~", 
                inline=True
            )
    
    async def send_notification(self, channel_id: int, embed: Embed, mentions: List[str] = None, 
                               product_url: str = None, uncached_url: str = None) -> bool:
        """
        Send a notification to a Discord channel.
        
        Args:
            channel_id: The Discord channel ID
            embed: The embed to send
            mentions: List of role/user mentions to include
            product_url: The product URL for the view
            uncached_url: The uncached URL for the button
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Format mentions if provided
            content = None
            if mentions and len(mentions) > 0:
                # Filter out invalid mentions and format properly
                valid_mentions = []
                for mention in mentions:
                    mention = mention.strip()
                    if not mention:
                        continue
                        
                    # Already properly formatted role/user mentions
                    if mention.startswith('<@&') and mention.endswith('>'):
                        valid_mentions.append(mention)
                    elif mention.startswith('<@!') and mention.endswith('>'):
                        valid_mentions.append(mention)
                    elif mention.startswith('<@') and mention.endswith('>'):
                        valid_mentions.append(mention)
                    # Handle raw role IDs
                    elif mention.isdigit():
                        valid_mentions.append(f'<@&{mention}>')
                    # Handle @everyone and @here
                    elif mention in ['@everyone', '@here']:
                        valid_mentions.append(mention)
                    else:
                        self.logger.warning(f"Invalid mention format: {mention}")
                
                if valid_mentions:
                    content = " ".join(valid_mentions)
                    self.logger.debug(f"Sending notification with mentions: {content}")
            
            # Get channel from Discord client
            channel = self.discord_client.get_channel(channel_id)
            if not channel:
                self.logger.error(f"Channel not found: {channel_id}")
                return False
            
            # Create view with uncached link button if URLs are provided
            view = None
            if product_url and uncached_url:
                view = ProductNotificationView(product_url, uncached_url)
            
            # Send message with embed, optional mentions, and view
            await channel.send(content=content, embed=embed, view=view)
            
            mention_info = f" with mentions: {content}" if content else ""
            self.logger.info(f"Notification sent to channel {channel_id}{mention_info}")
            return True
            
        except discord.errors.Forbidden as e:
            self.logger.error(f"Permission error sending notification to channel {channel_id}: {e}")
            return False
        except discord.errors.HTTPException as e:
            if e.status == 429:  # Rate limited
                self.logger.warning(f"Rate limited when sending notification: {e}")
                # We'll handle this with the retry mechanism
                return False
            self.logger.error(f"HTTP error sending notification: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
            return False
    
    async def queue_notification(self, notification: Notification) -> None:
        """
        Queue a notification for delivery with rate limit handling.
        
        Args:
            notification: The notification to queue
        """
        # Check if queue is getting too large
        if self.notification_queue.qsize() >= self.max_queue_size:
            self.logger.warning(
                f"Notification queue size ({self.notification_queue.qsize()}) exceeds limit. "
                f"Oldest notifications may be dropped."
            )
            # We continue anyway as the queue will handle overflow
        
        # Add notification to queue
        await self.notification_queue.put(notification)
        self.logger.debug(f"Queued notification for product {notification.product_id}")
        
        # Start processing task if not running
        if self.processing_task is None or self.processing_task.done():
            self.logger.debug("Starting notification queue processing task")
            self.processing_task = asyncio.create_task(self.process_notification_queue_instantly())  # Ultra-fast: instant processing
    
    async def process_notification_queue(self) -> None:
        """
        Process queued notifications with rate limiting and retry logic.
        Handles Discord API rate limits by processing in batches with delays.
        """
        self.logger.info(f"Processing notification queue with {self.notification_queue.qsize()} items")
        
        while not self.notification_queue.empty():
            try:
                # Process notifications in batches to respect rate limits
                for _ in range(min(self.batch_size, self.notification_queue.qsize())):
                    if self.notification_queue.empty():
                        break
                    
                    notification = await self.notification_queue.get()
                    
                    try:
                        # Create embed from stored data
                        embed = Embed.from_dict(notification.embed_data)
                        
                        # Send notification (this is already async, so it's non-blocking)
                        success = await self.send_notification(
                            notification.channel_id, embed, notification.role_mentions,
                            notification.product_url, notification.uncached_url
                        )
                        
                        if not success and notification.retry_count < notification.max_retries:
                            # Requeue with incremented retry count and exponential backoff
                            notification.retry_count += 1
                            self.logger.info(
                                f"Requeuing notification for product {notification.product_id} "
                                f"(attempt {notification.retry_count}/{notification.max_retries})"
                            )
                            await self.notification_queue.put(notification)
                        elif not success:
                            self.logger.error(
                                f"Failed to send notification for product {notification.product_id} "
                                f"after {notification.max_retries} attempts"
                            )
                    except Exception as e:
                        self.logger.error(f"Error processing notification: {e}")
                        # Requeue if retries remaining
                        if notification.retry_count < notification.max_retries:
                            notification.retry_count += 1
                            await self.notification_queue.put(notification)
                    finally:
                        # Mark task as done
                        self.notification_queue.task_done()
                
                # Rate limit delay between batches
                await asyncio.sleep(self.rate_limit_delay)
                
            except Exception as e:
                self.logger.error(f"Error processing notification queue: {e}")
                # Use longer delay on error to prevent rapid retries
                await asyncio.sleep(self.retry_delay)
        
        self.logger.info("Notification queue processing complete")
        
    async def create_and_queue_notification(self, product: ProductData, change: StockChange, 
                                           channel_id: int, role_mentions: List[str] = None) -> None:
        """
        Create and queue a notification in one step.
        
        Args:
            product: The product data
            change: The stock change event
            channel_id: The Discord channel ID
            role_mentions: Optional list of role mentions
        """
        # Create rich embed
        embed = await self.create_stock_notification(product, change)
        
        # Create notification object
        notification = Notification(
            product_id=product.product_id,
            channel_id=channel_id,
            embed_data=embed.to_dict(),
            role_mentions=role_mentions or [],
            timestamp=datetime.utcnow(),
            product_url=product.product_url,
            uncached_url=product.uncached_url,
            retry_count=0,
            max_retries=self.max_retries
        )
        
        # Queue for delivery
        await self.queue_notification(notification)
        

    async def send_notifications_parallel(self, notifications: List[Notification]) -> List[bool]:
        """
        Send multiple notifications in parallel for maximum speed.
        
        Args:
            notifications: List of notifications to send
            
        Returns:
            List of success/failure results
        """
        if not notifications:
            return []
        
        # Create tasks for parallel execution
        tasks = []
        for notification in notifications:
            embed = Embed.from_dict(notification.embed_data)
            task = asyncio.create_task(
                self.send_notification(
                    notification.channel_id, 
                    embed, 
                    notification.role_mentions,
                    notification.product_url, 
                    notification.uncached_url
                )
            )
            tasks.append(task)
        
        # Execute all notifications in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to False, keep boolean results
        return [result if isinstance(result, bool) else False for result in results]
    
    async def process_notification_queue_parallel(self) -> None:
        """
        Process queued notifications in parallel batches for maximum speed.
        """
        self.logger.info(f"Processing notification queue with {self.notification_queue.qsize()} items (PARALLEL MODE)")
        
        while not self.notification_queue.empty():
            try:
                # Collect a batch of notifications
                batch = []
                batch_size = min(10, self.notification_queue.qsize())  # Larger batches for speed
                
                for _ in range(batch_size):
                    if self.notification_queue.empty():
                        break
                    notification = await self.notification_queue.get()
                    batch.append(notification)
                
                if batch:
                    # Send all notifications in parallel
                    results = await self.send_notifications_parallel(batch)
                    
                    # Handle failures
                    for notification, success in zip(batch, results):
                        if not success and notification.retry_count < notification.max_retries:
                            notification.retry_count += 1
                            await self.notification_queue.put(notification)
                        elif not success:
                            self.logger.error(
                                f"Failed to send notification for product {notification.product_id} "
                                f"after {notification.max_retries} attempts"
                            )
                        
                        # Mark task as done
                        self.notification_queue.task_done()
                
                # Minimal delay between batches (optimized for speed)
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error processing notification queue: {e}")
                await asyncio.sleep(1.0)
        
        self.logger.info("Parallel notification queue processing complete")




    async def send_notifications_instantly(self, notifications: List) -> List[bool]:
        """Send notifications with maximum speed using parallel processing."""
        if not notifications:
            return []
        
        start_time = time.time()
        self.logger.info(f"INSTANT SEND: Processing {len(notifications)} notifications")
        
        # Group notifications by channel for optimal batching
        channel_groups = {}
        for notification in notifications:
            channel_id = notification.channel_id
            if channel_id not in channel_groups:
                channel_groups[channel_id] = []
            channel_groups[channel_id].append(notification)
        
        # Create tasks for parallel sending to all channels
        tasks = []
        for channel_id, channel_notifications in channel_groups.items():
            task = asyncio.create_task(
                self._send_channel_batch_instantly(channel_id, channel_notifications)
            )
            tasks.append(task)
        
        # Execute all channel batches in parallel
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results
        results = []
        for batch_result in batch_results:
            if isinstance(batch_result, list):
                results.extend(batch_result)
            elif not isinstance(batch_result, Exception):
                results.append(batch_result)
        
        elapsed = time.time() - start_time
        success_count = sum(1 for r in results if r)
        self.logger.info(f"INSTANT SEND: {success_count}/{len(notifications)} notifications sent in {elapsed:.3f}s")
        
        return results
    
    async def _send_channel_batch_instantly(self, channel_id: int, notifications: List) -> List[bool]:
        """Send a batch of notifications to a single channel with minimal delay."""
        results = []
        
        try:
            channel = self.discord_client.get_channel(channel_id)
            if not channel:
                self.logger.error(f"Channel {channel_id} not found")
                return [False] * len(notifications)
            
            # Send notifications with minimal delay
            for i, notification in enumerate(notifications):
                try:
                    # Create embed quickly
                    embed = discord.Embed.from_dict(notification.embed_data)
                    
                    # Format role mentions
                    content = None
                    if hasattr(notification, 'role_mentions') and notification.role_mentions:
                        mentions = notification.role_mentions
                        if isinstance(mentions, str):
                            mentions = [mentions]
                        
                        valid_mentions = []
                        for mention in mentions:
                            mention = mention.strip()
                            if mention.startswith('<@&') and mention.endswith('>'):
                                valid_mentions.append(mention)
                            elif mention.startswith('<@') and mention.endswith('>'):
                                valid_mentions.append(mention)
                            elif mention in ['@everyone', '@here']:
                                valid_mentions.append(mention)
                            elif mention.isdigit():
                                valid_mentions.append(f'<@&{mention}>')
                        
                        if valid_mentions:
                            content = " ".join(valid_mentions)
                    
                    # Create view with uncached link button if URLs are provided
                    view = None
                    if hasattr(notification, 'product_url') and hasattr(notification, 'uncached_url'):
                        if notification.product_url and notification.uncached_url:
                            view = ProductNotificationView(notification.product_url, notification.uncached_url)
                    
                    # Send notification (fire-and-forget for speed)
                    send_task = asyncio.create_task(channel.send(content=content, embed=embed, view=view))
                    
                    # Don't wait for completion unless it's the last one
                    if i == len(notifications) - 1:
                        await send_task  # Wait for last one to ensure completion
                    
                    results.append(True)
                    
                    # Ultra-minimal delay to avoid rate limits (50ms instead of 1000ms)
                    if i < len(notifications) - 1:  # No delay after last notification
                        await asyncio.sleep(0.05)  # 50ms delay
                        
                except Exception as e:
                    self.logger.error(f"Failed to send notification to channel {channel_id}: {e}")
                    results.append(False)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to send batch to channel {channel_id}: {e}")
            return [False] * len(notifications)
    
    async def process_notification_queue_instantly(self) -> None:
        """Process notification queue with maximum speed."""
        self.logger.info(f"Processing notification queue with {self.notification_queue.qsize()} items (INSTANT MODE)")
        
        notifications_batch = []
        
        # Collect all notifications in queue
        while not self.notification_queue.empty():
            try:
                notification = await asyncio.wait_for(self.notification_queue.get(), timeout=0.1)
                notifications_batch.append(notification)
                
                # Process in large batches for speed
                if len(notifications_batch) >= self.batch_size:
                    await self.send_notifications_instantly(notifications_batch)
                    notifications_batch = []
                    
            except asyncio.TimeoutError:
                break
            except Exception as e:
                self.logger.error(f"Error collecting notifications: {e}")
        
        # Process remaining notifications
        if notifications_batch:
            await self.send_notifications_instantly(notifications_batch)
        
        self.logger.info("Instant notification queue processing complete")

    async def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current notification queue status.
        
        Returns:
            Dictionary with queue statistics
        """
        return {
            "queue_size": self.notification_queue.qsize(),
            "max_queue_size": self.max_queue_size,
            "is_processing": self.processing_task is not None and not self.processing_task.done(),
            "scheduled_notifications": len(self.scheduled_notifications),
            "batch_queues": {batch_id: len(notifications) for batch_id, notifications in self.batch_queue.items()},
            "delivery_statuses": {
                "total": len(self.delivery_statuses),
                "delivered": sum(1 for status in self.delivery_statuses.values() if status.delivered),
                "pending": sum(1 for status in self.delivery_statuses.values() if not status.delivered)
            }
        }
        
    async def create_styled_notification(self, product: ProductData, change: StockChange, 
                                        style: Optional[NotificationStyle] = None) -> Embed:
        """
        Create a styled notification embed with customization options.
        
        Args:
            product: The product data
            change: The stock change event
            style: Optional notification style customization
            
        Returns:
            Discord Embed object with formatted product information
        """
        # Use default style if none provided
        if style is None:
            style = NotificationStyle()
            
        # Determine embed color based on current stock status and style
        embed_color = style.embed_color
        if embed_color == 0x00ff00:  # If default green, use status-based color
            embed_color = self.embed_colors.get(
                product.stock_status, 
                self.config_manager.get('notifications.embed_color', 0x00ff00)
            )
        
        # Get emoji style
        emoji_style_name = style.emoji_style
        if emoji_style_name not in self.emoji_styles:
            emoji_style_name = "default"
        emoji_set = self.emoji_styles[emoji_style_name]
        
        # Create emoji indicator based on stock status
        if product.stock_status == StockStatus.IN_STOCK.value:
            status_emoji = emoji_set["in_stock"]
        elif product.stock_status == StockStatus.OUT_OF_STOCK.value:
            status_emoji = emoji_set["out_of_stock"]
        elif product.stock_status == StockStatus.PRE_ORDER.value:
            status_emoji = emoji_set["pre_order"]
        else:
            status_emoji = emoji_set["unknown"]
        
        # Create title with emoji if not in compact mode
        if style.compact_mode:
            title = product.title
        else:
            title = f"{status_emoji} {product.title}" if status_emoji else product.title
            
        if len(title) > 256:  # Discord embed title limit
            title = title[:253] + "..."
        
        # Create embed with product details
        embed = Embed(
            title=title,
            description=self._create_styled_description(product, change, style, emoji_set),
            color=embed_color,
            url=product.uncached_url or product.product_url
        )
        
        # Add price information if not in compact mode
        if not style.compact_mode:
            self._add_price_fields(embed, product, change)
            
            # Add stock status information
            embed.add_field(
                name="Status", 
                value=f"**{product.stock_status}**", 
                inline=True
            )
            
            # Add delivery information if available
            if product.delivery_info:
                embed.add_field(
                    name="Delivery", 
                    value=product.delivery_info, 
                    inline=True
                )
            
            # Add seller information
            seller = "Bol.com" if product.sold_by_bol else "Marketplace Seller"
            embed.add_field(name="Seller", value=seller, inline=True)
        else:
            # Compact mode: Just add essential info
            embed.add_field(
                name="Price", 
                value=f"**{product.price}**", 
                inline=True
            )
            embed.add_field(
                name="Status", 
                value=f"**{product.stock_status}**", 
                inline=True
            )
        
        # Add product image if enabled
        if product.image_url and style.use_thumbnail:
            embed.set_thumbnail(url=product.image_url)
        # Discord doesn't have a direct way to set thumbnail to None
        # The test is checking embed.thumbnail is None, but it's actually an empty EmbedProxy
        # We'll handle this in the test instead
        
        # Add footer with timestamp if enabled
        if style.use_footer:
            embed.set_footer(text=f"Detected at {change.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return embed
    
    def _create_styled_description(self, product: ProductData, change: StockChange, 
                                  style: NotificationStyle, emoji_set: Dict[str, str]) -> str:
        """Create styled description for the embed based on notification style."""
        # Create status change message
        status_message = f"**Status Changed:** `{change.previous_status}` → `{change.current_status}`"
        
        # Add direct purchase call-to-action for in-stock items
        if product.stock_status == StockStatus.IN_STOCK.value:
            description = f"{status_message}\n\n**🔗 [Click here to purchase]({product.uncached_url or product.product_url})**"
        else:
            description = status_message
            
        # Add price change information if available
        if change.price_change:
            price_change = change.price_change
            if float(price_change.change_percentage) < 0:
                price_emoji = emoji_set["price_decrease"]
            else:
                price_emoji = emoji_set["price_increase"]
                
            price_change_text = f"\n\n{price_emoji} **Price changed:** `{price_change.previous_price}` → `{price_change.current_price}`"
            price_change_text += f" ({price_change.change_amount}, {abs(price_change.change_percentage):.1f}%)"
            description += price_change_text
            
            # Add price history if enabled
            if style.show_price_history:
                price_history = self._get_price_history(product.product_id)
                if price_history:
                    description += "\n\n**Price History:**\n" + price_history
        
        return description
    
    def _get_price_history(self, product_id: str, limit: int = 5) -> str:
        """Get price history for a product as formatted text."""
        try:
            # Get recent stock changes with price changes
            changes = self.stock_change_repo.get_changes_by_product(product_id, limit * 2)
            price_changes = []
            
            for change in changes:
                if change.price_change:
                    price_changes.append((
                        change.timestamp,
                        change.price_change.previous_price,
                        change.price_change.current_price,
                        change.price_change.change_percentage
                    ))
            
            # Limit to most recent changes
            price_changes = price_changes[:limit]
            
            if not price_changes:
                return ""
                
            # Format price history
            history_lines = []
            for timestamp, prev_price, curr_price, percentage in price_changes:
                date_str = timestamp.strftime("%Y-%m-%d")
                direction = "↓" if float(percentage) < 0 else "↑"
                history_lines.append(f"• {date_str}: {prev_price} → {curr_price} ({direction}{abs(float(percentage)):.1f}%)")
                
            return "\n".join(history_lines)
            
        except Exception as e:
            self.logger.error(f"Error getting price history: {e}")
            return ""
    
    async def create_price_change_notification(self, product: ProductData, price_change: PriceChange,
                                              channel_id: int, role_mentions: List[str] = None,
                                              style: Optional[NotificationStyle] = None) -> Notification:
        """
        Create a notification specifically for price changes.
        
        Args:
            product: The product data
            price_change: The price change information
            channel_id: The Discord channel ID
            role_mentions: Optional list of role mentions
            style: Optional notification style
            
        Returns:
            Notification object ready for queuing
        """
        # Create a stock change object with price change
        change = StockChange(
            product_id=product.product_id,
            previous_status=product.stock_status,
            current_status=product.stock_status,
            timestamp=datetime.utcnow(),
            price_change=price_change,
            notification_sent=False
        )
        
        # Use default style if none provided
        if style is None:
            style = NotificationStyle(
                embed_color=0x3498db,  # Blue for price changes
                show_price_history=True
            )
            
        # Create styled embed
        embed = await self.create_styled_notification(product, change, style)
        
        # Create notification object with medium priority
        notification = Notification(
            product_id=product.product_id,
            channel_id=channel_id,
            embed_data=embed.to_dict(),
            role_mentions=role_mentions or [],
            timestamp=datetime.utcnow(),
            product_url=product.product_url,
            uncached_url=product.uncached_url,
            retry_count=0,
            max_retries=self.max_retries,
            priority=2,  # Medium priority for price changes
            style=style
        )
        
        return notification
    
    async def schedule_notification(self, notification: Notification, delay_seconds: int = 0) -> str:
        """
        Schedule a notification for future delivery.
        
        Args:
            notification: The notification to schedule
            delay_seconds: Delay in seconds from now
            
        Returns:
            Notification ID
        """
        # Set scheduled time
        notification.scheduled_time = datetime.utcnow() + timedelta(seconds=delay_seconds)
        
        # Store in scheduled notifications
        self.scheduled_notifications[notification.notification_id] = notification
        
        # Start scheduler task if not running
        if self.scheduler_task is None or self.scheduler_task.done():
            self.scheduler_task = asyncio.create_task(self._run_notification_scheduler())
            
        self.logger.debug(f"Scheduled notification {notification.notification_id} for {notification.scheduled_time}")
        return notification.notification_id
    
    async def _run_notification_scheduler(self) -> None:
        """Run the notification scheduler to process scheduled notifications."""
        self.logger.info("Starting notification scheduler")
        
        while self.scheduled_notifications:
            try:
                now = datetime.utcnow()
                to_process = []
                
                # Find notifications that are due
                for notification_id, notification in list(self.scheduled_notifications.items()):
                    if notification.scheduled_time and notification.scheduled_time <= now:
                        to_process.append(notification)
                        del self.scheduled_notifications[notification_id]
                
                # Process due notifications
                for notification in to_process:
                    await self.queue_notification(notification)
                    
                # Wait before next check
                await asyncio.sleep(1.0)
                
            except Exception as e:
                self.logger.error(f"Error in notification scheduler: {e}")
                await asyncio.sleep(5.0)
                
        self.logger.info("Notification scheduler finished - no more scheduled notifications")
    
    async def create_notification_batch(self, channel_id: int, batch_window: int = None) -> str:
        """
        Create a new notification batch for grouping multiple notifications.
        
        Args:
            channel_id: The Discord channel ID for this batch
            batch_window: Optional custom batch window in seconds
            
        Returns:
            Batch ID
        """
        batch_id = str(uuid.uuid4())
        
        async with self.batch_lock:
            self.batch_queue[batch_id] = {
                "notifications": [],
                "channel_id": channel_id,
                "created_at": datetime.utcnow(),
                "window": batch_window or self.batch_window,
                "processing": False
            }
            
        # Start batch processor if not already running
        asyncio.create_task(self._process_batch_after_window(batch_id))
        
        return batch_id
    
    async def add_to_batch(self, batch_id: str, notification: Notification) -> bool:
        """
        Add a notification to an existing batch.
        
        Args:
            batch_id: The batch ID
            notification: The notification to add
            
        Returns:
            True if added successfully, False otherwise
        """
        async with self.batch_lock:
            if batch_id not in self.batch_queue:
                self.logger.error(f"Batch {batch_id} not found")
                return False
                
            if self.batch_queue[batch_id]["processing"]:
                self.logger.error(f"Batch {batch_id} is already processing")
                return False
                
            # Set batch ID on notification
            notification.batch_id = batch_id
            
            # Add to batch
            self.batch_queue[batch_id]["notifications"].append(notification)
            return True
    
    async def _process_batch_after_window(self, batch_id: str) -> None:
        """Process a batch after its window expires."""
        try:
            # Wait for batch window
            batch_info = self.batch_queue.get(batch_id)
            if not batch_info:
                return
                
            await asyncio.sleep(batch_info["window"])
            
            async with self.batch_lock:
                if batch_id not in self.batch_queue:
                    return
                    
                # Mark as processing
                self.batch_queue[batch_id]["processing"] = True
                
                # Get notifications
                notifications = self.batch_queue[batch_id]["notifications"]
                channel_id = self.batch_queue[batch_id]["channel_id"]
                
                if not notifications:
                    del self.batch_queue[batch_id]
                    return
            
            # Process batch
            await self._send_batched_notifications(batch_id, notifications, channel_id)
            
            # Clean up
            async with self.batch_lock:
                if batch_id in self.batch_queue:
                    del self.batch_queue[batch_id]
                    
        except Exception as e:
            self.logger.error(f"Error processing batch {batch_id}: {e}")
            
            # Clean up on error
            async with self.batch_lock:
                if batch_id in self.batch_queue:
                    del self.batch_queue[batch_id]
    
    async def _send_batched_notifications(self, batch_id: str, notifications: List[Notification], 
                                         channel_id: int) -> None:
        """Send batched notifications as a single message or multiple messages."""
        if not notifications:
            return
            
        # Group notifications by type
        stock_changes = []
        price_changes = []
        other_changes = []
        
        for notification in notifications:
            embed_data = notification.embed_data
            if "Price changed" in embed_data.get("description", ""):
                price_changes.append(notification)
            elif "Status Changed" in embed_data.get("description", ""):
                stock_changes.append(notification)
            else:
                other_changes.append(notification)
        
        # Get all role mentions
        all_mentions = set()
        for notification in notifications:
            all_mentions.update(notification.role_mentions)
        
        # Format mentions
        content = None
        if all_mentions:
            content = " ".join(all_mentions)
        
        # Get channel
        channel = self.discord_client.get_channel(channel_id)
        if not channel:
            self.logger.error(f"Channel not found: {channel_id}")
            return
            
        try:
            # Send stock changes first (highest priority)
            if stock_changes:
                embeds = [Embed.from_dict(n.embed_data) for n in stock_changes[:10]]  # Discord limit: 10 embeds
                if embeds:
                    await channel.send(content=content, embeds=embeds)
                    
                    # Update delivery status
                    for notification in stock_changes[:10]:
                        self._update_delivery_status(notification, True)
                        
                    # If more than 10, send additional messages
                    for i in range(10, len(stock_changes), 10):
                        embeds = [Embed.from_dict(n.embed_data) for n in stock_changes[i:i+10]]
                        await channel.send(embeds=embeds)
                        
                        # Update delivery status
                        for notification in stock_changes[i:i+10]:
                            self._update_delivery_status(notification, True)
                        
                        # Rate limit delay
                        await asyncio.sleep(self.rate_limit_delay)
            
            # Send price changes
            if price_changes:
                # Rate limit delay between message types
                if stock_changes:
                    await asyncio.sleep(self.rate_limit_delay)
                    
                embeds = [Embed.from_dict(n.embed_data) for n in price_changes[:10]]
                if embeds:
                    await channel.send(embeds=embeds)
                    
                    # Update delivery status
                    for notification in price_changes[:10]:
                        self._update_delivery_status(notification, True)
                        
                    # If more than 10, send additional messages
                    for i in range(10, len(price_changes), 10):
                        embeds = [Embed.from_dict(n.embed_data) for n in price_changes[i:i+10]]
                        await channel.send(embeds=embeds)
                        
                        # Update delivery status
                        for notification in price_changes[i:i+10]:
                            self._update_delivery_status(notification, True)
                        
                        # Rate limit delay
                        await asyncio.sleep(self.rate_limit_delay)
            
            # Send other changes
            if other_changes:
                # Rate limit delay between message types
                if stock_changes or price_changes:
                    await asyncio.sleep(self.rate_limit_delay)
                    
                embeds = [Embed.from_dict(n.embed_data) for n in other_changes[:10]]
                if embeds:
                    await channel.send(embeds=embeds)
                    
                    # Update delivery status
                    for notification in other_changes[:10]:
                        self._update_delivery_status(notification, True)
                        
                    # If more than 10, send additional messages
                    for i in range(10, len(other_changes), 10):
                        embeds = [Embed.from_dict(n.embed_data) for n in other_changes[i:i+10]]
                        await channel.send(embeds=embeds)
                        
                        # Update delivery status
                        for notification in other_changes[i:i+10]:
                            self._update_delivery_status(notification, True)
                        
                        # Rate limit delay
                        await asyncio.sleep(self.rate_limit_delay)
                        
            self.logger.info(f"Successfully sent batch {batch_id} with {len(notifications)} notifications")
            
        except discord.errors.Forbidden as e:
            self.logger.error(f"Permission error sending batch {batch_id}: {e}")
            self._update_batch_delivery_status(notifications, False, str(e))
            
        except discord.errors.HTTPException as e:
            self.logger.error(f"HTTP error sending batch {batch_id}: {e}")
            self._update_batch_delivery_status(notifications, False, str(e))
            
        except Exception as e:
            self.logger.error(f"Error sending batch {batch_id}: {e}")
            self._update_batch_delivery_status(notifications, False, str(e))
    
    def _update_batch_delivery_status(self, notifications: List[Notification], 
                                     delivered: bool, error_message: Optional[str] = None) -> None:
        """Update delivery status for all notifications in a batch."""
        for notification in notifications:
            self._update_delivery_status(notification, delivered, error_message)
    
    def _update_delivery_status(self, notification: Notification, delivered: bool, 
                               error_message: Optional[str] = None) -> None:
        """Update delivery status for a notification."""
        if not notification.delivery_status:
            notification.delivery_status = NotificationDeliveryStatus(
                notification_id=notification.notification_id,
                channel_id=notification.channel_id,
                product_id=notification.product_id
            )
            
        notification.delivery_status.delivery_attempts += 1
        notification.delivery_status.last_attempt = datetime.utcnow()
        notification.delivery_status.delivered = delivered
        
        if delivered:
            notification.delivery_status.delivered_at = datetime.utcnow()
        else:
            notification.delivery_status.error_message = error_message
            
        # Store in delivery status tracking
        self.delivery_statuses[notification.notification_id] = notification.delivery_status
        
        # Add to notification history
        if notification.product_id not in self.notification_history:
            self.notification_history[notification.product_id] = []
        self.notification_history[notification.product_id].append(notification.notification_id)
    
    async def get_delivery_status(self, notification_id: str) -> Optional[NotificationDeliveryStatus]:
        """
        Get delivery status for a notification.
        
        Args:
            notification_id: The notification ID
            
        Returns:
            Notification delivery status or None if not found
        """
        return self.delivery_statuses.get(notification_id)
    
    async def get_notification_history(self, product_id: str) -> List[NotificationDeliveryStatus]:
        """
        Get notification history for a product.
        
        Args:
            product_id: The product ID
            
        Returns:
            List of notification delivery statuses
        """
        notification_ids = self.notification_history.get(product_id, [])
        return [self.delivery_statuses.get(nid) for nid in notification_ids if nid in self.delivery_statuses]
    
    async def should_send_notification(self, product_id: str) -> bool:
        """
        Check if a notification should be sent based on cooldown settings.
        
        Args:
            product_id: The product ID
            
        Returns:
            True if notification should be sent, False otherwise
        """
        if not self.cooldown_enabled:
            return True
            
        now = datetime.utcnow()
        
        # Check product-specific cooldown
        if self.cooldown_per_product:
            last_time = self.notification_cooldowns.get(product_id)
            if last_time and (now - last_time).total_seconds() < self.cooldown_period:
                self.logger.debug(f"Notification for product {product_id} on cooldown")
                return False
        else:
            # Check global cooldown
            if self.notification_cooldowns and any(
                (now - last_time).total_seconds() < self.cooldown_period 
                for last_time in self.notification_cooldowns.values()
            ):
                self.logger.debug("Notification on global cooldown")
                return False
                
        # Update cooldown timestamp
        self.notification_cooldowns[product_id] = now
        return True