"""
Discord API metrics decorator for tracking Discord API operations.
"""
import time
import functools
import logging
from typing import Callable, Any
import discord

# Global performance monitor instance (will be set by main.py)
_performance_monitor = None

def set_performance_monitor(monitor):
    """Set the global performance monitor instance."""
    global _performance_monitor
    _performance_monitor = monitor

def discord_metrics(endpoint: str):
    """
    Decorator for tracking Discord API operation metrics.
    
    Args:
        endpoint: Discord API endpoint or operation name
        
    Returns:
        Decorated function that tracks execution time and rate limits
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            status_code = 200  # Default to success
            
            try:
                result = await func(*args, **kwargs)
                return result
            except discord.errors.HTTPException as e:
                status_code = e.status
                raise
            except Exception:
                status_code = 500  # Generic error
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                
                # Record metrics if performance monitor is available
                if _performance_monitor:
                    _performance_monitor.record_discord_request(
                        endpoint, duration_ms, status_code
                    )
                
                # Log rate limits
                if status_code == 429:
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Discord rate limit hit for endpoint: {endpoint}")
        
        return wrapper
    
    return decorator