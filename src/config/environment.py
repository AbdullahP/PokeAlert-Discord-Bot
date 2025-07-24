"""
Environment-specific configuration handling.
"""
import os
import sys
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
import json

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, skip loading .env file
    pass


class Environment:
    """Environment configuration handler."""
    
    @staticmethod
    def get_env() -> str:
        """Get current environment (development, production, testing)."""
        return os.getenv('ENVIRONMENT', 'development').lower()
    
    @staticmethod
    def is_development() -> bool:
        """Check if running in development environment."""
        return Environment.get_env() == 'development'
    
    @staticmethod
    def is_production() -> bool:
        """Check if running in production environment."""
        return Environment.get_env() == 'production'
    
    @staticmethod
    def is_testing() -> bool:
        """Check if running in testing environment."""
        return Environment.get_env() == 'testing'
    
    @staticmethod
    def get_data_dir() -> Path:
        """Get data directory path."""
        data_dir = os.getenv('DATA_DIR', 'data')
        path = Path(data_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @staticmethod
    def get_logs_dir() -> Path:
        """Get logs directory path."""
        logs_dir = os.getenv('LOGS_DIR', 'logs')
        path = Path(logs_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @staticmethod
    def get_config_dir() -> Path:
        """Get configuration directory path."""
        config_dir = os.getenv('CONFIG_DIR', 'config')
        path = Path(config_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @staticmethod
    def get_discord_token() -> Optional[str]:
        """Get Discord bot token from environment."""
        return os.getenv('DISCORD_TOKEN')
    
    @staticmethod
    def get_database_url() -> str:
        """Get database URL from environment."""
        default_url = f"sqlite:///{Environment.get_data_dir()}/pokemon_bot.db"
        return os.getenv('DATABASE_URL', default_url)
    
    @staticmethod
    def get_log_level() -> str:
        """Get logging level from environment."""
        return os.getenv('LOG_LEVEL', 'INFO').upper()
    
    @staticmethod
    def get_monitoring_interval() -> int:
        """Get default monitoring interval from environment."""
        try:
            return int(os.getenv('MONITORING_INTERVAL', '60'))
        except ValueError:
            return 60
    
    @staticmethod
    def get_max_concurrent() -> int:
        """Get maximum concurrent monitoring tasks from environment."""
        try:
            return int(os.getenv('MAX_CONCURRENT', '10'))
        except ValueError:
            return 10
    
    @staticmethod
    def get_health_check_config() -> Dict[str, Any]:
        """Get health check configuration."""
        enabled = os.getenv('HEALTH_CHECK_ENABLED', 'true').lower() in ('true', '1', 'yes')
        
        try:
            port = int(os.getenv('HEALTH_CHECK_PORT', '8080'))
        except ValueError:
            port = 8080
            
        return {
            'enabled': enabled,
            'host': os.getenv('HEALTH_CHECK_HOST', '127.0.0.1'),
            'port': port
        }
    
    @staticmethod
    def get_performance_config() -> Dict[str, Any]:
        """Get performance configuration."""
        try:
            connection_pool_size = int(os.getenv('CONNECTION_POOL_SIZE', '10'))
        except ValueError:
            connection_pool_size = 10
            
        try:
            max_connections_per_host = int(os.getenv('MAX_CONNECTIONS_PER_HOST', '5'))
        except ValueError:
            max_connections_per_host = 5
            
        try:
            request_timeout = int(os.getenv('REQUEST_TIMEOUT', '30'))
        except ValueError:
            request_timeout = 30
            
        try:
            cache_ttl = int(os.getenv('CACHE_TTL', '300'))
        except ValueError:
            cache_ttl = 300
            
        return {
            'connection_pool_size': connection_pool_size,
            'max_connections_per_host': max_connections_per_host,
            'request_timeout': request_timeout,
            'cache_ttl': cache_ttl
        }
    
    @staticmethod
    def get_notification_config() -> Dict[str, Any]:
        """Get notification configuration."""
        try:
            embed_color = int(os.getenv('NOTIFICATION_EMBED_COLOR', '65280'), 0)  # Default: green (0x00ff00)
        except ValueError:
            embed_color = 65280
            
        try:
            max_queue_size = int(os.getenv('NOTIFICATION_MAX_QUEUE', '1000'))
        except ValueError:
            max_queue_size = 1000
            
        try:
            retry_delay = float(os.getenv('NOTIFICATION_RETRY_DELAY', '5.0'))
        except ValueError:
            retry_delay = 5.0
            
        return {
            'embed_color': embed_color,
            'max_queue_size': max_queue_size,
            'retry_delay': retry_delay,
            'batch_size': int(os.getenv('NOTIFICATION_BATCH_SIZE', '5')),
            'rate_limit_delay': float(os.getenv('NOTIFICATION_RATE_LIMIT_DELAY', '1.0'))
        }
    
    @staticmethod
    def get_anti_detection_config() -> Dict[str, Any]:
        """Get anti-detection configuration."""
        return {
            'min_delay': float(os.getenv('ANTI_DETECTION_MIN_DELAY', '1.0')),
            'max_delay': float(os.getenv('ANTI_DETECTION_MAX_DELAY', '5.0')),
            'rotate_user_agents': os.getenv('ANTI_DETECTION_ROTATE_UA', 'true').lower() in ('true', '1', 'yes'),
            'use_cache_busting': os.getenv('ANTI_DETECTION_CACHE_BUST', 'true').lower() in ('true', '1', 'yes')
        }
    
    @staticmethod
    def get_user_agents() -> List[str]:
        """Get list of user agents for rotation."""
        # Check if user agents are defined in environment
        user_agents_env = os.getenv('USER_AGENTS')
        if user_agents_env:
            try:
                # Try to parse as JSON array
                return json.loads(user_agents_env)
            except json.JSONDecodeError:
                # Fall back to comma-separated list
                return [ua.strip() for ua in user_agents_env.split(',')]
        
        # Default user agents
        return [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0"
        ]
    
    @staticmethod
    def load_env_file(env_file: str = '.env') -> None:
        """Load environment variables from .env file."""
        env_path = Path(env_file)
        if not env_path.exists():
            return
        
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and not os.getenv(key):
                            os.environ[key] = value
        except Exception as e:
            print(f"Warning: Failed to load .env file: {e}")
    
    @staticmethod
    def setup_basic_logging():
        """Set up basic logging before config is loaded."""
        log_level = Environment.get_log_level()
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, log_level),
            format=log_format,
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        
        # Get logger for this module
        logger = logging.getLogger(__name__)
        logger.info(f"Basic logging initialized at level {log_level}")


# Load .env file on import
Environment.load_env_file()

# Set up basic logging
Environment.setup_basic_logging()