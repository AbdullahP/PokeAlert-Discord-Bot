# PokeAlert Hetzner Cloud Deployment

Easy deployment and management scripts for running PokeAlert Discord Bot on Hetzner Cloud.

## Quick Start

### 1. Create Hetzner Server
- Go to [Hetzner Cloud Console](https://console.hetzner.cloud)
- Create new project: "PokeAlert"
- Create server:
  - **Location**: Nuremberg (Germany) or Helsinki (Finland)
  - **Image**: Ubuntu 22.04
  - **Type**: CX11 (1 vCPU, 2GB RAM) - €3.29/month
  - **SSH Key**: Add your public key

### 2. Initial Setup
```bash
# SSH into your server
ssh root@YOUR_SERVER_IP

# Download and run setup script
curl -sSL https://raw.githubusercontent.com/AbdullahP/PokeAlert-Discord-Bot/main/deploy/hetzner-setup.sh | bash

# Configure Discord token
nano /opt/pokealert/.env
# Add: DISCORD_TOKEN=your_token_here

# Start the bot
cd /opt/pokealert
docker-compose up -d
```

### 3. Verify Deployment
```bash
# Check bot status
docker-compose ps

# View logs
docker-compose logs -f

# Test health endpoint
curl http://localhost:8080/health
```

## Management Commands

### Update Bot
```bash
cd /opt/pokealert
./deploy/update.sh
```

### Monitor Bot
```bash
cd /opt/pokealert
./deploy/monitor.sh
```

### Manual Operations
```bash
# View logs
docker-compose logs -f pokemon-bot

# Restart bot
docker-compose restart pokemon-bot

# Stop bot
docker-compose down

# Start bot
docker-compose up -d

# Rebuild bot (after code changes)
docker-compose build --no-cache
docker-compose up -d
```

## Scaling Up

### Upgrade Server Resources
1. Go to Hetzner Cloud Console
2. Select your server
3. Click "Resize"
4. Choose new size:
   - **CX21**: 2 vCPU, 4GB RAM - €5.83/month
   - **CX31**: 2 vCPU, 8GB RAM - €11.66/month
5. Server resizes in ~30 seconds with no data loss

### Add More Services
```bash
# Add PostgreSQL
echo "
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: pokealert
      POSTGRES_USER: pokealert
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - pokemon-bot-network

volumes:
  postgres_data:
" >> docker-compose.yml

# Add Redis for caching
echo "
  redis:
    image: redis:7-alpine
    networks:
      - pokemon-bot-network
" >> docker-compose.yml
```

## Automated Updates with GitHub Actions

Create `.github/workflows/deploy.yml` in your repository:

```yaml
name: Deploy to Hetzner

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - name: Deploy to server
      uses: appleboy/ssh-action@v0.1.5
      with:
        host: ${{ secrets.HOST }}
        username: root
        key: ${{ secrets.SSH_KEY }}
        script: |
          cd /opt/pokealert
          ./deploy/update.sh
```

Add these secrets to your GitHub repository:
- `HOST`: Your server IP address
- `SSH_KEY`: Your private SSH key

## Monitoring & Alerts

### Set up Uptime Monitoring
1. Create account at [UptimeRobot](https://uptimerobot.com)
2. Add HTTP monitor: `http://YOUR_SERVER_IP:8080/health`
3. Set check interval: 5 minutes
4. Configure email/SMS alerts

### Log Monitoring
```bash
# Monitor error logs
tail -f /opt/pokealert/logs/production.log | grep ERROR

# Monitor Discord events
docker-compose logs -f pokemon-bot | grep "Discord"

# Monitor stock changes
docker-compose logs -f pokemon-bot | grep "Stock change"
```

## Backup & Recovery

### Automatic Backups
Your bot already includes automatic database backups:
- **Frequency**: Every hour
- **Location**: `/opt/pokealert/backups/`
- **Retention**: 7 days

### Manual Backup
```bash
# Create full backup
tar -czf pokealert-backup-$(date +%Y%m%d).tar.gz /opt/pokealert

# Backup just database
cp /opt/pokealert/data/pokemon_bot.db ~/pokemon_bot_backup_$(date +%Y%m%d).db
```

### Restore from Backup
```bash
# Stop bot
docker-compose down

# Restore database
cp ~/pokemon_bot_backup_YYYYMMDD.db /opt/pokealert/data/pokemon_bot.db

# Start bot
docker-compose up -d
```

## Security

### Firewall Setup
```bash
# Install UFW
apt install ufw

# Allow SSH
ufw allow 22

# Allow HTTP (for health checks)
ufw allow 8080

# Enable firewall
ufw enable
```

### SSL Certificate (Optional)
```bash
# Install Nginx
apt install nginx certbot python3-certbot-nginx

# Configure domain
# Point your domain to server IP
# Create Nginx config for your domain

# Get SSL certificate
certbot --nginx -d yourdomain.com
```

## Troubleshooting

### Bot Not Starting
```bash
# Check logs
docker-compose logs pokemon-bot

# Check Discord token
grep DISCORD_TOKEN /opt/pokealert/.env

# Verify permissions
ls -la /opt/pokealert/data/
```

### High Memory Usage
```bash
# Check resource usage
docker stats

# Reduce concurrent monitoring
# Edit .env: MAX_CONCURRENT=5
```

### Network Issues
```bash
# Test connectivity
curl -I https://www.bol.com

# Check DNS
nslookup bol.com

# Restart networking
systemctl restart networking
```

## Cost Optimization

### Current Costs
- **CX11 Server**: €3.29/month
- **Traffic**: Free (20TB included)
- **Backups**: €0.66/month (20% of server cost)
- **Total**: ~€4/month

### Reduce Costs
```bash
# Disable automatic backups in Hetzner Console
# Use manual backups instead

# Use smaller monitoring intervals
# Edit .env: MONITORING_INTERVAL=120
```

## Support

- **Documentation**: Check `/opt/pokealert/docs/`
- **Logs**: `docker-compose logs -f`
- **Health Check**: `http://YOUR_SERVER_IP:8080/health`
- **GitHub Issues**: Create issue with logs and configuration