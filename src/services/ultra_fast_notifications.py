
class UltraFastNotificationService:
    """Ultra-fast notification service with parallel sending."""
    
    def __init__(self, discord_client):
        self.discord_client = discord_client
        self.notification_queue = asyncio.Queue(maxsize=5000)  # Larger queue
        self.batch_processor_task = None
        
    async def send_notifications_ultra_fast(self, notifications: List[Notification]) -> None:
        """Send notifications with maximum speed using batching and parallel processing."""
        if not notifications:
            return
        
        start_time = time.time()
        
        # Group notifications by channel for batching
        channel_groups = {}
        for notification in notifications:
            channel_id = notification.channel_id
            if channel_id not in channel_groups:
                channel_groups[channel_id] = []
            channel_groups[channel_id].append(notification)
        
        # Send all channel groups in parallel
        tasks = []
        for channel_id, channel_notifications in channel_groups.items():
            task = asyncio.create_task(
                self.send_channel_batch_ultra_fast(channel_id, channel_notifications)
            )
            tasks.append(task)
        
        # Execute all sends in parallel
        await asyncio.gather(*tasks, return_exceptions=True)
        
        elapsed = time.time() - start_time
        print(f"ULTRA SPEED: Sent {len(notifications)} notifications in {elapsed:.3f}s")
    
    async def send_channel_batch_ultra_fast(self, channel_id: int, notifications: List[Notification]) -> None:
        """Send a batch of notifications to a single channel ultra-fast."""
        try:
            channel = self.discord_client.get_channel(channel_id)
            if not channel:
                return
            
            # Send notifications with minimal delay
            for notification in notifications:
                # Create embed quickly
                embed = self.create_embed_ultra_fast(notification)
                
                # Send without waiting (fire and forget for speed)
                asyncio.create_task(channel.send(embed=embed))
                
                # Minimal delay to avoid rate limits
                await asyncio.sleep(0.05)  # 50ms delay instead of 1s
                
        except Exception as e:
            print(f"Ultra-fast batch send failed for channel {channel_id}: {e}")
    
    def create_embed_ultra_fast(self, notification: Notification) -> discord.Embed:
        """Create Discord embed with minimal processing time."""
        # Pre-computed embed template for speed
        embed = discord.Embed(
            title=notification.title[:100],  # Truncate for speed
            description=f"Price: {notification.price}\nStatus: {notification.stock_status}",
            color=0x00ff00 if notification.stock_status == "In Stock" else 0xff0000,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(name="Link", value=f"[View Product]({notification.url})", inline=False)
        
        return embed
