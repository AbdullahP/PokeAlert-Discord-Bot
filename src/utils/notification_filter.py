
"""
Notification System Patch - Only Notify on IN STOCK
This patch ensures notifications are only sent when products come IN STOCK.
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class StockNotificationFilter:
    """Filter notifications to only send when products come IN STOCK."""
    
    def __init__(self):
        self.last_notifications = {}  # Track last notification time per product
        self.cooldown_seconds = 300   # 5 minutes cooldown
    
    def should_send_notification(self, product_id: str, previous_status: str, current_status: str) -> bool:
        """Check if we should send a notification."""
        
        # Only notify when coming IN STOCK
        if (previous_status and previous_status.lower() in ['out of stock', 'unavailable'] and 
            current_status.lower() in ['in stock', 'available']):
            
            # Check cooldown
            now = datetime.now()
            last_notification = self.last_notifications.get(product_id)
            
            if last_notification:
                time_diff = (now - last_notification).total_seconds()
                if time_diff < self.cooldown_seconds:
                    logger.info(f"Notification for {product_id} skipped due to cooldown ({time_diff:.0f}s < {self.cooldown_seconds}s)")
                    return False
            
            # Update last notification time
            self.last_notifications[product_id] = now
            logger.info(f"✅ Notification approved for {product_id}: {previous_status} -> {current_status}")
            return True
        
        # Don't notify for other changes
        logger.debug(f"❌ Notification skipped for {product_id}: {previous_status} -> {current_status}")
        return False

# Global notification filter
notification_filter = StockNotificationFilter()
