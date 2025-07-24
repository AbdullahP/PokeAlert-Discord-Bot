# PokeAlert Discord Bot 🚨

A powerful Discord bot that monitors Pokemon card availability on bol.com and sends instant notifications when items come back in stock.

## Features ✨

- **Real-time Stock Monitoring** - Tracks Pokemon cards and products 24/7
- **Instant Discord Notifications** - Get notified the moment items are back in stock
- **Wishlist Support** - Monitor entire wishlists with a single command
- **Smart Anti-Detection** - Avoids rate limits and blocks
- **Dashboard Commands** - View all monitored products at a glance
- **Role Mentions** - Notify specific roles when products are available
- **Health Monitoring** - Built-in health checks and metrics

## Quick Start 🚀

### 1. Invite the Bot
[Invite PokeAlert to your Discord server](https://discord.com/developers/applications)

### 2. Basic Commands
```
/add_product <bol.com_url>     # Start monitoring a product
/dashboard                     # View all monitored products  
/remove_product <product_id>   # Stop monitoring a product
/help                         # Show all commands
```

### 3. Example Usage
```
/add_product https://www.bol.com/nl/nl/p/pokemon-kaarten-booster-pack/9300000123456789/
```

## Commands 📋

| Command | Description |
|---------|-------------|
| `/add_product <url>` | Add a product to monitor |
| `/remove_product <id>` | Remove a product from monitoring |
| `/dashboard` | View all monitored products |
| `/list_products` | List products in current channel |
| `/help` | Show help information |
| `/admin_dashboard` | Admin-only dashboard (if admin) |

## Supported URLs 🔗

- ✅ Individual product pages: `bol.com/nl/nl/p/product-name/123456/`
- ✅ Wishlist pages: `bol.com/nl/nl/account/verlanglijstje/`
- ✅ Search result pages
- ✅ Category pages

## Self-Hosting 🏠

### Prerequisites
- Python 3.10+
- Discord Bot Token
- Git

### Installation
```bash
# Clone the repository
git clone https://github.com/AbdullahP/PokeAlert-Discord-Bot.git
cd PokeAlert-Discord-Bot

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit .env with your Discord token
# DISCORD_TOKEN=your_token_here

# Run the bot
python start_production.py
```

### Deploy on Render
1. Fork this repository
2. Connect to [Render](https://render.com)
3. Create new Web Service from your fork
4. Add `DISCORD_TOKEN` environment variable
5. Deploy!

## Configuration ⚙️

Key environment variables:

```env
DISCORD_TOKEN=your_bot_token
MONITORING_INTERVAL=60
MAX_CONCURRENT_REQUESTS=10
LOG_LEVEL=INFO
```

## Health Monitoring 📊

The bot includes built-in health endpoints:
- `/health` - Basic health check
- `/health/detailed` - Detailed system status
- `/metrics` - Performance metrics
- `/status` - Monitoring status

## Contributing 🤝

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License 📄

This project is licensed under the MIT License.

## Support 💬

Need help? Join our Discord server or create an issue on GitHub.

---

Made with ❤️ for the Pokemon community