#!/usr/bin/env python
"""
Database migration script for Pokemon Discord Bot.

This script runs database migrations to update the schema to the latest version.
It can be run independently of the main application.
"""
import os
import sys
import logging
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import db
from src.config.environment import Environment


def setup_logging(verbose=False):
    """Set up logging for the migration script."""
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
    parser = argparse.ArgumentParser(description='Database migration tool for Pokemon Discord Bot')
    
    parser.add_argument(
        '--env-file',
        help='Path to .env file',
        default='.env'
    )
    
    parser.add_argument(
        '--database',
        help='Database URL (overrides environment variable)',
    )
    
    parser.add_argument(
        '--version',
        type=int,
        help='Target migration version (default: latest)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--create-tables',
        action='store_true',
        help='Create tables if they don\'t exist'
    )
    
    return parser.parse_args()


def main():
    """Run database migrations."""
    # Parse command line arguments
    args = parse_args()
    
    # Set up logging
    logger = setup_logging(args.verbose)
    logger.info("Starting database migration")
    
    # Load environment variables
    Environment.load_env_file(args.env_file)
    
    # Override database URL if provided
    if args.database:
        os.environ['DATABASE_URL'] = args.database
        logger.info(f"Using database URL from command line: {args.database}")
    
    try:
        # Create tables if requested or if running migrations
        if args.create_tables:
            logger.info("Creating database tables")
            db.create_tables()
            logger.info("Database tables created or verified")
        
        # Run migrations
        logger.info("Running database migrations")
        version = db.run_migrations(args.version)
        logger.info(f"Database migrated to version {version}")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        if args.verbose:
            logger.exception("Detailed error information:")
        sys.exit(1)
    
    logger.info("Migration completed successfully")


if __name__ == "__main__":
    main()