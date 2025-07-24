#!/bin/bash
# Hetzner Cloud Setup Script for PokeAlert Discord Bot
# Run this on your fresh Ubuntu server

set -e

echo "🚀 Setting up PokeAlert Discord Bot on Hetzner Cloud..."

# Update system
echo "📦 Updating system packages..."
apt update && apt upgrade -y

# Install Docker
echo "🐳 Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
usermod -aG docker $USER

# Install Docker Compose
echo "🔧 Installing Docker Compose..."
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install Git
echo "📚 Installing Git..."
apt install -y git nano htop curl wget

# Create app directory
echo "📁 Creating application directory..."
mkdir -p /opt/pokealert
cd /opt/pokealert

# Clone repository
echo "📥 Cloning PokeAlert repository..."
git clone https://github.com/AbdullahP/PokeAlert-Discord-Bot.git .

# Create environment file
echo "⚙️ Creating environment configuration..."
cp .env.example .env

# Create directories
mkdir -p data logs backups

# Set permissions
chown -R $USER:$USER /opt/pokealert

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit /opt/pokealert/.env with your Discord token"
echo "2. Run: cd /opt/pokealert && docker-compose up -d"
echo "3. Check logs: docker-compose logs -f"
echo ""
echo "Your bot will be running at: http://$(curl -s ifconfig.me):8080/health"