#!/usr/bin/env python
"""
Database backup script for Pokemon Discord Bot.

This script creates a backup of the SQLite database with production features:
- Automated scheduled backups
- Backup rotation and cleanup
- Compression support
- Recovery verification
- Health monitoring
"""
import os
import sys
import logging
import argparse
import shutil
import datetime
import gzip
import sqlite3
import time
import asyncio
from pathlib import Path
from typing import Optional, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.environment import Environment


def setup_logging(verbose=False):
    """Set up logging for the backup script."""
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
    parser = argparse.ArgumentParser(description='Database backup tool for Pokemon Discord Bot')
    
    parser.add_argument(
        '--env-file',
        help='Path to .env file',
        default='.env'
    )
    
    parser.add_argument(
        '--database',
        help='Database file path (overrides environment variable)',
    )
    
    parser.add_argument(
        '--output-dir',
        help='Output directory for backup file (default: data/backups)',
        default=None
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--daemon',
        action='store_true',
        help='Run as daemon with scheduled backups'
    )
    
    parser.add_argument(
        '--compress',
        action='store_true',
        help='Compress backup files with gzip'
    )
    
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify backup integrity after creation'
    )
    
    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Clean up old backup files'
    )
    
    parser.add_argument(
        '--restore',
        help='Restore database from backup file'
    )
    
    return parser.parse_args()


def get_database_path():
    """Get the database file path from environment."""
    db_url = Environment.get_database_url()
    
    # Extract file path from SQLite URL
    if db_url.startswith('sqlite:///'):
        return db_url[10:]
    
    return None


def create_backup(db_path, output_dir=None, compress=False, verify=False, logger=None):
    """Create a backup of the database with optional compression and verification."""
    if logger is None:
        logger = logging.getLogger(__name__)
    
    # Check if database file exists
    db_file = Path(db_path)
    if not db_file.exists():
        logger.error(f"Database file not found: {db_path}")
        return None
    
    # Create backup directory if it doesn't exist
    if output_dir is None:
        output_dir = Path(os.environ.get('BACKUP_DIR', './backups'))
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate backup filename with timestamp
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"pokemon_bot_{timestamp}.db"
    if compress:
        backup_filename += ".gz"
    backup_path = output_dir / backup_filename
    
    # Create backup
    try:
        if compress:
            # Create compressed backup
            with open(db_file, 'rb') as f_in:
                with gzip.open(backup_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            # Create regular backup
            shutil.copy2(db_file, backup_path)
        
        logger.info(f"Database backup created: {backup_path}")
        
        # Verify backup if requested
        if verify:
            if verify_backup(backup_path, compress, logger):
                logger.info("Backup verification successful")
            else:
                logger.error("Backup verification failed")
                return None
        
        return backup_path
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return None


def verify_backup(backup_path, compressed=False, logger=None):
    """Verify backup integrity by attempting to open the database."""
    if logger is None:
        logger = logging.getLogger(__name__)
    
    try:
        if compressed:
            # Extract and verify compressed backup
            with gzip.open(backup_path, 'rb') as f:
                # Try to read the SQLite header
                header = f.read(16)
                if not header.startswith(b'SQLite format 3'):
                    logger.error("Invalid SQLite header in compressed backup")
                    return False
        else:
            # Verify uncompressed backup
            conn = sqlite3.connect(backup_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()
            
            if not tables:
                logger.warning("Backup appears to be empty (no tables found)")
            else:
                logger.debug(f"Backup contains {len(tables)} tables")
        
        return True
    except Exception as e:
        logger.error(f"Backup verification failed: {e}")
        return False


def cleanup_old_backups(backup_dir, retention_days=7, logger=None):
    """Clean up old backup files based on retention policy."""
    if logger is None:
        logger = logging.getLogger(__name__)
    
    backup_path = Path(backup_dir)
    if not backup_path.exists():
        logger.warning(f"Backup directory does not exist: {backup_dir}")
        return
    
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
    deleted_count = 0
    
    try:
        for backup_file in backup_path.glob("pokemon_bot_*.db*"):
            if backup_file.stat().st_mtime < cutoff_date.timestamp():
                backup_file.unlink()
                deleted_count += 1
                logger.debug(f"Deleted old backup: {backup_file}")
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old backup files")
        else:
            logger.debug("No old backup files to clean up")
            
    except Exception as e:
        logger.error(f"Backup cleanup failed: {e}")


def restore_database(backup_path, target_path, logger=None):
    """Restore database from backup file."""
    if logger is None:
        logger = logging.getLogger(__name__)
    
    backup_file = Path(backup_path)
    target_file = Path(target_path)
    
    if not backup_file.exists():
        logger.error(f"Backup file not found: {backup_path}")
        return False
    
    try:
        # Create backup of current database if it exists
        if target_file.exists():
            backup_current = target_file.with_suffix(f".backup_{int(time.time())}")
            shutil.copy2(target_file, backup_current)
            logger.info(f"Current database backed up to: {backup_current}")
        
        # Restore from backup
        if backup_path.endswith('.gz'):
            # Decompress and restore
            with gzip.open(backup_file, 'rb') as f_in:
                with open(target_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            # Direct copy
            shutil.copy2(backup_file, target_file)
        
        # Verify restored database
        if verify_backup(target_file, False, logger):
            logger.info(f"Database successfully restored from: {backup_path}")
            return True
        else:
            logger.error("Restored database failed verification")
            return False
            
    except Exception as e:
        logger.error(f"Database restore failed: {e}")
        return False


async def backup_daemon(db_path, backup_dir, interval_seconds=3600, retention_days=7, logger=None):
    """Run backup daemon with scheduled backups."""
    if logger is None:
        logger = logging.getLogger(__name__)
    
    logger.info(f"Starting backup daemon (interval: {interval_seconds}s, retention: {retention_days} days)")
    
    while True:
        try:
            # Create backup
            backup_path = create_backup(
                db_path, 
                backup_dir, 
                compress=True, 
                verify=True, 
                logger=logger
            )
            
            if backup_path:
                # Clean up old backups
                cleanup_old_backups(backup_dir, retention_days, logger)
            
            # Wait for next backup
            await asyncio.sleep(interval_seconds)
            
        except KeyboardInterrupt:
            logger.info("Backup daemon stopped by user")
            break
        except Exception as e:
            logger.error(f"Backup daemon error: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retrying


def main():
    """Run database backup with various modes."""
    # Parse command line arguments
    args = parse_args()
    
    # Set up logging
    logger = setup_logging(args.verbose)
    
    # Load environment variables
    Environment.load_env_file(args.env_file)
    
    # Get database path
    db_path = args.database or get_database_path()
    if not db_path and not args.cleanup:
        logger.error("Database path not found. Please specify with --database or set DATABASE_URL environment variable.")
        sys.exit(1)
    
    # Handle restore operation
    if args.restore:
        logger.info(f"Restoring database from backup: {args.restore}")
        if restore_database(args.restore, db_path, logger):
            logger.info("Database restore completed successfully")
        else:
            logger.error("Database restore failed")
            sys.exit(1)
        return
    
    # Handle cleanup operation
    if args.cleanup:
        backup_dir = args.output_dir or os.environ.get('BACKUP_DIR', './backups')
        retention_days = int(os.environ.get('BACKUP_RETENTION_DAYS', '7'))
        logger.info(f"Cleaning up old backups in: {backup_dir}")
        cleanup_old_backups(backup_dir, retention_days, logger)
        return
    
    # Handle daemon mode
    if args.daemon:
        backup_dir = args.output_dir or os.environ.get('BACKUP_DIR', './backups')
        interval = int(os.environ.get('BACKUP_INTERVAL', '3600'))
        retention_days = int(os.environ.get('BACKUP_RETENTION_DAYS', '7'))
        
        logger.info(f"Starting backup daemon for database: {db_path}")
        try:
            asyncio.run(backup_daemon(db_path, backup_dir, interval, retention_days, logger))
        except KeyboardInterrupt:
            logger.info("Backup daemon stopped")
        return
    
    # Handle single backup operation
    logger.info(f"Creating backup for database: {db_path}")
    backup_path = create_backup(
        db_path, 
        args.output_dir, 
        compress=args.compress, 
        verify=args.verify, 
        logger=logger
    )
    
    if backup_path:
        logger.info("Backup completed successfully")
        
        # Clean up old backups if requested
        if args.cleanup:
            backup_dir = args.output_dir or os.path.dirname(backup_path)
            retention_days = int(os.environ.get('BACKUP_RETENTION_DAYS', '7'))
            cleanup_old_backups(backup_dir, retention_days, logger)
    else:
        logger.error("Backup failed")
        sys.exit(1)


if __name__ == "__main__":
    main()