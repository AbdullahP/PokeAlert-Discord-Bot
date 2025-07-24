"""
Price tracking service for monitoring price changes.
"""
import logging
import re
from typing import Optional, Tuple
from datetime import datetime

from ..models.product_data import ProductData, PriceChange
from ..database.notification_repository import NotificationRepository


class PriceTrackingService:
    """Service for tracking and analyzing price changes."""
    
    def __init__(self):
        """Initialize price tracking service."""
        self.logger = logging.getLogger(__name__)
        self.notification_repo = NotificationRepository()
    
    def detect_price_change(self, current_product: ProductData, 
                           previous_product: Optional[ProductData]) -> Optional[PriceChange]:
        """
        Detect price changes between current and previous product data.
        
        Args:
            current_product: Current product data
            previous_product: Previous product data or None if first check
            
        Returns:
            PriceChange object if price changed, None otherwise
        """
        if not previous_product:
            # First check, record initial price
            self._record_price(current_product)
            return None
            
        # Extract prices as numeric values
        current_price_value = self._extract_price_value(current_product.price)
        previous_price_value = self._extract_price_value(previous_product.price)
        
        # Check if price changed
        if current_price_value != previous_price_value:
            # Calculate change amount and percentage
            change_amount = current_price_value - previous_price_value
            change_percentage = (change_amount / previous_price_value) * 100 if previous_price_value else 0
            
            # Format change amount
            if change_amount >= 0:
                change_amount_str = f"€{change_amount:.2f}"
            else:
                change_amount_str = f"€{change_amount:.2f}"
            
            # Create price change object
            price_change = PriceChange(
                previous_price=previous_product.price,
                current_price=current_product.price,
                change_amount=change_amount_str,
                change_percentage=change_percentage
            )
            
            # Record new price
            self._record_price(current_product)
            
            return price_change
        
        return None
    
    def _extract_price_value(self, price_str: str) -> float:
        """
        Extract numeric value from price string.
        
        Args:
            price_str: Price string (e.g. "€59.99")
            
        Returns:
            Numeric price value
        """
        try:
            # Remove currency symbol and any non-numeric characters except decimal point
            numeric_str = re.sub(r'[^0-9.,]', '', price_str)
            
            # Replace comma with dot for decimal point if needed
            numeric_str = numeric_str.replace(',', '.')
            
            # Convert to float
            return float(numeric_str)
        except (ValueError, TypeError):
            self.logger.warning(f"Failed to extract price value from '{price_str}'")
            return 0.0
    
    def _record_price(self, product: ProductData) -> None:
        """
        Record price in price history.
        
        Args:
            product: Product data
        """
        try:
            self.notification_repo.add_price_history(product.product_id, product.price)
        except Exception as e:
            self.logger.error(f"Error recording price history: {e}")
    
    async def get_price_history(self, product_id: str, limit: int = 10) -> list:
        """
        Get price history for a product.
        
        Args:
            product_id: Product ID
            limit: Maximum number of history entries
            
        Returns:
            List of (price, timestamp) tuples
        """
        try:
            return self.notification_repo.get_price_history(product_id, limit)
        except Exception as e:
            self.logger.error(f"Error getting price history: {e}")
            return []
    
    def is_significant_price_change(self, price_change: PriceChange, threshold_percent: float = 5.0) -> bool:
        """
        Check if a price change is significant enough to notify.
        
        Args:
            price_change: Price change object
            threshold_percent: Percentage threshold for significance
            
        Returns:
            True if change is significant, False otherwise
        """
        return abs(price_change.change_percentage) >= threshold_percent