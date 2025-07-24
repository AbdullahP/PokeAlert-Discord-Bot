# Pokemon Discord Bot - User Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Discord Commands](#discord-commands)
3. [Admin Features](#admin-features)
4. [Notification System](#notification-system)
5. [Troubleshooting](#troubleshooting)
6. [FAQ](#faq)

## Getting Started

### What is the Pokemon Discord Bot?

The Pokemon Discord Bot is an advanced monitoring system that tracks Pokemon product availability on bol.com and sends instant notifications to your Discord server when items come in stock. It's designed to give you the fastest possible alerts so you never miss out on limited Pokemon products.

### Key Features

- **⚡ Lightning Fast**: Notifications within 10 seconds of stock changes
- **🎯 Precise Monitoring**: Tracks individual products and entire wishlists
- **🔔 Smart Notifications**: Rich embeds with product images, prices, and direct links
- **👑 Admin Controls**: Comprehensive management tools for server administrators
- **📊 Performance Dashboard**: Real-time monitoring statistics and health metrics
- **🛡️ Anti-Detection**: Advanced stealth measures to avoid being blocked
- **💾 Reliable**: Automatic backups and error recovery

### Prerequisites

To use the bot, you need:
- A Discord server where you have admin permissions
- The bot must be invited to your server with proper permissions
- Admin role (Admin, Moderator, or Bot Admin) to manage monitoring

## Discord Commands

### User Commands (Available to Everyone)

#### `/help`
**Description**: Display help information and available commands.

**Usage**: `/help`

**Example Response**:
```
🤖 **Pokemon Stock Monitor Bot**

**User Commands:**
• `/help` - Show this help message
• `/status` - Check bot status

**Admin Commands:**
• `/add-product` - Add product for monitoring
• `/remove-product` - Remove product from monitoring
• `/list-products` - Show all monitored products
• `/dashboard` - View monitoring dashboard

Need help? Contact a server admin or check the documentation.
```

#### `/status`
**Description**: Show basic bot status and statistics.

**Usage**: `/status`

**Example Response**:
```
✅ **Bot Status: Online**

📊 **Quick Stats:**
• Products Monitored: 15
• Success Rate: 98.2%
• Uptime: 2 days, 14 hours
• Last Check: 23 seconds ago

🔔 **Recent Activity:**
• 3 notifications sent today
• 0 errors in last hour
• All systems operational
```

### Admin Commands (Requires Admin Role)

#### `/add-product`
**Description**: Add a new product or wishlist URL for monitoring.

**Usage**: `/add-product url:<bol.com_url> channel:<#channel> [interval:<seconds>] [roles:<@role1,@role2>]`

**Parameters**:
- `url` (required): bol.com product or wishlist URL
- `channel` (required): Discord channel for notifications
- `interval` (optional): Monitoring interval in seconds (default: 60, minimum: 30)
- `roles` (optional): Roles to mention in notifications (comma-separated)

**Examples**:
```
# Add single product
/add-product url:https://www.bol.com/nl/nl/p/pokemon-tcg-booster-box/123456/ channel:#pokemon-alerts

# Add with custom interval and role mentions
/add-product url:https://www.bol.com/nl/nl/p/pokemon-plushie/789012/ channel:#alerts interval:45 roles:@Pokemon Fans,@Collectors

# Add entire wishlist
/add-product url:https://www.bol.com/nl/nl/account/wenslijst/123456789/ channel:#pokemon-alerts interval:30
```

**Success Response**:
```
✅ **Product Added Successfully**

📦 **Product**: Pokemon TCG Booster Box
💰 **Price**: €89.99
📍 **Channel**: #pokemon-alerts
⏱️ **Interval**: 60 seconds
🏷️ **Mentions**: @Pokemon Fans

🆔 **Product ID**: abc123
📊 **Status**: Monitoring started
```

#### `/remove-product`
**Description**: Remove a product from monitoring.

**Usage**: `/remove-product product_id:<product_id>`

**Parameters**:
- `product_id` (required): Product ID to remove (shown in `/list-products`)

**Example**:
```
/remove-product product_id:abc123
```

**Success Response**:
```
✅ **Product Removed**

The product has been removed from monitoring.
• Product ID: abc123
• Monitoring stopped
• No more notifications will be sent
```

#### `/list-products`
**Description**: List all monitored products for the current server.

**Usage**: `/list-products [channel:<#channel>] [status:<active|inactive|error>]`

**Parameters**:
- `channel` (optional): Filter by specific channel
- `status` (optional): Filter by monitoring status

**Examples**:
```
# List all products
/list-products

# List products for specific channel
/list-products channel:#pokemon-alerts

# List only active products
/list-products status:active
```

**Example Response**:
```
📦 **Monitored Products (5 total)**

**🟢 Active (3)**
1. **Pokemon TCG Booster Box** - #pokemon-alerts
   • Status: ✅ In Stock (€89.99)
   • ID: abc123 | Interval: 60s | Last check: 30s ago

2. **Pokemon Plushie Collection** - #general
   • Status: ❌ Out of Stock (€24.99)
   • ID: def456 | Interval: 45s | Last check: 15s ago

3. **Pokemon Game Bundle** - #gaming
   • Status: ⏳ Checking... (€59.99)
   • ID: ghi789 | Interval: 30s | Last check: 5s ago

**🔴 Inactive (1)**
4. **Pokemon Cards Set** - #pokemon-alerts
   • Status: ⚠️ Error (URL not accessible)
   • ID: jkl012 | Last error: 2 hours ago

**📊 Performance**: 98.5% uptime | 2.3s avg response time
```

#### `/product-status`
**Description**: Get detailed status for a specific product.

**Usage**: `/product-status product_id:<product_id>`

**Parameters**:
- `product_id` (required): Product ID to check

**Example**:
```
/product-status product_id:abc123
```

**Example Response**:
```
📦 **Product Status Details**

**Pokemon TCG Scarlet & Violet Booster Box**
🆔 **ID**: abc123
🔗 **URL**: https://www.bol.com/nl/nl/p/pokemon-tcg/123456/
📍 **Channel**: #pokemon-alerts
🏷️ **Mentions**: @Pokemon Fans, @Collectors

**📊 Current Status**
• Stock: ✅ In Stock
• Price: €89.99 (was €94.99)
• Last Check: 23 seconds ago
• Next Check: in 37 seconds

**📈 Performance (24h)**
• Success Rate: 99.2% (238/240 checks)
• Avg Response Time: 2.1 seconds
• Stock Changes: 2 times
• Notifications Sent: 2

**📅 Recent Activity**
• 2 hours ago: Stock changed from Out of Stock → In Stock
• 6 hours ago: Price changed from €94.99 → €89.99
• 1 day ago: Added to monitoring
```

#### `/dashboard`
**Description**: Display comprehensive monitoring dashboard.

**Usage**: `/dashboard`

**Example Response**:
```
📊 **Pokemon Bot Dashboard**

**🎯 Overview**
• Total Products: 15 monitored
• Active Monitors: 14 running
• Success Rate: 98.5% (last 24h)
• Avg Response Time: 2.3 seconds

**📈 Performance (24h)**
• Total Checks: 1,440
• Successful: 1,418
• Failed: 22
• Stock Changes: 8
• Notifications Sent: 12

**🔔 Recent Stock Changes**
• Pokemon Booster Box → In Stock (2 hours ago)
• Pokemon Plushie Set → Out of Stock (4 hours ago)
• Pokemon Game Bundle → In Stock (6 hours ago)

**⚠️ Issues**
• 1 product with errors (jkl012)
• 0 rate limit warnings
• 0 critical alerts

**💾 System Health**
• Database: ✅ Healthy (12.5 MB)
• Discord API: ✅ Connected (45ms latency)
• Memory Usage: 245 MB
• Uptime: 2 days, 14 hours

**📅 Last Updated**: Just now
```

#### `/configure`
**Description**: Configure bot settings for the server.

**Usage**: `/configure setting:<setting_name> value:<new_value>`

**Available Settings**:
- `default_interval`: Default monitoring interval (30-300 seconds)
- `max_products`: Maximum products per server (1-100)
- `notification_cooldown`: Cooldown between similar notifications (60-3600 seconds)
- `admin_roles`: Comma-separated list of admin role names

**Examples**:
```
# Set default monitoring interval
/configure setting:default_interval value:45

# Set maximum products per server
/configure setting:max_products value:50

# Update admin roles
/configure setting:admin_roles value:Admin,Moderator,Staff
```

## Admin Features

### Product Management

#### Adding Products

**Single Products**:
- Use direct bol.com product URLs
- Bot automatically extracts product information
- Supports all Pokemon-related products

**Wishlists**:
- Use bol.com wishlist URLs
- Bot monitors all products in the wishlist
- Automatically adds new products added to the wishlist
- More efficient than adding products individually

#### Monitoring Configuration

**Intervals**:
- Minimum: 30 seconds (to avoid rate limiting)
- Default: 60 seconds (good balance of speed and reliability)
- Maximum: 300 seconds (for stable products)
- Lower intervals = faster notifications but higher resource usage

**Channel Assignment**:
- Each product can be assigned to a specific channel
- Supports multiple channels per server
- Bot needs "Send Messages" permission in target channels

**Role Mentions**:
- Configure which roles get mentioned in notifications
- Supports multiple roles per product
- Use @role format or role names

### Performance Monitoring

#### Dashboard Metrics

**Success Rate**: Percentage of successful monitoring checks
- 95%+ = Excellent
- 90-95% = Good
- <90% = Needs attention

**Response Time**: Average time to check each product
- <3 seconds = Excellent
- 3-5 seconds = Good
- >5 seconds = Slow (check network/server)

**Error Tracking**: Monitor and resolve issues
- Network errors: Usually temporary
- Parsing errors: May indicate bol.com changes
- Database errors: Check disk space and permissions

#### Health Monitoring

**System Status**:
- Memory usage and CPU utilization
- Database health and size
- Discord API connectivity
- Uptime and reliability metrics

**Alerts**:
- Automatic notifications for critical issues
- Configurable thresholds and cooldowns
- Multiple notification channels (Discord, email, webhook)

### Backup and Recovery

#### Automatic Backups

**Schedule**:
- Hourly backups by default
- Compressed and verified
- 7-day retention policy

**Manual Backups**:
- Use `/backup create` command
- Download backup files if needed
- Restore from specific backup points

#### Data Recovery

**Database Issues**:
- Automatic integrity checks
- Self-healing for minor corruption
- Manual recovery tools available

**Configuration Recovery**:
- Settings backed up with database
- Easy restoration of monitoring configurations
- Export/import functionality for server migration

## Notification System

### Notification Format

#### Stock In Notifications
```
🟢 **POKEMON PRODUCT IN STOCK!**

**Pokemon TCG Scarlet & Violet Booster Box**
💰 **Price**: €89.99 ~~€94.99~~
📦 **Stock**: In Stock
🚚 **Delivery**: Tomorrow before 23:59

🛒 **[BUY NOW](https://www.bol.com/nl/nl/p/pokemon-tcg/123456/)**

@Pokemon Fans @Collectors
```

#### Stock Out Notifications
```
🔴 **Product Out of Stock**

**Pokemon Plushie Collection**
💰 **Price**: €24.99
📦 **Stock**: Out of Stock
⏰ **Last Available**: 2 minutes ago

We'll notify you when it's back in stock!
```

#### Price Change Notifications
```
💰 **Price Change Alert**

**Pokemon Game Bundle**
📉 **New Price**: €45.99 (was €59.99)
💵 **Savings**: €14.00 (23% off)
📦 **Stock**: In Stock

🛒 **[BUY NOW](https://www.bol.com/nl/nl/p/pokemon-game/789012/)**
```

### Notification Settings

#### Frequency Control
- Cooldown periods prevent spam
- Smart deduplication for similar notifications
- Rate limiting to respect Discord limits

#### Customization Options
- Custom embed colors per server
- Configurable mention patterns
- Optional price tracking
- Thumbnail images when available

#### Delivery Reliability
- Automatic retry for failed notifications
- Queue system for high-volume periods
- Fallback channels for critical alerts

## Troubleshooting

### Common Issues

#### Bot Not Responding
**Symptoms**: Commands don't work or bot appears offline

**Solutions**:
1. Check bot permissions in server settings
2. Verify bot has "Use Slash Commands" permission
3. Try `/status` command to test connectivity
4. Contact server admin if issues persist

#### No Notifications Received
**Symptoms**: Products are monitored but no alerts sent

**Solutions**:
1. Check channel permissions (bot needs "Send Messages")
2. Verify product URLs are accessible
3. Check if product is actually changing stock status
4. Review notification settings with `/list-products`

#### Slow or Missing Updates
**Symptoms**: Notifications arrive late or not at all

**Solutions**:
1. Check monitoring intervals with `/list-products`
2. Verify bot system health with `/dashboard`
3. Consider reducing number of monitored products
4. Check for rate limiting warnings

#### Permission Errors
**Symptoms**: "You don't have permission" messages

**Solutions**:
1. Verify you have admin role (Admin, Moderator, or Bot Admin)
2. Check server role hierarchy
3. Contact server owner to assign proper roles
4. Review bot configuration with server admin

### Error Messages

#### Common Error Codes

**INVALID_URL**: 
- Problem: URL is not a valid bol.com link
- Solution: Use direct product or wishlist URLs from bol.com

**CHANNEL_NOT_FOUND**:
- Problem: Specified channel doesn't exist or bot can't access it
- Solution: Verify channel exists and bot has permissions

**PRODUCT_EXISTS**:
- Problem: Product is already being monitored
- Solution: Use `/list-products` to find existing product ID

**RATE_LIMIT**:
- Problem: Too many commands sent too quickly
- Solution: Wait a few seconds before trying again

**DATABASE_ERROR**:
- Problem: Internal database issue
- Solution: Contact admin, issue usually resolves automatically

### Getting Help

#### Self-Service Options
1. Use `/help` command for quick reference
2. Check `/status` for system health
3. Review `/dashboard` for performance metrics
4. Try `/list-products` to verify configuration

#### Admin Support
1. Contact server administrators
2. Check server announcement channels
3. Review bot logs if you have access
4. Use support channels if available

#### Technical Support
1. GitHub Issues for bug reports
2. Discord support server
3. Documentation wiki
4. Email support for critical issues

## FAQ

### General Questions

**Q: How fast are the notifications?**
A: Notifications are typically sent within 10 seconds of a stock change, depending on the monitoring interval and server performance.

**Q: Can I monitor products from other websites?**
A: Currently, the bot only supports bol.com. Support for additional websites may be added in the future.

**Q: How many products can I monitor?**
A: The default limit is 100 products per server, but this can be configured by server administrators.

**Q: Does the bot work 24/7?**
A: Yes, the bot runs continuously and monitors products around the clock.

### Technical Questions

**Q: Why do some products show "Error" status?**
A: This usually means the product URL is no longer accessible, the product was removed, or there's a temporary network issue.

**Q: Can I change the monitoring interval for existing products?**
A: Currently, you need to remove and re-add the product with a new interval. A direct edit feature may be added in the future.

**Q: What happens if the bot goes offline?**
A: The bot has automatic recovery mechanisms and will resume monitoring when it comes back online. No configuration is lost.

**Q: How accurate are the stock notifications?**
A: The bot directly checks bol.com's website, so accuracy depends on how quickly bol.com updates their stock information.

### Privacy and Security

**Q: What data does the bot store?**
A: The bot stores product URLs, monitoring configurations, and performance metrics. No personal user data is collected.

**Q: Is my Discord server information secure?**
A: Yes, the bot only accesses channels it's given permission to and doesn't store unnecessary server data.

**Q: Can other servers see my monitored products?**
A: No, each server's monitoring configuration is completely separate and private.

### Troubleshooting

**Q: Why am I getting duplicate notifications?**
A: This can happen if the same product is added multiple times or if there are rapid stock changes. Check `/list-products` for duplicates.

**Q: The bot says a product is in stock, but I can't buy it. Why?**
A: Stock can change very quickly. The notification shows the status at the time of checking, but it may have sold out by the time you see the message.

**Q: Can I test if notifications are working?**
A: Yes, add a product that frequently changes stock status, or contact an admin to run a test notification.

**Q: Why are some product images missing from notifications?**
A: Some products don't have images available, or there may be temporary issues loading images from bol.com.

---

## Need More Help?

If you can't find the answer to your question in this guide:

1. **Try the bot commands**: Start with `/help` and `/status`
2. **Contact server admins**: They can help with server-specific issues
3. **Check the documentation**: Visit our GitHub wiki for detailed guides
4. **Join our support server**: Get help from other users and developers
5. **Report bugs**: Use GitHub Issues for technical problems

**Remember**: The bot is designed to be fast and reliable, but Pokemon products can sell out extremely quickly. Having notifications doesn't guarantee you'll be able to purchase items, but it gives you the best possible chance!

Happy Pokemon hunting! 🎯✨