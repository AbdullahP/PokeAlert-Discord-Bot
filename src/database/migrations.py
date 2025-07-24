"""
Database migration utilities for the Pokemon Discord Bot.
"""
import logging
import argparse
from pathlib import Path

from .connection import db
from ..config.environment import Environment


def run_migrations():
    """Run database migrations."""
    logger = logging.getLogger(__name__)
    logger.info("Running database migrations")
    
    try:
        # Create tables if they don't exist
        db.create_tables()
        
        # Run migrations
        current_version = db.run_migrations()
        logger.info(f"Database migrated to version {current_version}")
        
        return True
    except Exception as e:
        logger.error(f"Error running migrations: {e}")
        return False


def init_database():
    """Initialize database with tables and indexes."""
    logger = logging.getLogger(__name__)
    logger.info("Initializing database")
    
    try:
        # Create tables
        db.create_tables()
        logger.info("Database tables created successfully")
        
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Database migration utility")
    parser.add_argument(
        "--init", action="store_true", help="Initialize database with tables"
    )
    parser.add_argument(
        "--migrate", action="store_true", help="Run database migrations"
    )
    parser.add_argument(
        "--db-path", type=str, help="Custom database path"
    )
    
    args = parser.parse_args()
    
    # Set custom database path if provided
    if args.db_path:
        db.database_path = args.db_path
    
    # Run requested operations
    if args.init:
        success = init_database()
        if success:
            print("Database initialized successfully")
        else:
            print("Database initialization failed")
            exit(1)
    
    if args.migrate:
        success = run_migrations()
        if success:
            print("Database migrations completed successfully")
        else:
            print("Database migrations failed")
            exit(1)
    
    # If no operation specified, show help
    if not (args.init or args.migrate):
        parser.print_help()