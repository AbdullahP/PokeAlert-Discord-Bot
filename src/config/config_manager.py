"""
Configuration management for the Pokemon Discord Bot.
"""
import os
import yaml
import json
from typing import Any, Dict, Optional
from pathlib import Path

from ..models.interfaces import IConfigManager


class ConfigManager(IConfigManager):
    """Configuration manager implementation."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration manager."""
        self._config: Dict[str, Any] = {}
        self._config_path = config_path
        self._load_default_config()
        self._load_environment_variables()
        
        if config_path:
            self.load_config(config_path)
    
    def _load_default_config(self) -> None:
        """Load default configuration values."""
        self._config = {
            # Discord settings
            'discord': {
                'token': '',
                'command_prefix': '!',
                'admin_roles': ['Admin', 'Moderator'],
                'max_retries': 3,
                'retry_delay': 1.0
            },
            
            # Monitoring settings
            'monitoring': {
                'default_interval': 5,   # Ultra-fast: 5 seconds
                'min_interval': 1,       # Minimum 1 second - fastest possible
                'max_concurrent': 10,
                'request_timeout': 30,
                'user_agents': [
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
                ],
                'anti_detection': {
                    'min_delay': 1.0,
                    'max_delay': 5.0,
                    'rotate_user_agents': True,
                    'use_cache_busting': True
                }
            },
            
            # Database settings
            'database': {
                'url': 'sqlite:///data/pokemon_bot.db',
                'pool_size': 5,
                'max_overflow': 10,
                'pool_timeout': 30,
                'pool_recycle': 3600
            },
            
            # Notification settings
            'notifications': {
                'embed_color': 0x00ff00,  # Green
                'max_queue_size': 1000,
                'retry_delay': 5.0,
                'batch_size': 5,
                'rate_limit_delay': 1.0
            },
            
            # Logging settings
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'file_path': 'logs/pokemon_bot.log',
                'max_file_size': 10485760,  # 10MB
                'backup_count': 5
            },
            
            # Performance settings
            'performance': {
                'connection_pool_size': 10,
                'max_connections_per_host': 5,
                'request_timeout': 30,
                'cache_ttl': 300  # 5 minutes
            }
        }
    
    def _load_environment_variables(self) -> None:
        """Load configuration from environment variables."""
        env_mappings = {
            'DISCORD_TOKEN': 'discord.token',
            'DATABASE_URL': 'database.url',
            'LOG_LEVEL': 'logging.level',
            'MONITORING_INTERVAL': 'monitoring.default_interval',
            'MAX_CONCURRENT': 'monitoring.max_concurrent'
        }
        
        for env_var, config_key in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                self._set_nested_value(config_key, value)
    
    def _set_nested_value(self, key: str, value: Any) -> None:
        """Set a nested configuration value using dot notation."""
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Convert string values to appropriate types
        if isinstance(value, str):
            if value.lower() in ('true', 'false'):
                value = value.lower() == 'true'
            elif value.isdigit():
                value = int(value)
            elif value.replace('.', '').isdigit() and value.count('.') == 1:
                # Only convert to float if it has exactly one decimal point
                # This prevents IP addresses from being converted to floats
                try:
                    value = float(value)
                except ValueError:
                    pass  # Keep as string if conversion fails
        
        config[keys[-1]] = value
    
    def _get_nested_value(self, key: str, default: Any = None) -> Any:
        """Get a nested configuration value using dot notation."""
        keys = key.split('.')
        config = self._config
        
        try:
            for k in keys:
                config = config[k]
            return config
        except (KeyError, TypeError):
            return default
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._get_nested_value(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        self._set_nested_value(key, value)
    
    def load_config(self, config_path: str) -> None:
        """Load configuration from file."""
        path = Path(config_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                if path.suffix.lower() in ('.yml', '.yaml'):
                    file_config = yaml.safe_load(f)
                elif path.suffix.lower() == '.json':
                    file_config = json.load(f)
                else:
                    raise ValueError(f"Unsupported configuration file format: {path.suffix}")
            
            # Merge file configuration with existing configuration
            self._merge_config(self._config, file_config)
            self._config_path = config_path
            
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration from {config_path}: {e}")
    
    def save_config(self, config_path: str) -> None:
        """Save configuration to file."""
        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                if path.suffix.lower() in ('.yml', '.yaml'):
                    yaml.dump(self._config, f, default_flow_style=False, indent=2)
                elif path.suffix.lower() == '.json':
                    json.dump(self._config, f, indent=2)
                else:
                    raise ValueError(f"Unsupported configuration file format: {path.suffix}")
                    
        except Exception as e:
            raise RuntimeError(f"Failed to save configuration to {config_path}: {e}")
    
    def _merge_config(self, base: dict, override: dict) -> None:
        """Recursively merge configuration dictionaries."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def get_discord_config(self) -> dict:
        """Get Discord-specific configuration."""
        return self.get('discord', {})
    
    def get_monitoring_config(self) -> dict:
        """Get monitoring-specific configuration."""
        return self.get('monitoring', {})
    
    def get_database_config(self) -> dict:
        """Get database-specific configuration."""
        return self.get('database', {})
    
    def get_notification_config(self) -> dict:
        """Get notification-specific configuration."""
        return self.get('notifications', {})
    
    def get_logging_config(self) -> dict:
        """Get logging-specific configuration."""
        return self.get('logging', {})
    
    def validate_config(self) -> bool:
        """Validate required configuration values."""
        required_keys = [
            'discord.token',
            'database.url'
        ]
        
        missing_keys = []
        for key in required_keys:
            if not self.get(key):
                missing_keys.append(key)
        
        if missing_keys:
            raise ValueError(f"Missing required configuration keys: {missing_keys}")
        
        return True


# Global configuration instance
config = ConfigManager()