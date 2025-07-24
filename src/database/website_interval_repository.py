"""
Repository for managing website monitoring intervals in the database.
"""
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from urllib.parse import urlparse

from .connection import db


class WebsiteIntervalRepository:
    """Repository for website interval database operations."""
    
    def __init__(self):
        """Initialize the repository."""
        self.logger = logging.getLogger(__name__)
    
    def extract_domain(self, url: str) -> str:
        """
        Extract domain from URL.
        
        Args:
            url: Full URL
            
        Returns:
            Domain name (e.g., 'bol.com')
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix if present
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except Exception as e:
            self.logger.error(f"Error extracting domain from URL {url}: {e}")
            return "unknown"
    
    def set_interval(self, domain: str, interval_seconds: int, updated_by: str) -> bool:
        """
        Set monitoring interval for a domain.
        
        Args:
            domain: Domain name (e.g., 'bol.com')
            interval_seconds: Monitoring interval in seconds
            updated_by: User who set the interval
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Use INSERT OR REPLACE to handle both new and existing domains
            cursor = db.execute(
                '''INSERT OR REPLACE INTO website_intervals 
                   (domain, interval_seconds, updated_at, created_by) 
                   VALUES (?, ?, CURRENT_TIMESTAMP, ?)''',
                (domain.lower(), interval_seconds, updated_by)
            )
            db.commit()
            self.logger.info(f"Set interval for {domain}: {interval_seconds}s by {updated_by}")
            return True
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error setting interval for {domain}: {e}")
            return False
    
    def get_interval(self, domain: str, default_interval: int = 10) -> int:
        """
        Get monitoring interval for a domain.
        
        Args:
            domain: Domain name
            default_interval: Default interval if not set
            
        Returns:
            Interval in seconds
        """
        try:
            cursor = db.execute(
                'SELECT interval_seconds FROM website_intervals WHERE domain = ?',
                (domain.lower(),)
            )
            row = cursor.fetchone()
            
            if row:
                return row[0]
            else:
                return default_interval
        except Exception as e:
            self.logger.error(f"Error getting interval for {domain}: {e}")
            return default_interval
    
    def get_interval_for_url(self, url: str, default_interval: int = 10) -> int:
        """
        Get monitoring interval for a URL by extracting its domain.
        
        Args:
            url: Full URL
            default_interval: Default interval if not set
            
        Returns:
            Interval in seconds
        """
        domain = self.extract_domain(url)
        return self.get_interval(domain, default_interval)
    
    def get_all_intervals(self) -> List[Tuple[str, int, str, datetime]]:
        """
        Get all website intervals.
        
        Returns:
            List of tuples (domain, interval_seconds, created_by, updated_at)
        """
        try:
            cursor = db.execute(
                '''SELECT domain, interval_seconds, created_by, updated_at 
                   FROM website_intervals 
                   ORDER BY domain'''
            )
            return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Error getting all intervals: {e}")
            return []
    
    def get_intervals_dict(self) -> Dict[str, int]:
        """
        Get all website intervals as a dictionary for easy lookup.
        
        Returns:
            Dictionary mapping domains to intervals
        """
        try:
            cursor = db.execute(
                'SELECT domain, interval_seconds FROM website_intervals'
            )
            return {row[0]: row[1] for row in cursor.fetchall()}
        except Exception as e:
            self.logger.error(f"Error getting intervals dict: {e}")
            return {}
    
    def remove_interval(self, domain: str) -> bool:
        """
        Remove interval setting for a domain (will use default).
        
        Args:
            domain: Domain name to remove
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cursor = db.execute(
                'DELETE FROM website_intervals WHERE domain = ?',
                (domain.lower(),)
            )
            db.commit()
            
            if cursor.rowcount > 0:
                self.logger.info(f"Removed interval setting for {domain}")
                return True
            else:
                self.logger.warning(f"No interval setting found for {domain}")
                return False
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error removing interval for {domain}: {e}")
            return False
    
    def get_domain_stats(self, domain: str) -> Dict[str, any]:
        """
        Get statistics for a domain (interval + product count).
        
        Args:
            domain: Domain name
            
        Returns:
            Dictionary with domain statistics
        """
        try:
            # Get interval
            interval = self.get_interval(domain)
            
            # Count products for this domain
            cursor = db.execute(
                '''SELECT COUNT(*) FROM products 
                   WHERE url LIKE ? OR url LIKE ?''',
                (f'%{domain}%', f'%www.{domain}%')
            )
            product_count = cursor.fetchone()[0]
            
            # Get interval info if custom set
            cursor = db.execute(
                'SELECT created_by, updated_at FROM website_intervals WHERE domain = ?',
                (domain.lower(),)
            )
            interval_info = cursor.fetchone()
            
            return {
                'domain': domain,
                'interval_seconds': interval,
                'product_count': product_count,
                'is_custom': interval_info is not None,
                'created_by': interval_info[0] if interval_info else None,
                'updated_at': interval_info[1] if interval_info else None
            }
        except Exception as e:
            self.logger.error(f"Error getting domain stats for {domain}: {e}")
            return {
                'domain': domain,
                'interval_seconds': 10,
                'product_count': 0,
                'is_custom': False,
                'created_by': None,
                'updated_at': None
            }