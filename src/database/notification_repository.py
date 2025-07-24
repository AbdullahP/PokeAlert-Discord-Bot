"""
Repository for notification-related database operations.
"""
import json
import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime

from .connection import db
from ..models.product_data import (
    Notification, NotificationStyle, NotificationDeliveryStatus, 
    PriceChange, StockChange
)


class NotificationRepository:
    """Repository for notification-related database operations."""
    
    def __init__(self):
        """Initialize repository."""
        self.logger = logging.getLogger(__name__)
        self.db = db
    
    def _row_to_dict(self, row) -> dict:
        """Convert a SQLite Row to a dictionary."""
        if row is None:
            return None
        return {key: row[key] for key in row.keys()}
    
    def add_notification_style(self, style_id: str, name: str, style: NotificationStyle) -> bool:
        """Add a notification style to the database."""
        try:
            self.db.execute(
                '''
                INSERT INTO notification_styles (
                    id, name, embed_color, use_thumbnail, use_footer,
                    compact_mode, show_price_history, emoji_style
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    style_id, name, style.embed_color, style.use_thumbnail,
                    style.use_footer, style.compact_mode, style.show_price_history,
                    style.emoji_style
                )
            )
            self.db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error adding notification style: {e}")
            self.db.rollback()
            return False
    
    def update_notification_style(self, style_id: str, style: NotificationStyle) -> bool:
        """Update a notification style in the database."""
        try:
            self.db.execute(
                '''
                UPDATE notification_styles SET
                    embed_color = ?, use_thumbnail = ?, use_footer = ?,
                    compact_mode = ?, show_price_history = ?, emoji_style = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (
                    style.embed_color, style.use_thumbnail, style.use_footer,
                    style.compact_mode, style.show_price_history, style.emoji_style,
                    style_id
                )
            )
            self.db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error updating notification style: {e}")
            self.db.rollback()
            return False
    
    def get_notification_style(self, style_id: str) -> Optional[Tuple[str, NotificationStyle]]:
        """Get a notification style by ID."""
        try:
            cursor = self.db.execute(
                'SELECT * FROM notification_styles WHERE id = ?',
                (style_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
                
            row_dict = self._row_to_dict(row)
            style = NotificationStyle(
                embed_color=row_dict['embed_color'],
                use_thumbnail=bool(row_dict['use_thumbnail']),
                use_footer=bool(row_dict['use_footer']),
                compact_mode=bool(row_dict['compact_mode']),
                show_price_history=bool(row_dict['show_price_history']),
                emoji_style=row_dict['emoji_style']
            )
            return (row_dict['name'], style)
        except Exception as e:
            self.logger.error(f"Error getting notification style: {e}")
            return None
    
    def get_all_notification_styles(self) -> Dict[str, Tuple[str, NotificationStyle]]:
        """Get all notification styles."""
        try:
            cursor = self.db.execute('SELECT * FROM notification_styles')
            rows = cursor.fetchall()
            
            styles = {}
            for row in rows:
                row_dict = self._row_to_dict(row)
                style = NotificationStyle(
                    embed_color=row_dict['embed_color'],
                    use_thumbnail=bool(row_dict['use_thumbnail']),
                    use_footer=bool(row_dict['use_footer']),
                    compact_mode=bool(row_dict['compact_mode']),
                    show_price_history=bool(row_dict['show_price_history']),
                    emoji_style=row_dict['emoji_style']
                )
                styles[row_dict['id']] = (row_dict['name'], style)
            
            return styles
        except Exception as e:
            self.logger.error(f"Error getting all notification styles: {e}")
            return {}
    
    def assign_style_to_product(self, product_id: str, style_id: str) -> bool:
        """Assign a notification style to a product."""
        try:
            self.db.execute(
                '''
                INSERT OR REPLACE INTO product_notification_styles (
                    product_id, style_id
                ) VALUES (?, ?)
                ''',
                (product_id, style_id)
            )
            self.db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error assigning style to product: {e}")
            self.db.rollback()
            return False
    
    def get_product_style(self, product_id: str) -> Optional[Tuple[str, NotificationStyle]]:
        """Get the notification style assigned to a product."""
        try:
            cursor = self.db.execute(
                '''
                SELECT ns.* FROM notification_styles ns
                JOIN product_notification_styles pns ON ns.id = pns.style_id
                WHERE pns.product_id = ?
                ''',
                (product_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
                
            row_dict = self._row_to_dict(row)
            style = NotificationStyle(
                embed_color=row_dict['embed_color'],
                use_thumbnail=bool(row_dict['use_thumbnail']),
                use_footer=bool(row_dict['use_footer']),
                compact_mode=bool(row_dict['compact_mode']),
                show_price_history=bool(row_dict['show_price_history']),
                emoji_style=row_dict['emoji_style']
            )
            return (row_dict['name'], style)
        except Exception as e:
            self.logger.error(f"Error getting product style: {e}")
            return None
    
    def add_delivery_status(self, status: NotificationDeliveryStatus) -> bool:
        """Add a notification delivery status to the database."""
        try:
            last_attempt = status.last_attempt.isoformat() if status.last_attempt else None
            delivered_at = status.delivered_at.isoformat() if status.delivered_at else None
            
            self.db.execute(
                '''
                INSERT INTO notification_delivery_status (
                    notification_id, product_id, channel_id, delivery_attempts,
                    last_attempt, delivered, delivered_at, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    status.notification_id, status.product_id, status.channel_id,
                    status.delivery_attempts, last_attempt, status.delivered,
                    delivered_at, status.error_message
                )
            )
            self.db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error adding delivery status: {e}")
            self.db.rollback()
            return False
    
    def update_delivery_status(self, status: NotificationDeliveryStatus) -> bool:
        """Update a notification delivery status in the database."""
        try:
            last_attempt = status.last_attempt.isoformat() if status.last_attempt else None
            delivered_at = status.delivered_at.isoformat() if status.delivered_at else None
            
            self.db.execute(
                '''
                UPDATE notification_delivery_status SET
                    delivery_attempts = ?, last_attempt = ?, delivered = ?,
                    delivered_at = ?, error_message = ?
                WHERE notification_id = ?
                ''',
                (
                    status.delivery_attempts, last_attempt, status.delivered,
                    delivered_at, status.error_message, status.notification_id
                )
            )
            self.db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error updating delivery status: {e}")
            self.db.rollback()
            return False
    
    def get_delivery_status(self, notification_id: str) -> Optional[NotificationDeliveryStatus]:
        """Get a notification delivery status by ID."""
        try:
            cursor = self.db.execute(
                'SELECT * FROM notification_delivery_status WHERE notification_id = ?',
                (notification_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
                
            row_dict = self._row_to_dict(row)
            
            # Convert string timestamps to datetime objects
            last_attempt = None
            if row_dict['last_attempt']:
                last_attempt = datetime.fromisoformat(row_dict['last_attempt'])
                
            delivered_at = None
            if row_dict['delivered_at']:
                delivered_at = datetime.fromisoformat(row_dict['delivered_at'])
            
            return NotificationDeliveryStatus(
                notification_id=row_dict['notification_id'],
                product_id=row_dict['product_id'],
                channel_id=row_dict['channel_id'],
                delivery_attempts=row_dict['delivery_attempts'],
                last_attempt=last_attempt,
                delivered=bool(row_dict['delivered']),
                delivered_at=delivered_at,
                error_message=row_dict['error_message']
            )
        except Exception as e:
            self.logger.error(f"Error getting delivery status: {e}")
            return None
    
    def get_delivery_statuses_by_product(self, product_id: str, limit: int = 10) -> List[NotificationDeliveryStatus]:
        """Get notification delivery statuses for a product."""
        try:
            cursor = self.db.execute(
                '''
                SELECT * FROM notification_delivery_status
                WHERE product_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                ''',
                (product_id, limit)
            )
            rows = cursor.fetchall()
            
            statuses = []
            for row in rows:
                row_dict = self._row_to_dict(row)
                
                # Convert string timestamps to datetime objects
                last_attempt = None
                if row_dict['last_attempt']:
                    last_attempt = datetime.fromisoformat(row_dict['last_attempt'])
                    
                delivered_at = None
                if row_dict['delivered_at']:
                    delivered_at = datetime.fromisoformat(row_dict['delivered_at'])
                
                statuses.append(NotificationDeliveryStatus(
                    notification_id=row_dict['notification_id'],
                    product_id=row_dict['product_id'],
                    channel_id=row_dict['channel_id'],
                    delivery_attempts=row_dict['delivery_attempts'],
                    last_attempt=last_attempt,
                    delivered=bool(row_dict['delivered']),
                    delivered_at=delivered_at,
                    error_message=row_dict['error_message']
                ))
            
            return statuses
        except Exception as e:
            self.logger.error(f"Error getting delivery statuses by product: {e}")
            return []
    
    def create_notification_batch(self, batch_id: str, channel_id: int, window_seconds: int = 60) -> bool:
        """Create a notification batch in the database."""
        try:
            self.db.execute(
                '''
                INSERT INTO notification_batches (
                    batch_id, channel_id, window_seconds
                ) VALUES (?, ?, ?)
                ''',
                (batch_id, channel_id, window_seconds)
            )
            self.db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error creating notification batch: {e}")
            self.db.rollback()
            return False
    
    def update_batch_status(self, batch_id: str, status: str, processed_at: Optional[datetime] = None) -> bool:
        """Update a notification batch status in the database."""
        try:
            if processed_at is None and status == 'processed':
                processed_at = datetime.utcnow()
                
            processed_at_str = processed_at.isoformat() if processed_at else None
            
            self.db.execute(
                '''
                UPDATE notification_batches SET
                    status = ?, processed_at = ?
                WHERE batch_id = ?
                ''',
                (status, processed_at_str, batch_id)
            )
            self.db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error updating batch status: {e}")
            self.db.rollback()
            return False
    
    def add_scheduled_notification(self, notification: Notification) -> bool:
        """Add a scheduled notification to the database."""
        try:
            scheduled_time = notification.scheduled_time.isoformat() if notification.scheduled_time else None
            role_mentions = json.dumps(notification.role_mentions) if notification.role_mentions else '[]'
            embed_data = json.dumps(notification.embed_data)
            
            self.db.execute(
                '''
                INSERT INTO scheduled_notifications (
                    notification_id, product_id, channel_id, scheduled_time,
                    priority, batch_id, embed_data, role_mentions
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    notification.notification_id, notification.product_id,
                    notification.channel_id, scheduled_time, notification.priority,
                    notification.batch_id, embed_data, role_mentions
                )
            )
            self.db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error adding scheduled notification: {e}")
            self.db.rollback()
            return False
    
    def mark_scheduled_notification_processed(self, notification_id: str) -> bool:
        """Mark a scheduled notification as processed."""
        try:
            self.db.execute(
                'UPDATE scheduled_notifications SET processed = 1 WHERE notification_id = ?',
                (notification_id,)
            )
            self.db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error marking scheduled notification processed: {e}")
            self.db.rollback()
            return False
    
    def get_pending_scheduled_notifications(self, limit: int = 100) -> List[Notification]:
        """Get pending scheduled notifications that are due."""
        try:
            cursor = self.db.execute(
                '''
                SELECT * FROM scheduled_notifications
                WHERE processed = 0 AND scheduled_time <= CURRENT_TIMESTAMP
                ORDER BY priority, scheduled_time
                LIMIT ?
                ''',
                (limit,)
            )
            rows = cursor.fetchall()
            
            notifications = []
            for row in rows:
                row_dict = self._row_to_dict(row)
                
                # Parse JSON data
                embed_data = json.loads(row_dict['embed_data'])
                role_mentions = json.loads(row_dict['role_mentions'])
                
                # Convert string timestamp to datetime
                scheduled_time = datetime.fromisoformat(row_dict['scheduled_time'])
                
                notification = Notification(
                    notification_id=row_dict['notification_id'],
                    product_id=row_dict['product_id'],
                    channel_id=row_dict['channel_id'],
                    embed_data=embed_data,
                    role_mentions=role_mentions,
                    timestamp=datetime.utcnow(),
                    priority=row_dict['priority'],
                    scheduled_time=scheduled_time,
                    batch_id=row_dict['batch_id']
                )
                
                notifications.append(notification)
            
            return notifications
        except Exception as e:
            self.logger.error(f"Error getting pending scheduled notifications: {e}")
            return []
    
    def add_price_history(self, product_id: str, price: str) -> bool:
        """Add a price point to the price history."""
        try:
            self.db.execute(
                '''
                INSERT INTO price_history (product_id, price)
                VALUES (?, ?)
                ''',
                (product_id, price)
            )
            self.db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error adding price history: {e}")
            self.db.rollback()
            return False
    
    def get_price_history(self, product_id: str, limit: int = 10) -> List[Tuple[str, datetime]]:
        """Get price history for a product."""
        try:
            cursor = self.db.execute(
                '''
                SELECT price, timestamp FROM price_history
                WHERE product_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                ''',
                (product_id, limit)
            )
            rows = cursor.fetchall()
            
            history = []
            for row in rows:
                row_dict = self._row_to_dict(row)
                timestamp = datetime.fromisoformat(row_dict['timestamp'])
                history.append((row_dict['price'], timestamp))
            
            return history
        except Exception as e:
            self.logger.error(f"Error getting price history: {e}")
            return []