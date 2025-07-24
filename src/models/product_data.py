"""
Core data models for the Pokemon Discord Bot monitoring system.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import json
import uuid


class StockStatus(Enum):
    """Stock status enumeration."""
    IN_STOCK = "In Stock"
    OUT_OF_STOCK = "Out of Stock"
    PRE_ORDER = "Pre-order"
    UNKNOWN = "Unknown"


class URLType(Enum):
    """URL type enumeration."""
    WISHLIST = "wishlist"
    PRODUCT = "product"
    
    @staticmethod
    def is_wishlist(url: str) -> bool:
        """Check if URL is a wishlist URL."""
        return "verlanglijstje" in url.lower() or "wishlist" in url.lower()


@dataclass
class ProductData:
    """Enhanced product data schema from existing scraper."""
    title: str
    price: str
    original_price: str
    image_url: str
    product_url: str
    uncached_url: str
    stock_status: str
    stock_level: str
    website: str
    delivery_info: str
    sold_by_bol: bool
    last_checked: datetime
    product_id: str  # Unique identifier
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        data = asdict(self)
        data['last_checked'] = data['last_checked'].isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProductData':
        """Create instance from dictionary."""
        if isinstance(data.get('last_checked'), str):
            data['last_checked'] = datetime.fromisoformat(data['last_checked'])
        return cls(**data)
    
    def validate(self) -> bool:
        """Validate product data."""
        if not self.title or not self.product_url or not self.product_id:
            return False
        
        # Validate stock status is one of the enum values
        valid_statuses = [status.value for status in StockStatus]
        if self.stock_status not in valid_statuses:
            return False
            
        return True


@dataclass
class ProductConfig:
    """Product configuration for monitoring."""
    product_id: str
    url: str
    url_type: str  # URLType enum value
    channel_id: int
    guild_id: int
    monitoring_interval: int = 60  # seconds
    role_mentions: List[str] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.role_mentions is None:
            self.role_mentions = []
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        data = asdict(self)
        data['created_at'] = data['created_at'].isoformat()
        data['updated_at'] = data['updated_at'].isoformat()
        data['role_mentions'] = json.dumps(data['role_mentions'])
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProductConfig':
        """Create instance from dictionary."""
        if isinstance(data.get('role_mentions'), str):
            data['role_mentions'] = json.loads(data['role_mentions'])
        
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
            
        if isinstance(data.get('updated_at'), str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        
        # Convert SQLite integer boolean (0/1) to Python boolean
        if 'is_active' in data:
            data['is_active'] = bool(data['is_active'])
            
        return cls(**data)
    
    @classmethod
    def create_new(cls, url: str, url_type: str, channel_id: int, guild_id: int, 
                  monitoring_interval: int = 60) -> 'ProductConfig':
        """Create a new product configuration with generated ID."""
        product_id = str(uuid.uuid4())
        return cls(
            product_id=product_id,
            url=url,
            url_type=url_type,
            channel_id=channel_id,
            guild_id=guild_id,
            monitoring_interval=monitoring_interval
        )
    
    def validate(self) -> bool:
        """Validate product configuration."""
        if not self.product_id or not self.url:
            return False
            
        # Validate URL type is one of the enum values
        valid_types = [url_type.value for url_type in URLType]
        if self.url_type not in valid_types:
            return False
            
        # Validate monitoring interval is reasonable
        if self.monitoring_interval < 30:  # Minimum 30 seconds
            return False
            
        return True


@dataclass
class PriceChange:
    """Price change information."""
    previous_price: str
    current_price: str
    change_amount: str
    change_percentage: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PriceChange':
        """Create instance from dictionary."""
        return cls(**data)


@dataclass
class StockChange:
    """Stock change event data."""
    product_id: str
    previous_status: str
    current_status: str
    timestamp: datetime
    price_change: Optional[PriceChange] = None
    notification_sent: bool = False
    id: Optional[int] = None  # Database ID
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        data = asdict(self)
        data['timestamp'] = data['timestamp'].isoformat()
        
        if data['price_change']:
            data['price_change'] = json.dumps(data['price_change'].to_dict())
        else:
            data['price_change'] = None
            
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StockChange':
        """Create instance from dictionary."""
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
            
        if data.get('price_change'):
            if isinstance(data['price_change'], str):
                price_change_data = json.loads(data['price_change'])
            else:
                price_change_data = data['price_change']
            data['price_change'] = PriceChange.from_dict(price_change_data)
            
        return cls(**data)
    
    def validate(self) -> bool:
        """Validate stock change data."""
        if not self.product_id:
            return False
            
        # Validate status values are from the enum
        valid_statuses = [status.value for status in StockStatus]
        if (self.previous_status not in valid_statuses and self.previous_status != "Unknown") or \
           (self.current_status not in valid_statuses and self.current_status != "Unknown"):
            return False
            
        return True


@dataclass
class MonitoringStatus:
    """Monitoring status for a product."""
    product_id: str
    is_active: bool
    last_check: datetime
    success_rate: float
    error_count: int
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['last_check'] = data['last_check'].isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MonitoringStatus':
        """Create instance from dictionary."""
        if isinstance(data.get('last_check'), str):
            data['last_check'] = datetime.fromisoformat(data['last_check'])
        return cls(**data)


@dataclass
class DashboardData:
    """Dashboard data aggregation."""
    total_products: int
    active_products: int
    total_checks_today: int
    success_rate: float
    recent_stock_changes: List[StockChange]
    error_summary: dict
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['recent_stock_changes'] = [
            change.to_dict() for change in data['recent_stock_changes']
        ]
        return data


@dataclass
class NotificationStyle:
    """Notification style customization."""
    embed_color: int = 0x00ff00  # Default green
    use_thumbnail: bool = True
    use_footer: bool = True
    compact_mode: bool = False
    show_price_history: bool = False
    emoji_style: str = "default"  # default, minimal, none
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NotificationStyle':
        """Create instance from dictionary."""
        return cls(**data)


@dataclass
class NotificationDeliveryStatus:
    """Notification delivery status tracking."""
    notification_id: str
    channel_id: int
    product_id: str
    delivery_attempts: int = 0
    last_attempt: Optional[datetime] = None
    delivered: bool = False
    delivered_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        if data['last_attempt']:
            data['last_attempt'] = data['last_attempt'].isoformat()
        if data['delivered_at']:
            data['delivered_at'] = data['delivered_at'].isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NotificationDeliveryStatus':
        """Create instance from dictionary."""
        if isinstance(data.get('last_attempt'), str):
            data['last_attempt'] = datetime.fromisoformat(data['last_attempt'])
        if isinstance(data.get('delivered_at'), str):
            data['delivered_at'] = datetime.fromisoformat(data['delivered_at'])
        return cls(**data)


@dataclass
class Notification:
    """Enhanced notification data structure."""
    product_id: str
    channel_id: int
    embed_data: dict
    role_mentions: List[str]
    timestamp: datetime
    product_url: Optional[str] = None  # Product URL for the view
    uncached_url: Optional[str] = None  # Uncached URL for the button
    notification_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    retry_count: int = 0
    max_retries: int = 3
    priority: int = 1  # 1=high (stock changes), 2=medium (price drops), 3=low (other updates)
    scheduled_time: Optional[datetime] = None  # For scheduled notifications
    batch_id: Optional[str] = None  # For grouping notifications in batches
    style: NotificationStyle = field(default_factory=NotificationStyle)
    delivery_status: Optional[NotificationDeliveryStatus] = None
    
    def __post_init__(self):
        """Initialize delivery status if not provided."""
        if self.delivery_status is None:
            self.delivery_status = NotificationDeliveryStatus(
                notification_id=self.notification_id,
                channel_id=self.channel_id,
                product_id=self.product_id
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['timestamp'] = data['timestamp'].isoformat()
        if data['scheduled_time']:
            data['scheduled_time'] = data['scheduled_time'].isoformat()
        data['style'] = data['style'].to_dict() if data['style'] else None
        data['delivery_status'] = data['delivery_status'].to_dict() if data['delivery_status'] else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Notification':
        """Create instance from dictionary."""
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if isinstance(data.get('scheduled_time'), str):
            data['scheduled_time'] = datetime.fromisoformat(data['scheduled_time'])
        
        # Convert nested objects
        if 'style' in data and data['style']:
            data['style'] = NotificationStyle.from_dict(data['style'])
        if 'delivery_status' in data and data['delivery_status']:
            data['delivery_status'] = NotificationDeliveryStatus.from_dict(data['delivery_status'])
            
        return cls(**data)