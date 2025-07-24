"""
Database connection management for SQLite.
"""
import sqlite3
import logging
import json
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime

from ..config.environment import Environment


class DatabaseConnection:
    """SQLite database connection manager."""
    
    def __init__(self, database_path: Optional[str] = None):
        """Initialize database connection manager."""
        self.logger = logging.getLogger(__name__)
        
        if database_path:
            self.database_path = database_path
        else:
            data_dir = Environment.get_data_dir()
            self.database_path = str(data_dir / "pokemon_bot.db")
        
        self.connection: Optional[sqlite3.Connection] = None
        self._ensure_directory_exists()
        
        # Register adapters and converters for datetime
        sqlite3.register_adapter(datetime, lambda dt: dt.isoformat())
        sqlite3.register_converter("TIMESTAMP", lambda dt: datetime.fromisoformat(dt.decode()))
    
    def _ensure_directory_exists(self) -> None:
        """Ensure database directory exists."""
        db_path = Path(self.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def connect(self) -> sqlite3.Connection:
        """Connect to the SQLite database."""
        if self.connection is None:
            try:
                self.connection = sqlite3.connect(
                    self.database_path,
                    detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                    check_same_thread=False
                )
                self.connection.row_factory = sqlite3.Row
                self.logger.info(f"Connected to database: {self.database_path}")
            except sqlite3.Error as e:
                self.logger.error(f"Database connection error: {e}")
                raise
        
        return self.connection
    
    def close(self) -> None:
        """Close the database connection."""
        if self.connection:
            try:
                self.connection.close()
                self.connection = None
                self.logger.info("Database connection closed")
            except sqlite3.Error as e:
                self.logger.error(f"Error closing database connection: {e}")
    
    def execute(self, query: str, params: Tuple = ()) -> sqlite3.Cursor:
        """Execute a SQL query."""
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor
        except sqlite3.Error as e:
            self.logger.error(f"Query execution error: {e}")
            self.logger.error(f"Query: {query}")
            self.logger.error(f"Params: {params}")
            raise
    
    def execute_many(self, query: str, params_list: list) -> sqlite3.Cursor:
        """Execute a SQL query with multiple parameter sets."""
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            return cursor
        except sqlite3.Error as e:
            self.logger.error(f"Query execution error: {e}")
            self.logger.error(f"Query: {query}")
            raise
    
    def commit(self) -> None:
        """Commit the current transaction."""
        if self.connection:
            try:
                self.connection.commit()
            except sqlite3.Error as e:
                self.logger.error(f"Commit error: {e}")
                raise
    
    def rollback(self) -> None:
        """Rollback the current transaction."""
        if self.connection:
            try:
                self.connection.rollback()
            except sqlite3.Error as e:
                self.logger.error(f"Rollback error: {e}")
                raise
    
    def create_tables(self) -> None:
        """Create database tables if they don't exist."""
        try:
            # Products table
            self.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    url_type TEXT NOT NULL,
                    channel_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    monitoring_interval INTEGER DEFAULT 60,
                    role_mentions TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Product status tracking
            self.execute('''
                CREATE TABLE IF NOT EXISTS product_status (
                    product_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    price TEXT NOT NULL,
                    original_price TEXT,
                    image_url TEXT,
                    product_url TEXT NOT NULL,
                    uncached_url TEXT,
                    stock_status TEXT NOT NULL,
                    stock_level TEXT,
                    website TEXT,
                    delivery_info TEXT,
                    sold_by_bol BOOLEAN,
                    last_checked TIMESTAMP NOT NULL,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
                )
            ''')
            
            # Stock change history
            self.execute('''
                CREATE TABLE IF NOT EXISTS stock_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL,
                    previous_status TEXT NOT NULL,
                    current_status TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    price_change TEXT,
                    notification_sent BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
                )
            ''')
            
            # Performance metrics
            self.execute('''
                CREATE TABLE IF NOT EXISTS monitoring_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL,
                    check_duration_ms INTEGER NOT NULL,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
                )
            ''')
            
            # Create indexes for performance
            self._create_indexes()
            
            self.commit()
            self.logger.info("Database tables created successfully")
        except sqlite3.Error as e:
            self.rollback()
            self.logger.error(f"Error creating database tables: {e}")
            raise
    
    def _create_indexes(self) -> None:
        """Create indexes for better query performance."""
        try:
            # Index for product status lookups
            self.execute('''
                CREATE INDEX IF NOT EXISTS idx_product_status_product_id 
                ON product_status(product_id)
            ''')
            
            # Index for stock changes by product
            self.execute('''
                CREATE INDEX IF NOT EXISTS idx_stock_changes_product_id 
                ON stock_changes(product_id)
            ''')
            
            # Index for stock changes by timestamp
            self.execute('''
                CREATE INDEX IF NOT EXISTS idx_stock_changes_timestamp 
                ON stock_changes(timestamp)
            ''')
            
            # Index for metrics by product
            self.execute('''
                CREATE INDEX IF NOT EXISTS idx_metrics_product_id 
                ON monitoring_metrics(product_id)
            ''')
            
            # Index for metrics by timestamp
            self.execute('''
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp 
                ON monitoring_metrics(timestamp)
            ''')
            
            # Index for products by channel
            self.execute('''
                CREATE INDEX IF NOT EXISTS idx_products_channel_id 
                ON products(channel_id)
            ''')
            
            # Index for active products
            self.execute('''
                CREATE INDEX IF NOT EXISTS idx_products_is_active 
                ON products(is_active)
            ''')
            
            self.commit()
            self.logger.info("Database indexes created successfully")
        except sqlite3.Error as e:
            self.rollback()
            self.logger.error(f"Error creating database indexes: {e}")
            raise
    
    def run_migrations(self, version: int = None) -> int:
        """Run database migrations to update schema."""
        current_version = self._get_db_version()
        target_version = version or len(self._get_migrations())
        
        if current_version >= target_version:
            self.logger.info(f"Database already at version {current_version}, no migrations needed")
            return current_version
            
        self.logger.info(f"Running migrations from version {current_version} to {target_version}")
        
        migrations = self._get_migrations()
        for i in range(current_version, target_version):
            migration = migrations[i]
            self.logger.info(f"Running migration {i+1}: {migration['description']}")
            
            try:
                for query in migration['queries']:
                    self.execute(query)
                self.commit()
            except sqlite3.Error as e:
                self.rollback()
                self.logger.error(f"Migration {i+1} failed: {e}")
                raise
                
        self._set_db_version(target_version)
        self.logger.info(f"Database migrated to version {target_version}")
        return target_version
    
    def _get_db_version(self) -> int:
        """Get current database version."""
        try:
            # Create version table if it doesn't exist
            self.execute('''
                CREATE TABLE IF NOT EXISTS db_version (
                    version INTEGER PRIMARY KEY
                )
            ''')
            self.commit()
            
            # Get current version
            cursor = self.execute('SELECT version FROM db_version')
            row = cursor.fetchone()
            
            if row:
                return row[0]
            else:
                # Initialize version to 0 if not set
                self.execute('INSERT INTO db_version (version) VALUES (0)')
                self.commit()
                return 0
                
        except sqlite3.Error as e:
            self.logger.error(f"Error getting database version: {e}")
            return 0
    
    def _set_db_version(self, version: int) -> None:
        """Set current database version."""
        try:
            self.execute('UPDATE db_version SET version = ?', (version,))
            self.commit()
        except sqlite3.Error as e:
            self.rollback()
            self.logger.error(f"Error setting database version: {e}")
            raise
    
    def _get_migrations(self) -> List[Dict[str, Any]]:
        """Get list of migrations to apply."""
        return [
            {
                'description': 'Add price_change column to stock_changes table',
                'queries': []  # Skip this migration as column already exists
            },
            {
                'description': 'Add cascade delete constraints',
                'queries': [
                    '''
                    PRAGMA foreign_keys = OFF;
                    ''',
                    '''
                    CREATE TABLE product_status_new (
                        product_id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        price TEXT NOT NULL,
                        original_price TEXT,
                        image_url TEXT,
                        product_url TEXT NOT NULL,
                        uncached_url TEXT,
                        stock_status TEXT NOT NULL,
                        stock_level TEXT,
                        website TEXT,
                        delivery_info TEXT,
                        sold_by_bol BOOLEAN,
                        last_checked TIMESTAMP NOT NULL,
                        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
                    );
                    ''',
                    '''
                    INSERT INTO product_status_new
                    SELECT * FROM product_status;
                    ''',
                    '''
                    DROP TABLE product_status;
                    ''',
                    '''
                    ALTER TABLE product_status_new RENAME TO product_status;
                    ''',
                    '''
                    PRAGMA foreign_keys = ON;
                    '''
                ]
            },
            {
                'description': 'Add notification delivery status tracking',
                'queries': [
                    '''
                    CREATE TABLE IF NOT EXISTS notification_delivery_status (
                        notification_id TEXT PRIMARY KEY,
                        product_id TEXT NOT NULL,
                        channel_id INTEGER NOT NULL,
                        delivery_attempts INTEGER DEFAULT 0,
                        last_attempt TIMESTAMP,
                        delivered BOOLEAN DEFAULT FALSE,
                        delivered_at TIMESTAMP,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
                    )
                    ''',
                    '''
                    CREATE INDEX IF NOT EXISTS idx_notification_delivery_product_id 
                    ON notification_delivery_status(product_id)
                    ''',
                    '''
                    CREATE INDEX IF NOT EXISTS idx_notification_delivery_channel_id 
                    ON notification_delivery_status(channel_id)
                    ''',
                    '''
                    CREATE INDEX IF NOT EXISTS idx_notification_delivery_delivered 
                    ON notification_delivery_status(delivered)
                    '''
                ]
            },
            {
                'description': 'Add notification styles table',
                'queries': [
                    '''
                    CREATE TABLE IF NOT EXISTS notification_styles (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        embed_color INTEGER NOT NULL,
                        use_thumbnail BOOLEAN DEFAULT TRUE,
                        use_footer BOOLEAN DEFAULT TRUE,
                        compact_mode BOOLEAN DEFAULT FALSE,
                        show_price_history BOOLEAN DEFAULT FALSE,
                        emoji_style TEXT DEFAULT 'default',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    ''',
                    '''
                    CREATE TABLE IF NOT EXISTS product_notification_styles (
                        product_id TEXT NOT NULL,
                        style_id TEXT NOT NULL,
                        PRIMARY KEY (product_id, style_id),
                        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
                        FOREIGN KEY (style_id) REFERENCES notification_styles(id) ON DELETE CASCADE
                    )
                    ''',
                    '''
                    CREATE INDEX IF NOT EXISTS idx_product_notification_styles_product_id 
                    ON product_notification_styles(product_id)
                    '''
                ]
            },
            {
                'description': 'Add notification batching and scheduling tables',
                'queries': [
                    '''
                    CREATE TABLE IF NOT EXISTS notification_batches (
                        batch_id TEXT PRIMARY KEY,
                        channel_id INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed_at TIMESTAMP,
                        window_seconds INTEGER DEFAULT 60,
                        status TEXT DEFAULT 'pending'
                    )
                    ''',
                    '''
                    CREATE TABLE IF NOT EXISTS scheduled_notifications (
                        notification_id TEXT PRIMARY KEY,
                        product_id TEXT NOT NULL,
                        channel_id INTEGER NOT NULL,
                        scheduled_time TIMESTAMP NOT NULL,
                        priority INTEGER DEFAULT 1,
                        batch_id TEXT,
                        embed_data TEXT NOT NULL,
                        role_mentions TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed BOOLEAN DEFAULT FALSE,
                        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
                        FOREIGN KEY (batch_id) REFERENCES notification_batches(batch_id) ON DELETE SET NULL
                    )
                    ''',
                    '''
                    CREATE INDEX IF NOT EXISTS idx_scheduled_notifications_product_id 
                    ON scheduled_notifications(product_id)
                    ''',
                    '''
                    CREATE INDEX IF NOT EXISTS idx_scheduled_notifications_scheduled_time 
                    ON scheduled_notifications(scheduled_time)
                    ''',
                    '''
                    CREATE INDEX IF NOT EXISTS idx_scheduled_notifications_processed 
                    ON scheduled_notifications(processed)
                    '''
                ]
            },
            {
                'description': 'Add price history tracking',
                'queries': [
                    '''
                    CREATE TABLE IF NOT EXISTS price_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id TEXT NOT NULL,
                        price TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
                    )
                    ''',
                    '''
                    CREATE INDEX IF NOT EXISTS idx_price_history_product_id 
                    ON price_history(product_id)
                    ''',
                    '''
                    CREATE INDEX IF NOT EXISTS idx_price_history_timestamp 
                    ON price_history(timestamp)
                    '''
                ]
            },
            {
                'description': 'Add price thresholds for third-party seller detection',
                'queries': [
                    '''
                    CREATE TABLE IF NOT EXISTS price_thresholds (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        keyword TEXT NOT NULL UNIQUE,
                        max_price REAL NOT NULL,
                        created_by TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    ''',
                    '''
                    CREATE INDEX IF NOT EXISTS idx_price_thresholds_keyword 
                    ON price_thresholds(keyword)
                    '''
                ]
            },
            {
                'description': 'Add website intervals for domain-based monitoring intervals',
                'queries': [
                    '''
                    CREATE TABLE IF NOT EXISTS website_intervals (
                        domain TEXT PRIMARY KEY,
                        interval_seconds INTEGER NOT NULL DEFAULT 10,
                        created_by TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    ''',
                    '''
                    CREATE INDEX IF NOT EXISTS idx_website_intervals_domain 
                    ON website_intervals(domain)
                    ''',
                    '''
                    INSERT OR IGNORE INTO website_intervals (domain, interval_seconds, created_by) 
                    VALUES ('bol.com', 1, 'system_migration')
                    '''
                ]
            },
            {
                'description': 'Remove per-product monitoring intervals (use domain-based instead)',
                'queries': [
                    '''
                    PRAGMA foreign_keys = OFF;
                    ''',
                    '''
                    CREATE TABLE products_new (
                        id TEXT PRIMARY KEY,
                        url TEXT NOT NULL,
                        url_type TEXT NOT NULL,
                        channel_id INTEGER NOT NULL,
                        guild_id INTEGER NOT NULL,
                        role_mentions TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    ''',
                    '''
                    INSERT INTO products_new (id, url, url_type, channel_id, guild_id, role_mentions, is_active, created_at, updated_at)
                    SELECT id, url, url_type, channel_id, guild_id, role_mentions, is_active, created_at, updated_at
                    FROM products;
                    ''',
                    '''
                    DROP TABLE products;
                    ''',
                    '''
                    ALTER TABLE products_new RENAME TO products;
                    ''',
                    '''
                    CREATE INDEX IF NOT EXISTS idx_products_channel_id 
                    ON products(channel_id);
                    ''',
                    '''
                    CREATE INDEX IF NOT EXISTS idx_products_is_active 
                    ON products(is_active);
                    ''',
                    '''
                    PRAGMA foreign_keys = ON;
                    '''
                ]
            },
            {
                'description': 'Add monitoring_interval column back to products table',
                'queries': [
                    '''
                    ALTER TABLE products ADD COLUMN monitoring_interval INTEGER DEFAULT 60;
                    ''',
                    '''
                    UPDATE products SET monitoring_interval = 60 WHERE monitoring_interval IS NULL;
                    '''
                ]
            }
        ]


# Global database connection instance
db = DatabaseConnection()