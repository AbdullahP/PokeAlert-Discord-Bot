# Production Deployment Guide

## Overview

This guide covers deploying the Pokemon Discord Bot in a production environment with high availability, monitoring, and security best practices.

## Prerequisites

- Docker and Docker Compose installed
- Server with minimum 1GB RAM and 2GB storage
- Domain name (optional, for webhooks and monitoring)
- SSL certificate (if using custom domain)

## Quick Production Deployment

### 1. Server Setup

```bash
# Create application directory
sudo mkdir -p /opt/pokemon-bot
cd /opt/pokemon-bot

# Clone repository
git clone https://github.com/your-username/pokemon-discord-bot.git .

# Set proper permissions
sudo chown -R $USER:$USER /opt/pokemon-bot
chmod +x scripts/*.sh scripts/*.py
```

### 2. Environment Configuration

```bash
# Copy production environment template
cp .env.production .env

# Edit configuration
nano .env
```

**Required Environment Variables:**
```env
# Discord Configuration
DISCORD_TOKEN=your_production_bot_token
DISCORD_GUILD_ID=your_server_id

# Application Settings
ENVIRONMENT=production
LOG_LEVEL=INFO
MONITORING_INTERVAL=60
MAX_CONCURRENT=20

# Paths
DATA_PATH=/opt/pokemon-bot/data
LOGS_PATH=/opt/pokemon-bot/logs
BACKUP_PATH=/opt/pokemon-bot/backups

# Backup Configuration
BACKUP_ENABLED=true
BACKUP_INTERVAL=3600
BACKUP_RETENTION_DAYS=7

# Monitoring
HEALTH_CHECK_PORT=8080
METRICS_ENABLED=true
```

### 3. Deploy with Docker Compose

```bash
# Create required directories
mkdir -p data logs backups

# Start services
docker-compose up -d

# Verify deployment
docker-compose ps
docker-compose logs -f pokemon-bot
```

### 4. Verify Deployment

```bash
# Check health endpoint
curl http://localhost:8080/health

# Check metrics
curl http://localhost:8080/metrics

# Test Discord commands
# In Discord: /status
```

## Advanced Production Setup

### SSL/TLS Configuration

If exposing health check endpoint publicly:

```yaml
# docker-compose.override.yml
version: '3.8'
services:
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - pokemon-bot
```

**nginx.conf:**
```nginx
events {
    worker_connections 1024;
}

http {
    upstream pokemon-bot {
        server pokemon-bot:8080;
    }

    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl;
        server_name your-domain.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;

        location /health {
            proxy_pass http://pokemon-bot;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        location /metrics {
            proxy_pass http://pokemon-bot;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            
            # Restrict access to metrics
            allow 10.0.0.0/8;
            allow 172.16.0.0/12;
            allow 192.168.0.0/16;
            deny all;
        }
    }
}
```

### Monitoring Integration

#### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 30s

scrape_configs:
  - job_name: 'pokemon-bot'
    static_configs:
      - targets: ['pokemon-bot:8080']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

#### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Pokemon Discord Bot",
    "panels": [
      {
        "title": "Success Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "pokemon_bot_success_rate * 100"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "pokemon_bot_response_time_seconds"
          }
        ]
      },
      {
        "title": "Products Monitored",
        "type": "stat",
        "targets": [
          {
            "expr": "pokemon_bot_products_total"
          }
        ]
      }
    ]
  }
}
```

### Backup Strategy

#### Automated Backups

The bot includes automated backup functionality:

```bash
# Manual backup
docker-compose exec pokemon-bot python scripts/db_backup.py --compress --verify

# Check backup status
docker-compose exec pokemon-bot python scripts/db_backup.py --list-backups

# Restore from backup
docker-compose exec pokemon-bot python scripts/db_recovery.py --restore-latest --database /app/data/pokemon_bot.db
```

#### External Backup Storage

**AWS S3 Integration:**
```bash
# Install AWS CLI in backup container
# Add to docker-compose.yml backup service:
environment:
  - AWS_ACCESS_KEY_ID=your_key
  - AWS_SECRET_ACCESS_KEY=your_secret
  - AWS_DEFAULT_REGION=us-east-1
  - S3_BUCKET=pokemon-bot-backups

# Backup script with S3 upload
command: >
  sh -c "
    python /app/scripts/db_backup.py --compress --verify &&
    aws s3 sync /app/backups s3://pokemon-bot-backups/$(date +%Y-%m-%d)/
  "
```

### Security Hardening

#### Container Security

```yaml
# docker-compose.yml security enhancements
services:
  pokemon-bot:
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp:noexec,nosuid,size=100m
    user: "1000:1000"
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
```

#### Network Security

```yaml
# Restrict network access
networks:
  pokemon-bot-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
    driver_opts:
      com.docker.network.bridge.enable_icc: "false"
      com.docker.network.bridge.enable_ip_masquerade: "true"
```

#### Secrets Management

```bash
# Use Docker secrets for sensitive data
echo "your_discord_token" | docker secret create discord_token -
echo "your_database_password" | docker secret create db_password -
```

```yaml
# docker-compose.yml
services:
  pokemon-bot:
    secrets:
      - discord_token
      - db_password
    environment:
      - DISCORD_TOKEN_FILE=/run/secrets/discord_token

secrets:
  discord_token:
    external: true
  db_password:
    external: true
```

### High Availability Setup

#### Multi-Instance Deployment

```yaml
# docker-compose.ha.yml
version: '3.8'
services:
  pokemon-bot-1:
    extends:
      file: docker-compose.yml
      service: pokemon-bot
    container_name: pokemon-bot-1
    
  pokemon-bot-2:
    extends:
      file: docker-compose.yml
      service: pokemon-bot
    container_name: pokemon-bot-2
    
  load-balancer:
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - ./nginx-lb.conf:/etc/nginx/nginx.conf
    depends_on:
      - pokemon-bot-1
      - pokemon-bot-2
```

#### Database Clustering

For high-availability database setup:

```yaml
services:
  postgres-primary:
    image: postgres:15
    environment:
      POSTGRES_DB: pokemon_bot
      POSTGRES_USER: pokemon
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_REPLICATION_USER: replicator
      POSTGRES_REPLICATION_PASSWORD: ${REPLICATION_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgresql.conf:/etc/postgresql/postgresql.conf
    command: postgres -c config_file=/etc/postgresql/postgresql.conf
    
  postgres-replica:
    image: postgres:15
    environment:
      PGUSER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    command: |
      bash -c "
      until pg_basebackup --pgdata=/var/lib/postgresql/data -R --slot=replication_slot --host=postgres-primary --port=5432
      do
        echo 'Waiting for primary to connect...'
        sleep 1s
      done
      echo 'Backup done, starting replica...'
      chmod 0700 /var/lib/postgresql/data
      postgres
      "
    depends_on:
      - postgres-primary
```

### Performance Optimization

#### Resource Limits

```yaml
# docker-compose.yml
services:
  pokemon-bot:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'
```

#### Caching Layer

```yaml
services:
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    
  pokemon-bot:
    environment:
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
```

### Monitoring and Alerting

#### Health Check Configuration

```yaml
# docker-compose.yml
services:
  pokemon-bot:
    healthcheck:
      test: ["CMD", "python", "/app/src/health_check.py"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
```

#### External Monitoring

**Uptime Robot Setup:**
1. Create account at uptimerobot.com
2. Add HTTP monitor for `https://your-domain.com/health`
3. Set 5-minute intervals
4. Configure email/SMS alerts

**DataDog Integration:**
```yaml
services:
  datadog:
    image: datadog/agent:latest
    environment:
      - DD_API_KEY=${DATADOG_API_KEY}
      - DD_SITE=datadoghq.com
      - DD_LOGS_ENABLED=true
      - DD_PROCESS_AGENT_ENABLED=true
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /proc/:/host/proc/:ro
      - /sys/fs/cgroup/:/host/sys/fs/cgroup:ro
```

### Logging and Debugging

#### Centralized Logging

```yaml
services:
  elasticsearch:
    image: elasticsearch:8.5.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    
  logstash:
    image: logstash:8.5.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
    depends_on:
      - elasticsearch
      
  kibana:
    image: kibana:8.5.0
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch
```

#### Log Rotation

```yaml
services:
  pokemon-bot:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Disaster Recovery

#### Backup Procedures

```bash
#!/bin/bash
# backup-script.sh

# Create full backup
docker-compose exec pokemon-bot python scripts/db_backup.py --compress --verify

# Backup configuration
tar -czf config-backup-$(date +%Y%m%d).tar.gz config/ .env

# Upload to remote storage
aws s3 cp config-backup-$(date +%Y%m%d).tar.gz s3://pokemon-bot-backups/config/

# Clean old backups
find backups/ -name "*.db.gz" -mtime +7 -delete
```

#### Recovery Procedures

```bash
#!/bin/bash
# recovery-script.sh

# Stop services
docker-compose down

# Restore database
docker-compose run --rm pokemon-bot python scripts/db_recovery.py --restore-latest --database /app/data/pokemon_bot.db

# Restore configuration
tar -xzf config-backup-latest.tar.gz

# Start services
docker-compose up -d

# Verify recovery
curl http://localhost:8080/health
```

### Maintenance Procedures

#### Regular Maintenance Tasks

```bash
#!/bin/bash
# maintenance.sh

# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Docker images
docker-compose pull
docker-compose up -d

# Clean up old images
docker image prune -f

# Vacuum database
docker-compose exec pokemon-bot sqlite3 /app/data/pokemon_bot.db "VACUUM;"

# Check disk space
df -h

# Review logs
docker-compose logs --tail=100 pokemon-bot | grep ERROR
```

#### Scheduled Maintenance

```cron
# /etc/cron.d/pokemon-bot-maintenance

# Daily backup at 2 AM
0 2 * * * /opt/pokemon-bot/scripts/backup.sh

# Weekly maintenance at 3 AM Sunday
0 3 * * 0 /opt/pokemon-bot/scripts/maintenance.sh

# Monthly log cleanup at 4 AM first day of month
0 4 1 * * /opt/pokemon-bot/scripts/cleanup-logs.sh
```

### Troubleshooting Production Issues

#### Common Production Issues

**High Memory Usage:**
```bash
# Check memory usage
docker stats pokemon-bot-prod

# Restart if needed
docker-compose restart pokemon-bot

# Check for memory leaks
docker-compose logs pokemon-bot | grep -i memory
```

**Database Lock Issues:**
```bash
# Check for long-running transactions
docker-compose exec pokemon-bot sqlite3 /app/data/pokemon_bot.db ".timeout 1000"

# Force unlock if needed
docker-compose exec pokemon-bot sqlite3 /app/data/pokemon_bot.db "BEGIN IMMEDIATE; ROLLBACK;"
```

**Network Connectivity Issues:**
```bash
# Test external connectivity
docker-compose exec pokemon-bot curl -I https://www.bol.com

# Check DNS resolution
docker-compose exec pokemon-bot nslookup www.bol.com

# Test Discord API
docker-compose exec pokemon-bot curl -I https://discord.com/api/v10/gateway
```

#### Emergency Procedures

**Complete System Failure:**
1. Check system resources: `htop`, `df -h`
2. Review Docker logs: `docker-compose logs`
3. Restart services: `docker-compose restart`
4. Restore from backup if needed
5. Contact support if issues persist

**Data Corruption:**
1. Stop bot immediately: `docker-compose stop pokemon-bot`
2. Create backup of current state
3. Run integrity check: `python scripts/db_recovery.py --check-integrity`
4. Attempt repair: `python scripts/db_recovery.py --repair`
5. Restore from backup if repair fails

This completes the production deployment guide. The bot should now be fully configured for production use with monitoring, backups, and high availability.