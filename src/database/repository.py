"""
Repository pattern implementation for database operations.
"""
import json
import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime

from .connection import db
from ..models.product_data import ProductConfig, ProductData, StockChange, MonitoringStatus, PriceChange


class Repository:
    """Base repository with common database operations."""
    
    def __init__(self):
        """Initialize repository."""
        self.logger = logging.getLogger(__name__)
        self.db = db
    
    def _row_to_dict(self, row) -> dict:
        """Convert a SQLite Row to a dictionary."""
        if row is None:
            return None
        return {key: row[key] for key in row.keys()}
    
    def _execute_transaction(self, queries: List[Tuple[str, Tuple]]) -> bool:
        """Execute multiple queries as a transaction."""
        try:
            for query, params in queries:
                self.db.execute(query, params)
            self.db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Transaction error: {e}")
            self.db.rollback()
            return False


class ProductRepository(Repository):
    """Repository for product-related database operations."""
    
    def add_product(self, config: ProductConfig) -> bool:
        """Add a product to the database."""
        try:
            if not config.validate():
                self.logger.error(f"Invalid product configuration: {config}")
                return False
                
            role_mentions_json = json.dumps(config.role_mentions) if config.role_mentions else '[]'
            
            self.db.execute(
                '''
                INSERT INTO products (
                    id, url, url_type, channel_id, guild_id, 
                    monitoring_interval, role_mentions, is_active, 
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    config.product_id, config.url, config.url_type,
                    config.channel_id, config.guild_id, config.monitoring_interval,
                    role_mentions_json, config.is_active,
                    config.created_at.isoformat(), config.updated_at.isoformat()
                )
            )
            self.db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error adding product: {e}")
            self.db.rollback()
            return False
    
    def update_product(self, config: ProductConfig) -> bool:
        """Update a product in the database."""
        try:
            if not config.validate():
                self.logger.error(f"Invalid product configuration: {config}")
                return False
                
            role_mentions_json = json.dumps(config.role_mentions) if config.role_mentions else '[]'
            config.updated_at = datetime.utcnow()
            
            self.db.execute(
                '''
                UPDATE products SET
                    url = ?, url_type = ?, channel_id = ?, guild_id = ?,
                    monitoring_interval = ?, role_mentions = ?, is_active = ?,
                    updated_at = ?
                WHERE id = ?
                ''',
                (
                    config.url, config.url_type, config.channel_id, config.guild_id,
                    config.monitoring_interval, role_mentions_json, config.is_active,
                    config.updated_at.isoformat(), config.product_id
                )
            )
            self.db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error updating product: {e}")
            self.db.rollback()
            return False
    
    def delete_product(self, product_id: str) -> bool:
        """Delete a product from the database."""
        try:
            # With CASCADE constraints, this will delete related records
            self.db.execute('DELETE FROM products WHERE id = ?', (product_id,))
            self.db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error deleting product: {e}")
            self.db.rollback()
            return False
    
    def get_product(self, product_id: str) -> Optional[ProductConfig]:
        """Get a product by ID."""
        try:
            cursor = self.db.execute('SELECT * FROM products WHERE id = ?', (product_id,))
            row = cursor.fetchone()
            if not row:
                return None
            
            row_dict = self._row_to_dict(row)
            # Map database 'id' field to 'product_id' for ProductConfig
            if 'id' in row_dict:
                row_dict['product_id'] = row_dict.pop('id')
            return ProductConfig.from_dict(row_dict)
        except Exception as e:
            self.logger.error(f"Error getting product: {e}")
            return None
    
    def get_products_by_channel(self, channel_id: int) -> List[ProductConfig]:
        """Get all products for a channel."""
        try:
            cursor = self.db.execute('SELECT * FROM products WHERE channel_id = ?', (channel_id,))
            rows = cursor.fetchall()
            
            products = []
            for row in rows:
                row_dict = self._row_to_dict(row)
                # Map database 'id' field to 'product_id' for ProductConfig
                if 'id' in row_dict:
                    row_dict['product_id'] = row_dict.pop('id')
                products.append(ProductConfig.from_dict(row_dict))
            
            return products
        except Exception as e:
            self.logger.error(f"Error getting products by channel: {e}")
            return []
    
    def get_all_active_products(self) -> List[ProductConfig]:
        """Get all active products."""
        try:
            cursor = self.db.execute('SELECT * FROM products WHERE is_active = 1')
            rows = cursor.fetchall()
            
            products = []
            for row in rows:
                row_dict = self._row_to_dict(row)
                # Map database 'id' field to 'product_id' for ProductConfig
                if 'id' in row_dict:
                    row_dict['product_id'] = row_dict.pop('id')
                products.append(ProductConfig.from_dict(row_dict))
            
            return products
        except Exception as e:
            self.logger.error(f"Error getting active products: {e}")
            return []
    
    def get_products_by_guild(self, guild_id: int) -> List[ProductConfig]:
        """Get all products for a guild."""
        try:
            cursor = self.db.execute('SELECT * FROM products WHERE guild_id = ?', (guild_id,))
            rows = cursor.fetchall()
            
            products = []
            for row in rows:
                row_dict = self._row_to_dict(row)
                # Map database 'id' field to 'product_id' for ProductConfig
                if 'id' in row_dict:
                    row_dict['product_id'] = row_dict.pop('id')
                products.append(ProductConfig.from_dict(row_dict))
            
            return products
        except Exception as e:
            self.logger.error(f"Error getting products by guild: {e}")
            return []
    
    def count_products(self, active_only: bool = False) -> int:
        """Count total products."""
        try:
            query = 'SELECT COUNT(*) as count FROM products'
            if active_only:
                query += ' WHERE is_active = 1'
                
            cursor = self.db.execute(query)
            row = cursor.fetchone()
            return row['count'] if row else 0
        except Exception as e:
            self.logger.error(f"Error counting products: {e}")
            return 0


class ProductStatusRepository(Repository):
    """Repository for product status operations."""
    
    def update_product_status(self, product_data: ProductData) -> bool:
        """Update product status in the database."""
        try:
            if not product_data.validate():
                self.logger.error(f"Invalid product data: {product_data}")
                return False
                
            # Check if status exists
            cursor = self.db.execute(
                'SELECT 1 FROM product_status WHERE product_id = ?',
                (product_data.product_id,)
            )
            exists = cursor.fetchone() is not None
            
            if exists:
                self.db.execute(
                    '''
                    UPDATE product_status SET
                        title = ?, price = ?, original_price = ?,
                        image_url = ?, product_url = ?, uncached_url = ?,
                        stock_status = ?, stock_level = ?, website = ?,
                        delivery_info = ?, sold_by_bol = ?, last_checked = ?
                    WHERE product_id = ?
                    ''',
                    (
                        product_data.title, product_data.price, product_data.original_price,
                        product_data.image_url, product_data.product_url, product_data.uncached_url,
                        product_data.stock_status, product_data.stock_level, product_data.website,
                        product_data.delivery_info, product_data.sold_by_bol,
                        product_data.last_checked.isoformat(),
                        product_data.product_id
                    )
                )
            else:
                self.db.execute(
                    '''
                    INSERT INTO product_status (
                        product_id, title, price, original_price,
                        image_url, product_url, uncached_url,
                        stock_status, stock_level, website,
                        delivery_info, sold_by_bol, last_checked
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        product_data.product_id, product_data.title, product_data.price,
                        product_data.original_price, product_data.image_url, product_data.product_url,
                        product_data.uncached_url, product_data.stock_status, product_data.stock_level,
                        product_data.website, product_data.delivery_info, product_data.sold_by_bol,
                        product_data.last_checked.isoformat()
                    )
                )
            
            self.db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error updating product status: {e}")
            self.db.rollback()
            return False
    
    def get_product_status(self, product_id: str) -> Optional[ProductData]:
        """Get current status for a product."""
        try:
            cursor = self.db.execute(
                'SELECT * FROM product_status WHERE product_id = ?',
                (product_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            row_dict = self._row_to_dict(row)
            return ProductData.from_dict(row_dict)
        except Exception as e:
            self.logger.error(f"Error getting product status: {e}")
            return None
    
    def get_all_product_statuses(self) -> List[ProductData]:
        """Get all product statuses."""
        try:
            cursor = self.db.execute('SELECT * FROM product_status')
            rows = cursor.fetchall()
            
            statuses = []
            for row in rows:
                row_dict = self._row_to_dict(row)
                statuses.append(ProductData.from_dict(row_dict))
            
            return statuses
        except Exception as e:
            self.logger.error(f"Error getting all product statuses: {e}")
            return []


class StockChangeRepository(Repository):
    """Repository for stock change operations."""
    
    def add_stock_change(self, change: StockChange) -> Optional[int]:
        """Add a stock change event to the database and return the ID."""
        try:
            if not change.validate():
                self.logger.error(f"Invalid stock change: {change}")
                return None
                
            price_change_json = None
            if change.price_change:
                price_change_json = json.dumps(change.price_change.to_dict())
                
            cursor = self.db.execute(
                '''
                INSERT INTO stock_changes (
                    product_id, previous_status, current_status,
                    timestamp, price_change, notification_sent
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (
                    change.product_id, change.previous_status,
                    change.current_status, change.timestamp.isoformat(),
                    price_change_json, change.notification_sent
                )
            )
            self.db.commit()
            return cursor.lastrowid
        except Exception as e:
            self.logger.error(f"Error adding stock change: {e}")
            self.db.rollback()
            return None
    
    def mark_notification_sent(self, change_id: int) -> bool:
        """Mark a stock change notification as sent."""
        try:
            self.db.execute(
                'UPDATE stock_changes SET notification_sent = 1 WHERE id = ?',
                (change_id,)
            )
            self.db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error marking notification sent: {e}")
            self.db.rollback()
            return False
    
    def get_stock_change(self, change_id: int) -> Optional[StockChange]:
        """Get a stock change by ID."""
        try:
            cursor = self.db.execute(
                'SELECT * FROM stock_changes WHERE id = ?',
                (change_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
                
            row_dict = self._row_to_dict(row)
            stock_change = StockChange.from_dict(row_dict)
            stock_change.id = row_dict['id']
            return stock_change
        except Exception as e:
            self.logger.error(f"Error getting stock change: {e}")
            return None
    
    def get_recent_changes(self, hours: int = 24) -> List[StockChange]:
        """Get recent stock changes within the specified hours."""
        try:
            cursor = self.db.execute(
                '''
                SELECT sc.*
                FROM stock_changes sc
                WHERE sc.timestamp >= datetime('now', '-' || ? || ' hours')
                ORDER BY sc.timestamp DESC
                ''',
                (hours,)
            )
            rows = cursor.fetchall()
            
            changes = []
            for row in rows:
                row_dict = self._row_to_dict(row)
                stock_change = StockChange.from_dict(row_dict)
                stock_change.id = row_dict['id']
                changes.append(stock_change)
                
            return changes
        except Exception as e:
            self.logger.error(f"Error getting recent changes: {e}")
            return []
    
    def get_changes_by_product(self, product_id: str, limit: int = 10) -> List[StockChange]:
        """Get recent stock changes for a product."""
        try:
            cursor = self.db.execute(
                '''
                SELECT * FROM stock_changes
                WHERE product_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                ''',
                (product_id, limit)
            )
            rows = cursor.fetchall()
            
            changes = []
            for row in rows:
                row_dict = self._row_to_dict(row)
                stock_change = StockChange.from_dict(row_dict)
                stock_change.id = row_dict['id']
                changes.append(stock_change)
                
            return changes
        except Exception as e:
            self.logger.error(f"Error getting changes by product: {e}")
            return []
    
    def get_pending_notifications(self) -> List[StockChange]:
        """Get stock changes that need notifications."""
        try:
            cursor = self.db.execute(
                '''
                SELECT sc.*
                FROM stock_changes sc
                WHERE sc.notification_sent = 0
                ORDER BY sc.timestamp ASC
                '''
            )
            rows = cursor.fetchall()
            
            changes = []
            for row in rows:
                row_dict = self._row_to_dict(row)
                stock_change = StockChange.from_dict(row_dict)
                stock_change.id = row_dict['id']
                changes.append(stock_change)
                
            return changes
        except Exception as e:
            self.logger.error(f"Error getting pending notifications: {e}")
            return []


class MetricsRepository(Repository):
    """Repository for monitoring metrics operations."""
    
    def add_metric(self, product_id: str, duration_ms: int, success: bool, error_message: Optional[str] = None) -> bool:
        """Add a monitoring metric to the database."""
        try:
            self.db.execute(
                '''
                INSERT INTO monitoring_metrics (
                    product_id, check_duration_ms, success, error_message
                ) VALUES (?, ?, ?, ?)
                ''',
                (product_id, duration_ms, success, error_message)
            )
            self.db.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error adding metric: {e}")
            self.db.rollback()
            return False
    
    def get_monitoring_status(self, product_id: str, hours: int = 24) -> MonitoringStatus:
        """Get monitoring status for a product."""
        try:
            # Get success rate
            cursor = self.db.execute(
                '''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors,
                    MAX(timestamp) as last_check
                FROM monitoring_metrics
                WHERE product_id = ? AND timestamp >= datetime('now', '-' || ? || ' hours')
                ''',
                (product_id, hours)
            )
            row = cursor.fetchone()
            row_dict = self._row_to_dict(row)
            
            total = row_dict['total'] or 0
            successes = row_dict['successes'] or 0
            errors = row_dict['errors'] or 0
            last_check = datetime.fromisoformat(row_dict['last_check']) if row_dict['last_check'] else None
            
            success_rate = (successes / total) * 100 if total > 0 else 0
            
            # Get last error
            cursor = self.db.execute(
                '''
                SELECT error_message
                FROM monitoring_metrics
                WHERE product_id = ? AND success = 0
                ORDER BY timestamp DESC
                LIMIT 1
                ''',
                (product_id,)
            )
            error_row = cursor.fetchone()
            last_error = error_row['error_message'] if error_row else None
            
            # Get product active status
            cursor = self.db.execute(
                'SELECT is_active FROM products WHERE id = ?',
                (product_id,)
            )
            product_row = cursor.fetchone()
            is_active = bool(product_row['is_active']) if product_row else False
            
            return MonitoringStatus(
                product_id=product_id,
                is_active=is_active,
                last_check=last_check or datetime.utcnow(),
                success_rate=success_rate,
                error_count=errors,
                last_error=last_error
            )
        except Exception as e:
            self.logger.error(f"Error getting monitoring status: {e}")
            return MonitoringStatus(
                product_id=product_id,
                is_active=False,
                last_check=datetime.utcnow(),
                success_rate=0,
                error_count=0,
                last_error=str(e)
            )
    
    def get_metrics_by_product(self, product_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get metrics for a product."""
        try:
            cursor = self.db.execute(
                '''
                SELECT * FROM monitoring_metrics
                WHERE product_id = ? AND timestamp >= datetime('now', '-' || ? || ' hours')
                ORDER BY timestamp DESC
                ''',
                (product_id, hours)
            )
            rows = cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Error getting metrics by product: {e}")
            return []
    
    def get_average_duration(self, product_id: str, hours: int = 24) -> float:
        """Get average check duration for a product."""
        try:
            cursor = self.db.execute(
                '''
                SELECT AVG(check_duration_ms) as avg_duration
                FROM monitoring_metrics
                WHERE product_id = ? AND success = 1 AND timestamp >= datetime('now', '-' || ? || ' hours')
                ''',
                (product_id, hours)
            )
            row = cursor.fetchone()
            return float(row['avg_duration']) if row and row['avg_duration'] else 0.0
        except Exception as e:
            self.logger.error(f"Error getting average duration: {e}")
            return 0.0
    
    def get_total_checks_today(self) -> int:
        """Get total number of checks performed today."""
        try:
            cursor = self.db.execute(
                '''
                SELECT COUNT(*) as count
                FROM monitoring_metrics
                WHERE timestamp >= date('now')
                '''
            )
            row = cursor.fetchone()
            return row['count'] if row else 0
        except Exception as e:
            self.logger.error(f"Error getting total checks today: {e}")
            return 0