# Pokemon Discord Bot - API Documentation

## Overview

The Pokemon Discord Bot provides a comprehensive monitoring system for bol.com Pokemon product availability with Discord integration. This document covers all APIs, commands, and integration points.

## Table of Contents

1. [Discord Commands](#discord-commands)
2. [Configuration API](#configuration-api)
3. [Health Check API](#health-check-api)
4. [Database Schema](#database-schema)
5. [Error Codes](#error-codes)
6. [Rate Limits](#rate-limits)

## Discord Commands

### Admin Commands

All admin commands require appropriate Discord permissions (Admin, Moderator, or Bot Admin roles).

#### `/add-product`
Add a new product or wishlist URL for monitoring.

**Parameters:**
- `url` (required): bol.com product or wishlist URL
- `channel` (required): Discord channel for notifications
- `interval` (optional): Monitoring interval in seconds (default: 60, minimum: 30)
- `roles` (optional): Comma-separated list of roles to mention

**Example:**
```
/add-product url:https://www.bol.com/nl/nl/p/pokemon-tcg-scarlet-violet-paldea-evolved-booster-box/9300000135849797/ channel:#pokemon-alerts interval:45 roles:@Pokemon Fans,@Collectors
```

**Response:**
```json
{
  "success": true,
  "product_id": "abc123",
  "message": "Product added successfully",
  "monitoring_status": "active"
}
```

#### `/remove-product`
Remove a product from monitoring.

**Parameters:**
- `product_id` (required): Product ID to remove

**Example:**
```
/remove-product product_id:abc123
```

#### `/list-products`
List all monitored products for the current server.

**Parameters:**
- `channel` (optional): Filter by specific channel
- `status` (optional): Filter by status (active, inactive, error)

**Response Format:**
```
📦 **Monitored Products**

**Active (3)**
1. Pokemon TCG Booster Box - #pokemon-alerts - ✅ In Stock
2. Pokemon Plushie Collection - #general - ❌ Out of Stock
3. Pokemon Game Bundle - #gaming - ⏳ Checking...

**Performance:** 98.5% uptime, 2.3s avg response time
```

#### `/product-status`
Get detailed status for a specific product.

**Parameters:**
- `product_id` (required): Product ID to check

#### `/dashboard`
Display comprehensive monitoring dashboard.

**Response includes:**
- Total products monitored
- Success rate and performance metrics
- Recent stock changes
- Error summary
- System health status

### User Commands

#### `/help`
Display help information and available commands.

#### `/status`
Show bot status and basic statistics (available to all users).

## Configuration API

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DISCORD_TOKEN` | Discord bot token | - | Yes |
| `DISCORD_GUILD_ID` | Discord server ID | - | Yes |
| `DATABASE_URL` | SQLite database path | `/app/data/pokemon_bot.db` | No |
| `LOG_LEVEL` | Logging level | `INFO` | No |
| `MONITORING_INTERVAL` | Default monitoring interval (seconds) | `60` | No |
| `MAX_CONCURRENT` | Max concurrent monitoring tasks | `10` | No |
| `BACKUP_ENABLED` | Enable automatic backups | `true` | No |
| `BACKUP_INTERVAL` | Backup interval (seconds) | `3600` | No |
| `BACKUP_RETENTION_DAYS` | Backup retention period | `7` | No |
| `HEALTH_CHECK_PORT` | Health check HTTP port | `8080` | No |
| `ADMIN_ROLE_NAMES` | Comma-separated admin role names | `Admin,Moderator,Bot Admin` | No |

### Configuration Files

#### `config/config.yaml`
Main configuration file for application settings.

```yaml
discord:
  command_prefix: "!"
  max_message_length: 2000
  embed_color: 0x3498db

monitoring:
  default_interval: 60
  min_interval: 30
  max_concurrent: 10
  timeout: 30
  retry_attempts: 3
  retry_delay: 5

notifications:
  max_per_minute: 30
  queue_size: 1000
  retry_attempts: 3
  embed_thumbnail: true

database:
  connection_timeout: 30
  max_connections: 10
  backup_on_startup: true

logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  max_file_size: "10MB"
  backup_count: 5
```

#### `config/config.production.yaml`
Production-specific overrides.

```yaml
logging:
  level: WARNING
  
monitoring:
  max_concurrent: 20
  
notifications:
  max_per_minute: 60
```

## Health Check API

### GET /health
Returns bot health status and metrics.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "uptime": 86400,
  "version": "1.0.0",
  "metrics": {
    "products_monitored": 25,
    "active_monitors": 23,
    "success_rate": 98.5,
    "avg_response_time": 2.3,
    "notifications_sent_24h": 45,
    "errors_24h": 2
  },
  "database": {
    "status": "connected",
    "size_mb": 12.5,
    "last_backup": "2024-01-15T09:00:00Z"
  },
  "discord": {
    "status": "connected",
    "latency_ms": 45,
    "guilds": 1
  }
}
```

### GET /metrics
Prometheus-compatible metrics endpoint.

**Response:**
```
# HELP pokemon_bot_products_total Total number of monitored products
# TYPE pokemon_bot_products_total gauge
pokemon_bot_products_total 25

# HELP pokemon_bot_success_rate Success rate of monitoring checks
# TYPE pokemon_bot_success_rate gauge
pokemon_bot_success_rate 0.985

# HELP pokemon_bot_response_time_seconds Average response time for monitoring checks
# TYPE pokemon_bot_response_time_seconds gauge
pokemon_bot_response_time_seconds 2.3

# HELP pokemon_bot_notifications_total Total notifications sent
# TYPE pokemon_bot_notifications_total counter
pokemon_bot_notifications_total 1250
```

## Database Schema

### Tables

#### `products`
Stores monitored product configurations.

```sql
CREATE TABLE products (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    url_type TEXT NOT NULL CHECK (url_type IN ('product', 'wishlist')),
    channel_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    monitoring_interval INTEGER DEFAULT 60,
    role_mentions TEXT, -- JSON array
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `product_status`
Current status of monitored products.

```sql
CREATE TABLE product_status (
    product_id TEXT PRIMARY KEY,
    title TEXT,
    price TEXT,
    original_price TEXT,
    stock_status TEXT,
    stock_level TEXT,
    image_url TEXT,
    last_checked TIMESTAMP,
    check_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
```

#### `stock_changes`
Historical record of stock changes.

```sql
CREATE TABLE stock_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT,
    previous_status TEXT,
    current_status TEXT,
    price_change REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notification_sent BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
```

#### `monitoring_metrics`
Performance and error tracking.

```sql
CREATE TABLE monitoring_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT,
    check_duration_ms INTEGER,
    success BOOLEAN,
    error_message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
```

## Error Codes

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Missing or invalid token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |
| 503 | Service Unavailable - Bot offline |

### Discord Command Errors

| Error Code | Description | Resolution |
|------------|-------------|------------|
| `INVALID_URL` | Provided URL is not a valid bol.com link | Use a valid bol.com product or wishlist URL |
| `CHANNEL_NOT_FOUND` | Specified channel doesn't exist | Verify channel exists and bot has access |
| `PERMISSION_DENIED` | User lacks required permissions | Ensure user has admin role |
| `PRODUCT_EXISTS` | Product already being monitored | Use different URL or update existing product |
| `RATE_LIMIT` | Too many requests | Wait before retrying |
| `DATABASE_ERROR` | Database operation failed | Check logs and database health |
| `NETWORK_ERROR` | Failed to connect to bol.com | Check network connectivity |
| `PARSING_ERROR` | Failed to parse product data | bol.com may have changed their format |

### Monitoring Errors

| Error Type | Description | Auto-Recovery |
|------------|-------------|---------------|
| `NetworkTimeout` | Request to bol.com timed out | Yes, with exponential backoff |
| `HTTPError` | HTTP error from bol.com | Yes, with retry logic |
| `ParseError` | Failed to parse HTML content | No, requires manual intervention |
| `DatabaseError` | Database operation failed | Yes, with connection retry |
| `DiscordError` | Discord API error | Yes, with message queuing |

## Rate Limits

### Discord API Limits
- **Global**: 50 requests per second
- **Per Channel**: 5 messages per 5 seconds
- **Slash Commands**: 3000 per day per application

### bol.com Monitoring Limits
- **Request Rate**: 1 request per 2-5 seconds (randomized)
- **Concurrent Requests**: Maximum 10 simultaneous
- **User-Agent Rotation**: Every 10 requests
- **Retry Logic**: Exponential backoff (1s, 2s, 4s, 8s, max 30s)

### Internal Limits
- **Products per Server**: 100 maximum
- **Monitoring Interval**: 30 seconds minimum
- **Notification Queue**: 1000 messages maximum
- **Database Connections**: 10 maximum concurrent

## Webhook Integration

### Stock Change Webhooks
Configure external webhooks to receive stock change notifications.

**Webhook URL Configuration:**
```yaml
webhooks:
  stock_changes:
    - url: "https://your-webhook-url.com/pokemon-alerts"
      secret: "your-webhook-secret"
      events: ["stock_in", "stock_out", "price_change"]
```

**Webhook Payload:**
```json
{
  "event": "stock_in",
  "timestamp": "2024-01-15T10:30:00Z",
  "product": {
    "id": "abc123",
    "title": "Pokemon TCG Booster Box",
    "url": "https://www.bol.com/nl/nl/p/...",
    "price": "€89.99",
    "previous_price": "€94.99",
    "stock_status": "In Stock",
    "image_url": "https://media.bol.com/..."
  },
  "guild_id": "123456789",
  "channel_id": "987654321"
}
```

## SDK and Libraries

### Python SDK Example
```python
from pokemon_bot_client import PokemonBotClient

client = PokemonBotClient(token="your-bot-token")

# Add product for monitoring
result = await client.add_product(
    url="https://www.bol.com/nl/nl/p/pokemon-tcg/",
    channel_id=123456789,
    interval=60
)

# Get monitoring status
status = await client.get_dashboard()
print(f"Monitoring {status['total_products']} products")
```

### JavaScript/Node.js Example
```javascript
const { PokemonBotClient } = require('pokemon-bot-client');

const client = new PokemonBotClient({ token: 'your-bot-token' });

// Add product for monitoring
const result = await client.addProduct({
  url: 'https://www.bol.com/nl/nl/p/pokemon-tcg/',
  channelId: '123456789',
  interval: 60
});

console.log('Product added:', result.productId);
```

## Troubleshooting

### Common Issues

1. **Bot not responding to commands**
   - Check bot permissions in Discord server
   - Verify bot token is valid
   - Check bot status with `/status` command

2. **Products not being monitored**
   - Verify URL is accessible
   - Check monitoring interval settings
   - Review error logs for parsing issues

3. **Notifications not being sent**
   - Check channel permissions
   - Verify role mentions are valid
   - Check Discord rate limits

4. **High memory usage**
   - Review number of concurrent monitors
   - Check for memory leaks in logs
   - Consider reducing monitoring frequency

### Log Analysis

**Important log patterns to monitor:**
```
ERROR - Failed to monitor product abc123: NetworkTimeout
WARN - Discord rate limit hit, queuing notification
INFO - Stock change detected: Product xyz789 now In Stock
DEBUG - Monitoring check completed in 2.3s
```

### Performance Optimization

1. **Reduce monitoring frequency** for stable products
2. **Use wishlist URLs** instead of individual product URLs
3. **Optimize database queries** with proper indexing
4. **Monitor resource usage** and scale accordingly
5. **Implement caching** for frequently accessed data

## Support and Contact

- **Documentation**: [GitHub Wiki](https://github.com/your-repo/wiki)
- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Discord**: [Support Server](https://discord.gg/your-invite)
- **Email**: support@your-domain.com