# Pokemon Discord Bot - Complete Setup Guide

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Production Deployment](#production-deployment)
4. [Configuration](#configuration)
5. [Discord Bot Setup](#discord-bot-setup)
6. [Database Setup](#database-setup)
7. [Monitoring Setup](#monitoring-setup)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

**Minimum Requirements:**
- CPU: 1 vCPU
- RAM: 512MB
- Storage: 2GB
- Network: Stable internet connection

**Recommended for Production:**
- CPU: 2 vCPU
- RAM: 1GB
- Storage: 10GB SSD
- Network: Low latency connection

### Software Requirements

- **Docker** 20.10+ and **Docker Compose** 2.0+
- **Python** 3.10+ (if running without Docker)
- **Git** for cloning the repository

### Discord Requirements

- Discord account with server admin permissions
- Ability to create Discord applications/bots

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/pokemon-discord-bot.git
cd pokemon-discord-bot
```

### 2. Create Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to "Bot" section and click "Add Bot"
4. Copy the bot token (keep it secure!)
5. Enable "Message Content Intent" under "Privileged Gateway Intents"

### 3. Invite Bot to Server

1. Go to "OAuth2" > "URL Generator"
2. Select scopes: `bot` and `applications.commands`
3. Select bot permissions:
   - Send Messages
   - Use Slash Commands
   - Embed Links
   - Attach Files
   - Read Message History
   - Mention Everyone
4. Copy the generated URL and open it to invite the bot

### 4. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit the configuration
nano .env
```

**Required settings in `.env`:**
```env
DISCORD_TOKEN=your_bot_token_here
DISCORD_GUILD_ID=your_server_id_here
```

### 5. Start the Bot

```bash
# Using Docker (recommended)
docker-compose up -d

# Or using Python directly
pip install -r requirements.txt
python -m src.main
```

### 6. Test the Bot

In your Discord server, try:
```
/help
/status
```

## Production Deployment

### Docker Deployment (Recommended)

#### 1. Prepare Production Environment

```bash
# Create production directories
mkdir -p /opt/pokemon-bot/{data,logs,backups,config}
cd /opt/pokemon-bot

# Clone repository
git clone https://github.com/your-username/pokemon-discord-bot.git .

# Set up environment
cp .env.production .env
```

#### 2. Configure Production Settings

Edit `.env` file:
```env
# Discord Configuration
DISCORD_TOKEN=your_production_bot_token
DISCORD_GUILD_ID=your_server_id

# Application Settings
ENVIRONMENT=production
LOG_LEVEL=INFO
MONITORING_INTERVAL=60
MAX_CONCURRENT=20

# Paths (adjust for your setup)
DATA_PATH=/opt/pokemon-bot/data
LOGS_PATH=/opt/pokemon-bot/logs
BACKUP_PATH=/opt/pokemon-bot/backups

# Backup Configuration
BACKUP_ENABLED=true
BACKUP_INTERVAL=3600
BACKUP_RETENTION_DAYS=7

# Security
HEALTH_CHECK_PORT=8080
```

#### 3. Deploy with Docker Compose

```bash
# Build and start services
docker-compose -f docker-compose.yml up -d

# Check status
docker-compose ps
docker-compose logs -f pokemon-bot
```

#### 4. Set Up Systemd Service (Optional)

Create `/etc/systemd/system/pokemon-bot.service`:
```ini
[Unit]
Description=Pokemon Discord Bot
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/pokemon-bot
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable pokemon-bot
sudo systemctl start pokemon-bot
```

### Cloud Deployment

#### AWS EC2 Deployment

1. **Launch EC2 Instance**
   - Instance type: t3.small or larger
   - OS: Ubuntu 22.04 LTS
   - Security group: Allow port 8080 for health checks

2. **Install Dependencies**
   ```bash
   sudo apt update
   sudo apt install -y docker.io docker-compose git
   sudo usermod -aG docker ubuntu
   ```

3. **Deploy Application**
   ```bash
   git clone https://github.com/your-username/pokemon-discord-bot.git
   cd pokemon-discord-bot
   cp .env.production .env
   # Edit .env with your settings
   docker-compose up -d
   ```

4. **Set Up CloudWatch Monitoring** (Optional)
   ```bash
   # Install CloudWatch agent
   wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
   sudo dpkg -i amazon-cloudwatch-agent.deb
   ```

#### DigitalOcean Droplet Deployment

1. **Create Droplet**
   - Size: Basic $12/month (2GB RAM)
   - OS: Ubuntu 22.04
   - Add your SSH key

2. **Initial Setup**
   ```bash
   # Connect to droplet
   ssh root@your-droplet-ip
   
   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   
   # Install Docker Compose
   curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   chmod +x /usr/local/bin/docker-compose
   ```

3. **Deploy Bot**
   ```bash
   git clone https://github.com/your-username/pokemon-discord-bot.git
   cd pokemon-discord-bot
   cp .env.production .env
   # Configure .env
   docker-compose up -d
   ```

## Configuration

### Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `DISCORD_TOKEN` | Discord bot token | - | `your_discord_bot_token_here` |
| `DISCORD_GUILD_ID` | Discord server ID | - | `123456789012345678` |
| `LOG_LEVEL` | Logging verbosity | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `MONITORING_INTERVAL` | Default check interval (seconds) | `60` | `30`, `60`, `120` |
| `MAX_CONCURRENT` | Max simultaneous monitors | `10` | `5`, `10`, `20` |
| `DATABASE_URL` | Database file path | `/app/data/pokemon_bot.db` | `/path/to/database.db` |
| `BACKUP_ENABLED` | Enable automatic backups | `true` | `true`, `false` |
| `BACKUP_INTERVAL` | Backup frequency (seconds) | `3600` | `1800`, `3600`, `7200` |
| `BACKUP_RETENTION_DAYS` | Keep backups for N days | `7` | `3`, `7`, `14`, `30` |
| `HEALTH_CHECK_PORT` | HTTP health check port | `8080` | `8080`, `9090` |
| `ADMIN_ROLE_NAMES` | Admin role names (comma-separated) | `Admin,Moderator,Bot Admin` | `Admin,Staff` |

### Configuration Files

#### Main Configuration (`config/config.yaml`)

```yaml
# Discord settings
discord:
  command_prefix: "/"
  max_message_length: 2000
  embed_color: 0x3498db
  timeout: 30

# Monitoring settings
monitoring:
  default_interval: 60
  min_interval: 30
  max_concurrent: 10
  timeout: 30
  retry_attempts: 3
  retry_delay: 5
  user_agents:
    - "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    - "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Notification settings
notifications:
  max_per_minute: 30
  queue_size: 1000
  retry_attempts: 3
  embed_thumbnail: true
  mention_roles: true

# Database settings
database:
  connection_timeout: 30
  max_connections: 10
  backup_on_startup: true
  vacuum_interval: 86400  # 24 hours

# Logging settings
logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  max_file_size: "10MB"
  backup_count: 5
  log_to_file: true
```

#### Production Overrides (`config/config.production.yaml`)

```yaml
# Production-specific settings
logging:
  level: WARNING
  
monitoring:
  max_concurrent: 20
  retry_attempts: 5
  
notifications:
  max_per_minute: 60
  
database:
  max_connections: 20
```

## Discord Bot Setup

### 1. Create Discord Application

1. Visit [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Enter application name: "Pokemon Stock Monitor"
4. Save the application

### 2. Configure Bot Settings

1. Go to "Bot" section
2. Click "Add Bot"
3. Configure bot settings:
   - **Username**: PokemonStockBot
   - **Public Bot**: Disabled (recommended)
   - **Requires OAuth2 Code Grant**: Disabled
   - **Bot Permissions**: See permissions below

### 3. Required Bot Permissions

**Text Permissions:**
- Send Messages
- Send Messages in Threads
- Embed Links
- Attach Files
- Read Message History
- Mention Everyone
- Use External Emojis
- Add Reactions

**General Permissions:**
- Use Slash Commands

### 4. Privileged Gateway Intents

Enable these intents in the Bot section:
- **Message Content Intent**: Required for command processing

### 5. Generate Invite Link

1. Go to "OAuth2" > "URL Generator"
2. Select scopes:
   - `bot`
   - `applications.commands`
3. Select permissions (use the list above)
4. Copy the generated URL
5. Open URL in browser and select your server

### 6. Server Setup

After inviting the bot:

1. **Create Channels** (if needed):
   - `#pokemon-alerts` - For stock notifications
   - `#bot-commands` - For bot interactions

2. **Set Up Roles**:
   - Create admin roles: `Bot Admin`, `Moderator`
   - Assign roles to trusted users

3. **Test Bot**:
   ```
   /help
   /status
   ```

## Database Setup

### Automatic Setup

The bot automatically creates and migrates the database on first run. No manual setup required.

### Manual Database Operations

#### Initialize Database
```bash
python scripts/db_migrate.py --init
```

#### Run Migrations
```bash
python scripts/db_migrate.py --migrate
```

#### Create Backup
```bash
python scripts/db_backup.py --compress --verify
```

#### Restore from Backup
```bash
python scripts/db_recovery.py --restore-latest --database /path/to/database.db
```

#### Check Database Health
```bash
python scripts/db_recovery.py --check-integrity --database /path/to/database.db
```

### Database Maintenance

#### Automated Backups

Backups run automatically when `BACKUP_ENABLED=true`:
- **Frequency**: Every hour (configurable)
- **Retention**: 7 days (configurable)
- **Compression**: Enabled by default
- **Verification**: Each backup is verified

#### Manual Maintenance

```bash
# Create immediate backup
docker-compose exec pokemon-bot python scripts/db_backup.py --compress --verify

# Clean old backups
docker-compose exec pokemon-bot python scripts/db_backup.py --cleanup

# Check database integrity
docker-compose exec pokemon-bot python scripts/db_recovery.py --check-integrity --database /app/data/pokemon_bot.db

# Vacuum database (optimize)
docker-compose exec pokemon-bot sqlite3 /app/data/pokemon_bot.db "VACUUM;"
```

## Monitoring Setup

### Health Checks

The bot exposes a health check endpoint on port 8080:

```bash
# Check bot health
curl http://localhost:8080/health

# Get metrics
curl http://localhost:8080/metrics
```

### Log Monitoring

#### View Logs
```bash
# Docker logs
docker-compose logs -f pokemon-bot

# File logs
tail -f logs/pokemon_bot.log
```

#### Log Rotation

Logs are automatically rotated:
- **Max size**: 10MB per file
- **Backup count**: 5 files
- **Compression**: Automatic for old logs

### Performance Monitoring

#### Key Metrics to Monitor

1. **Response Time**: Average time to check products
2. **Success Rate**: Percentage of successful checks
3. **Error Rate**: Number of errors per hour
4. **Memory Usage**: RAM consumption
5. **Database Size**: Storage usage

#### Monitoring Commands

```bash
# System resources
docker stats pokemon-bot-prod

# Database size
du -h data/pokemon_bot.db

# Log analysis
grep "ERROR" logs/pokemon_bot.log | tail -20
```

### Alerting Setup

#### Discord Alerts

The bot can send alerts to a designated admin channel:

```yaml
# In config.yaml
alerts:
  enabled: true
  channel_id: 123456789  # Admin channel ID
  error_threshold: 10    # Errors per hour
  downtime_threshold: 300  # Seconds
```

#### External Monitoring

**Uptime Robot Setup:**
1. Create account at [Uptime Robot](https://uptimerobot.com)
2. Add HTTP monitor: `http://your-server:8080/health`
3. Set check interval: 5 minutes
4. Configure alerts (email, SMS, webhook)

**Prometheus + Grafana:**
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'pokemon-bot'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

## Troubleshooting

### Common Issues

#### Bot Not Starting

**Symptoms**: Container exits immediately or fails to start

**Solutions**:
1. Check Discord token:
   ```bash
   # Verify token format
   echo $DISCORD_TOKEN | wc -c  # Should be ~70 characters
   ```

2. Check permissions:
   ```bash
   # Verify file permissions
   ls -la data/ logs/
   ```

3. Check logs:
   ```bash
   docker-compose logs pokemon-bot
   ```

#### Commands Not Working

**Symptoms**: Bot doesn't respond to slash commands

**Solutions**:
1. Check bot permissions in Discord server
2. Verify bot has "Use Slash Commands" permission
3. Re-invite bot with correct permissions
4. Check if commands are registered:
   ```bash
   docker-compose logs pokemon-bot | grep "Registered commands"
   ```

#### Monitoring Not Working

**Symptoms**: Products not being checked or notifications not sent

**Solutions**:
1. Check network connectivity:
   ```bash
   docker-compose exec pokemon-bot curl -I https://www.bol.com
   ```

2. Verify product URLs are accessible
3. Check monitoring logs:
   ```bash
   docker-compose logs pokemon-bot | grep "Monitoring"
   ```

4. Test individual product:
   ```bash
   # Add test product with short interval
   /add-product url:https://www.bol.com/nl/nl/p/test/ channel:#test interval:30
   ```

#### High Memory Usage

**Symptoms**: Bot consuming excessive RAM

**Solutions**:
1. Reduce concurrent monitors:
   ```env
   MAX_CONCURRENT=5
   ```

2. Increase monitoring intervals:
   ```env
   MONITORING_INTERVAL=120
   ```

3. Check for memory leaks:
   ```bash
   docker stats pokemon-bot-prod
   ```

#### Database Issues

**Symptoms**: Database errors or corruption

**Solutions**:
1. Check database integrity:
   ```bash
   python scripts/db_recovery.py --check-integrity --database data/pokemon_bot.db
   ```

2. Restore from backup:
   ```bash
   python scripts/db_recovery.py --restore-latest --database data/pokemon_bot.db
   ```

3. Repair database:
   ```bash
   python scripts/db_recovery.py --repair --database data/pokemon_bot.db
   ```

### Debug Mode

Enable debug logging for troubleshooting:

```env
LOG_LEVEL=DEBUG
```

Then restart the bot and check logs:
```bash
docker-compose restart pokemon-bot
docker-compose logs -f pokemon-bot
```

### Getting Help

1. **Check Documentation**: Review this guide and API documentation
2. **Search Issues**: Look for similar problems in GitHub issues
3. **Enable Debug Logging**: Set `LOG_LEVEL=DEBUG` for detailed logs
4. **Create Issue**: If problem persists, create a GitHub issue with:
   - Bot version
   - Configuration (remove sensitive data)
   - Error logs
   - Steps to reproduce

### Performance Tuning

#### Optimize for Speed
```env
# Faster monitoring
MONITORING_INTERVAL=30
MAX_CONCURRENT=20

# Reduce delays
REQUEST_DELAY_MIN=0.5
REQUEST_DELAY_MAX=1.5
```

#### Optimize for Stability
```env
# Slower but more reliable
MONITORING_INTERVAL=120
MAX_CONCURRENT=5

# Longer delays to avoid detection
REQUEST_DELAY_MIN=2
REQUEST_DELAY_MAX=5
```

#### Optimize for Resource Usage
```env
# Lower resource usage
MAX_CONCURRENT=3
BACKUP_INTERVAL=7200
LOG_LEVEL=WARNING
```

## Security Considerations

### Bot Token Security
- Never commit tokens to version control
- Use environment variables or secure secret management
- Rotate tokens regularly
- Restrict bot permissions to minimum required

### Server Security
- Keep system updated
- Use firewall to restrict access
- Monitor logs for suspicious activity
- Use HTTPS for webhooks

### Discord Security
- Limit admin roles
- Monitor bot usage
- Review permissions regularly
- Use 2FA on Discord account

## Maintenance

### Regular Tasks

**Daily**:
- Check bot status and logs
- Monitor resource usage
- Verify notifications are working

**Weekly**:
- Review error logs
- Check database size
- Test backup restoration
- Update dependencies if needed

**Monthly**:
- Rotate bot token (optional)
- Review and clean old logs
- Performance optimization
- Security audit

### Updates

```bash
# Update bot
git pull origin main
docker-compose build --no-cache
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs -f pokemon-bot
```

This completes the comprehensive setup guide. The bot should now be fully configured and ready for production use.