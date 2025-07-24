"""
Repository for managing price thresholds in the database.
"""
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from .connection import db


class PriceThresholdRepository:
    """Repository for price threshold database operations."""
    
    def __init__(self):
        """Initialize the repository."""
        self.logger = logging.getLogger(__name__)
    
    def add_threshold(self, keyword: str, max_price: float, created_by: str) -> bool:
        """
        Add a new price threshold.
        
        Args:
            keyword: Product keyword to match
            max_price: Maximum reasonable price
            created_by: User who created the threshold
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cursor = db.execute(
                '''INSERT INTO price_thresholds (keyword, max_price, created_by) 
                   VALUES (?, ?, ?)''',
                (keyword, max_price, created_by)
            )
            db.commit()
            self.logger.info(f"Added price threshold: {keyword} -> €{max_price} by {created_by}")
            return True
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error adding price threshold: {e}")
            return False
    
    def update_threshold(self, keyword: str, max_price: float, updated_by: str) -> bool:
        """
        Update an existing price threshold.
        
        Args:
            keyword: Product keyword to update
            max_price: New maximum reasonable price
            updated_by: User who updated the threshold
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cursor = db.execute(
                '''UPDATE price_thresholds 
                   SET max_price = ?, updated_at = CURRENT_TIMESTAMP 
                   WHERE keyword = ?''',
                (max_price, keyword)
            )
            db.commit()
            
            if cursor.rowcount > 0:
                self.logger.info(f"Updated price threshold: {keyword} -> €{max_price} by {updated_by}")
                return True
            else:
                self.logger.warning(f"No threshold found to update for keyword: {keyword}")
                return False
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error updating price threshold: {e}")
            return False
    
    def remove_threshold(self, keyword: str) -> bool:
        """
        Remove a price threshold.
        
        Args:
            keyword: Product keyword to remove
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cursor = db.execute(
                'DELETE FROM price_thresholds WHERE keyword = ?',
                (keyword,)
            )
            db.commit()
            
            if cursor.rowcount > 0:
                self.logger.info(f"Removed price threshold: {keyword}")
                return True
            else:
                self.logger.warning(f"No threshold found to remove for keyword: {keyword}")
                return False
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error removing price threshold: {e}")
            return False
    
    def get_threshold(self, keyword: str) -> Optional[Tuple[str, float, str, datetime]]:
        """
        Get a specific price threshold.
        
        Args:
            keyword: Product keyword to search for
            
        Returns:
            Tuple of (keyword, max_price, created_by, created_at) or None
        """
        try:
            cursor = db.execute(
                'SELECT keyword, max_price, created_by, created_at FROM price_thresholds WHERE keyword = ?',
                (keyword,)
            )
            row = cursor.fetchone()
            
            if row:
                return (row[0], row[1], row[2], row[3])
            return None
        except Exception as e:
            self.logger.error(f"Error getting price threshold: {e}")
            return None
    
    def get_all_thresholds(self) -> List[Tuple[str, float, str, datetime]]:
        """
        Get all price thresholds.
        
        Returns:
            List of tuples (keyword, max_price, created_by, created_at)
        """
        try:
            cursor = db.execute(
                '''SELECT keyword, max_price, created_by, created_at 
                   FROM price_thresholds 
                   ORDER BY keyword'''
            )
            return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Error getting all price thresholds: {e}")
            return []
    
    def get_thresholds_dict(self) -> Dict[str, float]:
        """
        Get all price thresholds as a dictionary for easy lookup.
        
        Returns:
            Dictionary mapping keywords to max prices
        """
        try:
            cursor = db.execute(
                'SELECT keyword, max_price FROM price_thresholds'
            )
            return {row[0]: row[1] for row in cursor.fetchall()}
        except Exception as e:
            self.logger.error(f"Error getting price thresholds dict: {e}")
            return {}
    
    def search_thresholds(self, search_term: str) -> List[Tuple[str, float, str, datetime]]:
        """
        Search for price thresholds by keyword.
        
        Args:
            search_term: Term to search for in keywords
            
        Returns:
            List of matching thresholds
        """
        try:
            cursor = db.execute(
                '''SELECT keyword, max_price, created_by, created_at 
                   FROM price_thresholds 
                   WHERE keyword LIKE ? 
                   ORDER BY keyword''',
                (f'%{search_term}%',)
            )
            return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Error searching price thresholds: {e}")
            return []