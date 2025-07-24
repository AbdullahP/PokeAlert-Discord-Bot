#!/usr/bin/env python
"""
Data cleanup script for Pokemon Discord Bot.

This script removes old data from the database based on retention policies.
"""
import os
import sys
import logging
import argparse
import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.environment import Environment
from src.config.config_manager import ConfigManager
from src.database.connection import DatabaseConnection


def setup_logging(verbose=False):
    """Set up logging for the cleanup script."""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    return logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Data cleanup tool for Pokemon Discord Bot')
    
    parser.add_argument(
        '--env-file',
        help='Path to .env file',
        default='.env'
    )
    
    parser.add_argument(
        '--config-file',
        help='Path to config file',
        default=None
    )
    
    parser.add_argument(
        '--metrics-days',
        type=int,
        help='Days to keep metrics data (overrides config)',
        default=None
    )
    
    parser.add_argument(
        '--stock-changes-days',
        type=int,
        help='Days to keep stock change history (overrides config)',
        default=None
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    return parser.parse_args()


def cleanup_metrics(db, days, dry_run=False, logger=None):
    """Clean up old metrics data."""
    if logger is None:
        logger = logging.getLogger(__name__)
    
    cutoff_date = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()
    
    try:
        # Count records to be deleted
        cursor = db.execute(
            "SELECT COUNT(*) FROM monitoring_metrics WHERE timestamp < ?",
            (cutoff_date,)
        )
        count = cursor.fetchone()[0]
        
        if count == 0:
            logger.info(f"No metrics data older than {days} days to delete")
            return 0
        
        logger.info(f"Found {count} metrics records older than {days} days")
        
        if not dry_run:
            # Delete old records
            db.execute(
                "DELETE FROM monitoring_metrics WHERE timestamp < ?",
                (cutoff_date,)
            )
            db.commit()
            logger.info(f"Deleted {count} old metrics records")
        else:
            logger.info(f"Would delete {count} old metrics records (dry run)")
        
        return count
    except Exception as e:
        logger.error(f"Error cleaning up metrics data: {e}")
        db.rollback()
        return 0


def cleanup_stock_changes(db, days, dry_run=False, logger=None):
    """Clean up old stock change history."""
    if logger is None:
        logger = logging.getLogger(__name__)
    
    cutoff_date = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()
    
    try:
        # Count records to be deleted
        cursor = db.execute(
            "SELECT COUNT(*) FROM stock_changes WHERE timestamp < ?",
            (cutoff_date,)
        )
        count = cursor.fetchone()[0]
        
        if count == 0:
            logger.info(f"No stock change data older than {days} days to delete")
            return 0
        
        logger.info(f"Found {count} stock change records older than {days} days")
        
        if not dry_run:
            # Delete old records
            db.execute(
                "DELETE FROM stock_changes WHERE timestamp < ?",
                (cutoff_date,)
            )
            db.commit()
            logger.info(f"Deleted {count} old stock change records")
        else:
            logger.info(f"Would delete {count} old stock change records (dry run)")
        
        return count
    except Exception as e:
        logger.error(f"Error cleaning up stock change data: {e}")
        db.rollback()
        return 0


def main():
    """Run data cleanup."""
    # Parse command line arguments
    args = parse_args()
    
    # Set up logging
    logger = setup_logging(args.verbose)
    logger.info("Starting data cleanup")
    
    # Load environment variables
    Environment.load_env_file(args.env_file)
    
    # Load configuration
    config = ConfigManager()
    if args.config_file:
        config.load_config(args.config_file)
    else:
        config_dir = Environment.get_config_dir()
        default_config = config_dir / "config.yaml"
        if default_config.exists():
            config.load_config(str(default_config))
        
        env_config = config_dir / f"config.{Environment.get_env()}.yaml"
        if env_config.exists():
            config.load_config(str(env_config))
    
    # Get retention settings
    metrics_days = args.metrics_days or config.get('data_retention.metrics_days', 30)
    stock_changes_days = args.stock_changes_days or config.get('data_retention.stock_changes_days', 90)
    
    logger.info(f"Retention policy: metrics={metrics_days} days, stock changes={stock_changes_days} days")
    
    # Connect to database
    db = DatabaseConnection()
    
    try:
        # Clean up metrics data
        metrics_count = cleanup_metrics(db, metrics_days, args.dry_run, logger)
        
        # Clean up stock change history
        stock_changes_count = cleanup_stock_changes(db, stock_changes_days, args.dry_run, logger)
        
        # Log summary
        total_count = metrics_count + stock_changes_count
        if args.dry_run:
            logger.info(f"Dry run complete. Would delete {total_count} records in total.")
        else:
            logger.info(f"Cleanup complete. Deleted {total_count} records in total.")
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        if args.verbose:
            logger.exception("Detailed error information:")
        sys.exit(1)
    finally:
        # Close database connection
        db.close()


if __name__ == "__main__":
    main()