"""
Database metrics decorator for tracking database operations.
"""
import time
import functools
import logging
from typing import Callable, Any

# Global performance monitor instance (will be set by main.py)
_performance_monitor = None

def set_performance_monitor(monitor):
    """Set the global performance monitor instance."""
    global _performance_monitor
    _performance_monitor = monitor

def db_metrics(operation_type: str):
    """
    Decorator for tracking database operation metrics.
    
    Args:
        operation_type: Type of database operation (e.g., 'query', 'insert')
        
    Returns:
        Decorated function that tracks execution time and success/failure
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            success = True
            error = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error = e
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                
                # Record metrics if performance monitor is available
                if _performance_monitor:
                    _performance_monitor.record_db_operation(
                        operation_type, duration_ms, success
                    )
                
                # Log slow operations
                if duration_ms > 100:  # Log operations taking more than 100ms
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Slow database operation: {operation_type} took {duration_ms:.2f}ms"
                        + (f" (Error: {error})" if error else "")
                    )
        
        return wrapper
    
    return decorator