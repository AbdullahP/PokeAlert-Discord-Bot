#!/usr/bin/env python
"""
Database recovery script for Pokemon Discord Bot.

This script provides comprehensive database recovery capabilities:
- Automatic backup restoration
- Database integrity checks
- Data migration and repair
- Emergency recovery procedures
"""
import os
import sys
import logging
import argparse
import sqlite3
import shutil
import datetime
from pathlib import Path
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.environment import Environment


def setup_logging(verbose=False):
    """Set up logging for the recovery script."""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
    
    return logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Database recovery tool for Pokemon Discord Bot')
    
    parser.add_argument(
        '--database',
        help='Database file path to recover',
        required=True
    )
    
    parser.add_argument(
        '--backup-dir',
        help='Directory containing backup files',
        default='./backups'
    )
    
    parser.add_argument(
        '--check-integrity',
        action='store_true',
        help='Check database integrity'
    )
    
    parser.add_argument(
        '--repair',
        action='store_true',
        help='Attempt to repair corrupted database'
    )
    
    parser.add_argument(
        '--restore-latest',
        action='store_true',
        help='Restore from latest backup'
    )
    
    parser.add_argument(
        '--restore-from',
        help='Restore from specific backup file'
    )
    
    parser.add_argument(
        '--list-backups',
        action='store_true',
        help='List available backup files'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    return parser.parse_args()


def check_database_integrity(db_path: str, logger=None) -> bool:
    """Check database integrity using SQLite's built-in checks."""
    if logger is None:
        logger = logging.getLogger(__name__)
    
    db_file = Path(db_path)
    if not db_file.exists():
        logger.error(f"Database file not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Run integrity check
        logger.info("Running database integrity check...")
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        
        if result[0] == "ok":
            logger.info("Database integrity check passed")
            
            # Additional checks
            cursor.execute("PRAGMA foreign_key_check;")
            fk_errors = cursor.fetchall()
            
            if fk_errors:
                logger.warning(f"Found {len(fk_errors)} foreign key constraint violations")
                for error in fk_errors:
                    logger.warning(f"FK violation: {error}")
            else:
                logger.info("Foreign key constraints are valid")
            
            # Check table structure
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            logger.info(f"Database contains {len(tables)} tables: {[t[0] for t in tables]}")
            
            conn.close()
            return True
        else:
            logger.error(f"Database integrity check failed: {result[0]}")
            conn.close()
            return False
            
    except Exception as e:
        logger.error(f"Database integrity check failed: {e}")
        return False


def repair_database(db_path: str, logger=None) -> bool:
    """Attempt to repair a corrupted database."""
    if logger is None:
        logger = logging.getLogger(__name__)
    
    db_file = Path(db_path)
    if not db_file.exists():
        logger.error(f"Database file not found: {db_path}")
        return False
    
    # Create backup of corrupted database
    backup_path = db_file.with_suffix(f".corrupted_{int(datetime.datetime.now().timestamp())}")
    shutil.copy2(db_file, backup_path)
    logger.info(f"Corrupted database backed up to: {backup_path}")
    
    try:
        # Create new database and dump data
        temp_db = db_file.with_suffix(".temp")
        
        logger.info("Attempting to recover data from corrupted database...")
        
        # Connect to corrupted database
        old_conn = sqlite3.connect(db_path)
        old_cursor = old_conn.cursor()
        
        # Create new database
        new_conn = sqlite3.connect(temp_db)
        new_cursor = new_conn.cursor()
        
        # Get schema from corrupted database
        old_cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL;")
        schema_statements = old_cursor.fetchall()
        
        # Recreate tables in new database
        for statement in schema_statements:
            try:
                new_cursor.execute(statement[0])
                logger.debug(f"Created table: {statement[0][:50]}...")
            except Exception as e:
                logger.warning(f"Failed to create table: {e}")
        
        # Copy data table by table
        old_cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = old_cursor.fetchall()
        
        recovered_tables = 0
        for table in tables:
            table_name = table[0]
            try:
                # Get data from old table
                old_cursor.execute(f"SELECT * FROM {table_name};")
                rows = old_cursor.fetchall()
                
                if rows:
                    # Get column info
                    old_cursor.execute(f"PRAGMA table_info({table_name});")
                    columns = old_cursor.fetchall()
                    column_names = [col[1] for col in columns]
                    
                    # Insert data into new table
                    placeholders = ','.join(['?' for _ in column_names])
                    new_cursor.executemany(
                        f"INSERT INTO {table_name} VALUES ({placeholders})",
                        rows
                    )
                    
                    logger.info(f"Recovered {len(rows)} rows from table '{table_name}'")
                    recovered_tables += 1
                else:
                    logger.info(f"Table '{table_name}' is empty")
                    recovered_tables += 1
                    
            except Exception as e:
                logger.error(f"Failed to recover table '{table_name}': {e}")
        
        # Commit and close connections
        new_conn.commit()
        old_conn.close()
        new_conn.close()
        
        if recovered_tables > 0:
            # Replace corrupted database with repaired one
            shutil.move(temp_db, db_file)
            logger.info(f"Database repair completed. Recovered {recovered_tables} tables.")
            
            # Verify repaired database
            if check_database_integrity(db_path, logger):
                logger.info("Repaired database passed integrity check")
                return True
            else:
                logger.error("Repaired database failed integrity check")
                return False
        else:
            logger.error("No tables could be recovered")
            if temp_db.exists():
                temp_db.unlink()
            return False
            
    except Exception as e:
        logger.error(f"Database repair failed: {e}")
        return False


def list_available_backups(backup_dir: str, logger=None) -> List[Dict]:
    """List all available backup files with metadata."""
    if logger is None:
        logger = logging.getLogger(__name__)
    
    backup_path = Path(backup_dir)
    if not backup_path.exists():
        logger.warning(f"Backup directory does not exist: {backup_dir}")
        return []
    
    backups = []
    for backup_file in backup_path.glob("pokemon_bot_*.db*"):
        try:
            stat = backup_file.stat()
            backup_info = {
                'path': str(backup_file),
                'name': backup_file.name,
                'size': stat.st_size,
                'modified': datetime.datetime.fromtimestamp(stat.st_mtime),
                'compressed': backup_file.suffix == '.gz'
            }
            backups.append(backup_info)
        except Exception as e:
            logger.warning(f"Could not read backup file {backup_file}: {e}")
    
    # Sort by modification time (newest first)
    backups.sort(key=lambda x: x['modified'], reverse=True)
    
    return backups


def restore_from_backup(backup_path: str, target_path: str, logger=None) -> bool:
    """Restore database from backup file."""
    if logger is None:
        logger = logging.getLogger(__name__)
    
    # Import the restore function from backup script
    from scripts.db_backup import restore_database
    
    return restore_database(backup_path, target_path, logger)


def main():
    """Run database recovery operations."""
    args = parse_args()
    logger = setup_logging(args.verbose)
    
    # List available backups
    if args.list_backups:
        logger.info(f"Listing backups in: {args.backup_dir}")
        backups = list_available_backups(args.backup_dir, logger)
        
        if not backups:
            logger.info("No backup files found")
            return
        
        logger.info(f"Found {len(backups)} backup files:")
        for i, backup in enumerate(backups, 1):
            size_mb = backup['size'] / (1024 * 1024)
            compressed = " (compressed)" if backup['compressed'] else ""
            logger.info(f"{i:2d}. {backup['name']} - {size_mb:.1f}MB - {backup['modified']}{compressed}")
        return
    
    # Check database integrity
    if args.check_integrity:
        logger.info(f"Checking integrity of database: {args.database}")
        if check_database_integrity(args.database, logger):
            logger.info("Database integrity check completed successfully")
        else:
            logger.error("Database integrity check failed")
            sys.exit(1)
        return
    
    # Repair database
    if args.repair:
        logger.info(f"Attempting to repair database: {args.database}")
        if repair_database(args.database, logger):
            logger.info("Database repair completed successfully")
        else:
            logger.error("Database repair failed")
            sys.exit(1)
        return
    
    # Restore from latest backup
    if args.restore_latest:
        backups = list_available_backups(args.backup_dir, logger)
        if not backups:
            logger.error("No backup files found")
            sys.exit(1)
        
        latest_backup = backups[0]
        logger.info(f"Restoring from latest backup: {latest_backup['name']}")
        
        if restore_from_backup(latest_backup['path'], args.database, logger):
            logger.info("Database restoration completed successfully")
        else:
            logger.error("Database restoration failed")
            sys.exit(1)
        return
    
    # Restore from specific backup
    if args.restore_from:
        logger.info(f"Restoring from backup: {args.restore_from}")
        
        if restore_from_backup(args.restore_from, args.database, logger):
            logger.info("Database restoration completed successfully")
        else:
            logger.error("Database restoration failed")
            sys.exit(1)
        return
    
    # If no specific action is requested, run integrity check
    logger.info("No specific action requested. Running integrity check...")
    if check_database_integrity(args.database, logger):
        logger.info("Database is healthy")
    else:
        logger.error("Database has integrity issues. Consider running --repair or --restore-latest")
        sys.exit(1)


if __name__ == "__main__":
    main()