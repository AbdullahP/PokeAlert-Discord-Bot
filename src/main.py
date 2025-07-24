"""
Main application entry point for the Pokemon Discord Bot.
"""
import asyncio
import logging
import logging.handlers
import sys
import signal
import time
import os
from pathlib import Path

from .config.environment import Environment
from .config.config_manager import config, ConfigManager
from .database.connection import db
from .discord_bot.client import DiscordBotClient
from .services.notification_service import NotificationService
from .services.monitoring_engine import MonitoringEngine
from .services.product_manager import ProductManager
from .services.admin_manager import AdminManager
from .services.error_handler import error_handler
from .services.health_check import health_server
from .services.performance_monitor import PerformanceMonitor
from .database.metrics_decorator import set_performance_monitor as set_db_performance_monitor
from .discord_bot.metrics_decorator import set_performance_monitor as set_discord_performance_monitor

# Import and apply optimizations
import sys
import os
# Add the parent directory to the path to import optimizations
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

try:
    from fix_price_extraction import apply_patch as apply_price_extraction_patch
    from apply_intelligent_monitoring_v2 import patch_monitoring_engine
except ImportError as e:
    # Fallback if the import fails
    def apply_price_extraction_patch():
        pass
    def patch_monitoring_engine():
        pass


def setup_logging():
    """Set up logging configuration."""
    from .config.logging_config import configure_logging
    return configure_logging()


def setup_signal_handlers(loop):
    """Set up signal handlers for graceful shutdown."""
    def signal_handler():
        logger = logging.getLogger(__name__)
        logger.info("Shutdown signal received, closing application...")
        
        # Stop the event loop
        if loop.is_running():
            loop.stop()
    
    # Register signal handlers (skip on Windows as it's not supported)
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)
    else:
        # On Windows, we'll handle Ctrl+C differently
        def windows_signal_handler(signum, frame):
            logger = logging.getLogger(__name__)
            logger.info("Shutdown signal received, closing application...")
            if loop.is_running():
                loop.call_soon_threadsafe(loop.stop)
        
        signal.signal(signal.SIGINT, windows_signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, windows_signal_handler)


async def shutdown_services():
    """Gracefully shut down all services."""
    logger = logging.getLogger(__name__)
    logger.info("Shutting down services...")
    
    # Stop performance monitor if it exists
    try:
        if 'performance_monitor' in globals():
            logger.info("Stopping performance monitor...")
            await globals()['performance_monitor'].stop()
    except Exception as e:
        logger.error(f"Error stopping performance monitor: {e}")
    
    # Stop health check server
    try:
        logger.info("Stopping health check server...")
        await health_server.stop()
    except Exception as e:
        logger.error(f"Error stopping health check server: {e}")
    
    # Close database connection
    try:
        logger.info("Closing database connection...")
        db.close()
    except Exception as e:
        logger.error(f"Error closing database connection: {e}")
    
    logger.info("All services shut down")


def load_configuration():
    """Load configuration from files and environment variables."""
    logger = logging.getLogger(__name__)
    
    # Get configuration directory
    config_dir = Environment.get_config_dir()
    
    # Default config file path
    default_config_path = config_dir / "config.yaml"
    
    # Check for environment-specific config
    env = Environment.get_env()
    env_config_path = config_dir / f"config.{env}.yaml"
    
    # Load default config if it exists
    if default_config_path.exists():
        try:
            logger.info(f"Loading default configuration from {default_config_path}")
            config.load_config(str(default_config_path))
        except Exception as e:
            logger.error(f"Error loading default configuration: {e}")
    
    # Load environment-specific config if it exists
    if env_config_path.exists():
        try:
            logger.info(f"Loading {env} configuration from {env_config_path}")
            config.load_config(str(env_config_path))
        except Exception as e:
            logger.error(f"Error loading {env} configuration: {e}")
    
    # Check for custom config path from environment
    custom_config_path = os.getenv('CONFIG_FILE')
    if custom_config_path and Path(custom_config_path).exists():
        try:
            logger.info(f"Loading custom configuration from {custom_config_path}")
            config.load_config(custom_config_path)
        except Exception as e:
            logger.error(f"Error loading custom configuration: {e}")
    
    # Update health check configuration from environment
    health_check_config = Environment.get_health_check_config()
    config.set('health_check.enabled', health_check_config['enabled'])
    config.set('health_check.host', health_check_config['host'])
    config.set('health_check.port', health_check_config['port'])
    
    # Update performance configuration from environment
    performance_config = Environment.get_performance_config()
    for key, value in performance_config.items():
        config.set(f'performance.{key}', value)
    
    # Update notification configuration from environment
    notification_config = Environment.get_notification_config()
    for key, value in notification_config.items():
        config.set(f'notifications.{key}', value)
    
    # Update anti-detection configuration from environment
    anti_detection_config = Environment.get_anti_detection_config()
    for key, value in anti_detection_config.items():
        config.set(f'monitoring.anti_detection.{key}', value)
    
    # Update user agents from environment
    user_agents = Environment.get_user_agents()
    if user_agents:
        config.set('monitoring.user_agents', user_agents)
    
    # Set Discord token from environment if not already set
    discord_token = config.get('discord.token') or Environment.get_discord_token()
    if discord_token:
        config.set('discord.token', discord_token)
    
    # Validate required configuration
    try:
        config.validate_config()
        logger.info("Configuration validated successfully")
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        return False
    
    return True


async def main():
    """Main application entry point."""
    # Set up basic logging (will be enhanced after config is loaded)
    logger = logging.getLogger(__name__)
    logger.info(f"Starting Pokemon Discord Bot in {Environment.get_env()} mode")
    
    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    setup_signal_handlers(loop)
    
    try:
        # Load configuration
        logger.info("Loading configuration")
        if not load_configuration():
            logger.error("Failed to load valid configuration. Exiting.")
            return
        
        # Set up enhanced logging with loaded configuration
        logger = setup_logging()
        
        # Apply price extraction patch for accurate price detection
        logger.info("Applying price extraction improvements...")
        try:
            apply_price_extraction_patch()
            logger.info("Price extraction patch applied successfully")
        except Exception as e:
            logger.error(f"Failed to apply price extraction patch: {e}")
        
        # Apply intelligent monitoring optimizations
        # Intelligent monitoring v2 disabled due to recursion errors
        logger.info("Intelligent monitoring optimizations v2 disabled for stability")
        
        # Initialize database
        logger.info("Initializing database")
        db.create_tables()
        migration_version = db.run_migrations()
        logger.info(f"Database migrated to version {migration_version}")
        
        # Start health check server if enabled
        health_check_enabled = config.get('health_check.enabled', True)
        if health_check_enabled:
            health_host = config.get('health_check.host', '127.0.0.1')
            health_port = config.get('health_check.port', 8080)
            logger.info(f"Starting health check server on {health_host}:{health_port}")
            
            # Update health server configuration
            health_server.host = health_host
            health_server.port = health_port
            health_server.start_in_thread()
        else:
            logger.info("Health check server disabled by configuration")
        
        # Initialize services
        logger.info("Initializing services")
        
        # Initialize performance monitor
        logger.info("Initializing performance monitor")
        performance_monitor = PerformanceMonitor(config)
        
        # Set performance monitor for database and Discord metrics
        set_db_performance_monitor(performance_monitor)
        set_discord_performance_monitor(performance_monitor)
        
        # Start performance monitoring
        await performance_monitor.start()
        
        monitoring_engine = MonitoringEngine(config)
        
        # Apply price extraction
        
        # Initialize Discord client
        logger.info("Initializing Discord client")
        discord_token = config.get('discord.token') or Environment.get_discord_token()
        if not discord_token:
            logger.error("Discord token not found. Please set DISCORD_TOKEN environment variable.")
            return
        
        discord_client = DiscordBotClient(config)
        
        # Initialize notification service after Discord client
        notification_service = NotificationService(config, discord_client)
        
        # Initialize product manager with monitoring engine and notification service
        product_manager = ProductManager(monitoring_engine, notification_service)
        discord_client.set_product_manager(product_manager)
        
        # Initialize admin manager
        logger.info("Initializing admin manager")
        admin_manager = AdminManager(config, discord_client, product_manager, performance_monitor)
        
        # Set admin manager in Discord client
        discord_client.set_admin_manager(admin_manager)
        
        # Error handler is already initialized and available globally
        
        # Initialize monitoring-notification integration
        from .services.monitoring_notification_integration import MonitoringNotificationIntegration
        logger.info("Initializing monitoring-notification integration")
        monitoring_notification_integration = MonitoringNotificationIntegration(notification_service)
        await monitoring_notification_integration.register_with_monitoring_engine(monitoring_engine)
        
        # Process any pending notifications from previous runs
        logger.info("Processing pending notifications")
        asyncio.create_task(monitoring_notification_integration.process_pending_notifications())
        
        # Initialize and send initial status notifications
        from .services.initial_status_notifier import InitialStatusNotifier
        logger.info("Initializing initial status notifier")
        initial_status_notifier = InitialStatusNotifier(notification_service, product_manager, monitoring_engine)
        
        # Send initial status notifications after Discord client is ready
        # DISABLED: No initial embeds on startup
        # async def send_initial_notifications():
        #     # Wait a bit for Discord client to be fully ready
        #     await asyncio.sleep(10)
        #     await initial_status_notifier.send_initial_status_notifications()
        # 
        # asyncio.create_task(send_initial_notifications())
        
        # Start continuous monitoring for all products
        async def start_monitoring():
            # Wait for Discord client to be ready and initial notifications to complete
            await asyncio.sleep(15)
            logger.info("Starting continuous product monitoring...")
            
            # Get all active products from the database
            try:
                active_products = await product_manager.get_all_active_products()
                
                if active_products:
                    logger.info(f"Starting monitoring for {len(active_products)} active products")
                    await monitoring_engine.start_monitoring(active_products)
                    logger.info("✅ Continuous monitoring started with website-based intervals")
                else:
                    logger.info("No active products found to monitor")
            except Exception as e:
                logger.error(f"Error starting continuous monitoring: {e}")
        
        asyncio.create_task(start_monitoring())
        
        # Run initial health check
        logger.info("Running initial health check")
        health_status = await error_handler.run_health_check()
        if health_status["status"] != "healthy":
            logger.warning(f"System health check returned status: {health_status['status']}")
            for component, status in health_status["components"].items():
                if status.get("status") != "healthy":
                    logger.warning(f"Component {component} status: {status.get('status')}")
        
        # Log startup complete
        logger.info(f"Pokemon Discord Bot startup complete in {Environment.get_env()} mode")
        
        # Start Discord client
        logger.info("Starting Discord client")
        await discord_client.start(discord_token)
        
    except Exception as e:
        # Log the error through our error handler
        await error_handler.handle_error(e, {"context": "application_startup"})
        logger.exception(f"Error starting application: {e}")
        await shutdown_services()
        sys.exit(1)


if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())