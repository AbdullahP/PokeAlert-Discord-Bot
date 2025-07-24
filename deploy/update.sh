#!/bin/bash
# Easy Update Script for PokeAlert Discord Bot
# Run this to update your bot with latest changes

set -e

echo "🔄 Updating PokeAlert Discord Bot..."

# Navigate to app directory
cd /opt/pokealert

# Stop the bot
echo "⏹️ Stopping current bot..."
docker-compose down

# Backup current version
echo "💾 Creating backup..."
cp -r . ../pokealert-backup-$(date +%Y%m%d-%H%M%S) || true

# Pull latest changes
echo "📥 Pulling latest changes from GitHub..."
git pull origin main

# Rebuild and restart
echo "🔨 Rebuilding and starting bot..."
docker-compose build --no-cache
docker-compose up -d

# Show status
echo "📊 Checking bot status..."
sleep 5
docker-compose ps
docker-compose logs --tail=20

echo "✅ Update complete!"
echo "🌐 Health check: http://$(curl -s ifconfig.me):8080/health"
echo "📋 View logs: docker-compose logs -f"