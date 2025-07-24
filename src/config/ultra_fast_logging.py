
# Ultra-speed logging configuration
import logging

class UltraFastLogger:
    """Minimal overhead logging for maximum speed."""
    
    def __init__(self):
        # Disable debug logging in production
        logging.getLogger().setLevel(logging.WARNING)
        
        # Disable verbose monitoring logs
        logging.getLogger('src.services.monitoring_engine').setLevel(logging.ERROR)
        logging.getLogger('aiohttp').setLevel(logging.ERROR)
        logging.getLogger('discord').setLevel(logging.ERROR)
        
        # Create speed-optimized formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Use async logging handler
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.addHandler(handler)
    
    @staticmethod
    def log_speed_metric(operation: str, duration: float, count: int = 1):
        """Log only critical speed metrics."""
        if duration > 1.0:  # Only log if slower than 1 second
            logging.warning(f"SLOW OPERATION: {operation} took {duration:.3f}s for {count} items")
        else:
            logging.info(f"FAST: {operation} completed in {duration:.3f}s ({count} items)")
