#!/usr/bin/env python3
'''
ULTIMATE MONITORING SYSTEM - START SCRIPT
Production-ready startup with all optimizations.
'''
import os
import sys
import asyncio
import logging
from pathlib import Path

# Load environment variables from .env file
def load_env_file():
    """Load environment variables from .env file."""
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# Load .env file
load_env_file()

# Ensure we're in the right directory
os.chdir(Path(__file__).parent)

# Add src to path
sys.path.insert(0, 'src')

# Configure production logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/production.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def check_environment():
    '''Check if environment is properly configured.'''
    logger.info("Checking environment configuration...")
    
    # Check Discord token
    if not os.getenv('DISCORD_TOKEN'):
        logger.error("DISCORD_TOKEN not set! Please configure your environment.")
        logger.error("Set it in .env file or as environment variable.")
        return False
    
    # Check required directories
    required_dirs = ['data', 'logs', 'config']
    for directory in required_dirs:
        if not os.path.exists(directory):
            logger.error(f"Required directory missing: {directory}")
            return False
    
    logger.info("✅ Environment check passed")
    return True

async def main():
    '''Start the ultimate monitoring system.'''
    logger.info("=" * 60)
    logger.info("🚀 ULTIMATE MONITORING SYSTEM - STARTING")
    logger.info("=" * 60)
    
    # Environment check
    if not check_environment():
        logger.error("❌ Environment check failed. Please fix issues and try again.")
        return
    
    # Import and start
    try:
        logger.info("Loading monitoring system...")
        from main import main as app_main
        await app_main()
    except ImportError:
        logger.info("Loading from src.main...")
        from src.main import main as app_main
        await app_main()
    except Exception as e:
        logger.error(f"❌ Failed to start: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Shutdown requested by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)
