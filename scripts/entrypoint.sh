#!/bin/bash
set -e

# Create necessary directories
mkdir -p /app/data
mkdir -p /app/logs
mkdir -p /app/config

# Set proper permissions
chmod -R 755 /app/data
chmod -R 755 /app/logs
chmod -R 755 /app/config

# Check if Discord token is set
if [ -z "$DISCORD_TOKEN" ]; then
    echo "ERROR: DISCORD_TOKEN environment variable is not set!"
    echo "Please set the DISCORD_TOKEN environment variable and restart the container."
    exit 1
fi

# Run database migrations
echo "Running database migrations..."
python -m scripts.db_migrate --create-tables

# Run health check to verify setup
echo "Running initial health check..."
python -m src.health_check --url http://localhost:8080 || true

# Log startup information
echo "Starting Pokemon Discord Bot in $ENVIRONMENT mode"
echo "Log level: $LOG_LEVEL"
echo "Monitoring interval: $MONITORING_INTERVAL seconds"

# Execute the command
exec "$@"