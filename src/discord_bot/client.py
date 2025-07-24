"""
Discord bot client implementation.
"""
import logging
from typing import Optional, List, Dict, Callable, Any, Coroutine
import discord
from discord import app_commands
from discord import Interaction, Embed, app_commands, errors

from ..models.interfaces import IDiscordBotClient, IProductManager, IAdminManager
from ..config.config_manager import ConfigManager
from ..models.product_data import ProductConfig, URLType


class CommandError(Exception):
    """Custom exception for command errors."""
    pass


class DiscordBotClient(discord.Client, IDiscordBotClient):
    """Discord bot client implementation."""
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize Discord bot client."""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        super().__init__(intents=intents)
        
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.tree = app_commands.CommandTree(self)
        self._command_handlers: Dict[str, Callable[[Interaction], Coroutine[Any, Any, None]]] = {}
        self._product_manager = None
        self._admin_manager = None
        
    def set_product_manager(self, product_manager: IProductManager) -> None:
        """Set the product manager instance."""
        self._product_manager = product_manager
        
    def set_admin_manager(self, admin_manager: IAdminManager) -> None:
        """Set the admin manager instance."""
        self._admin_manager = admin_manager
    
    async def setup_hook(self) -> None:
        """Set up the bot when it's ready."""
        await self.setup_commands()
        
    async def on_ready(self) -> None:
        """Called when the bot is ready."""
        self.logger.info(f"Bot is ready! Connected to {len(self.guilds)} guilds.")
        if len(self.guilds) == 0:
            self.logger.warning("Bot is not in any guilds. Please check:")
            self.logger.warning("1. Bot token is correct")
            self.logger.warning("2. Bot has been invited to servers")
            self.logger.warning("3. Bot has proper permissions (Send Messages, Use Slash Commands)")
        else:
            for guild in self.guilds:
                self.logger.info(f"Connected to guild: {guild.name} (ID: {guild.id})")
    
    async def setup_commands(self) -> None:
        """Set up Discord slash commands."""
        self.logger.info("Setting up Discord slash commands")
        
        # Create command group for product management
        product_group = app_commands.Group(name="product", description="Manage monitored products")
        
        # Add product command
        @product_group.command(name="add", description="Add a product or wishlist to monitor")
        @app_commands.describe(
            url="The bol.com product or wishlist URL to monitor",
            channel="The channel to send notifications to",
            interval="Monitoring interval in seconds (minimum 30)"
        )
        async def add_product(
            interaction: Interaction, 
            url: str, 
            channel: discord.TextChannel,
            interval: Optional[int] = 60
        ):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # Remove product command
        @product_group.command(name="remove", description="Remove a product from monitoring")
        @app_commands.describe(
            product_id="The ID of the product to remove"
        )
        async def remove_product(interaction: Interaction, product_id: str):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # List products command
        @product_group.command(name="list", description="List all monitored products")
        @app_commands.describe(
            channel="Optional channel to filter products by"
        )
        async def list_products(
            interaction: Interaction, 
            channel: Optional[discord.TextChannel] = None
        ):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # Status command
        @self.tree.command(name="status", description="Show monitoring status and metrics")
        async def status_command(interaction: Interaction):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
            
        # Metrics command
        @self.tree.command(name="metrics", description="Show detailed performance metrics")
        @app_commands.describe(
            hours="Time window in hours (default: 24)"
        )
        async def metrics_command(interaction: Interaction, hours: Optional[int] = 24):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
            
        # Product metrics command
        @self.tree.command(name="product_metrics", description="Show metrics for a specific product")
        @app_commands.describe(
            product_id="The ID of the product to show metrics for",
            hours="Time window in hours (default: 24)"
        )
        async def product_metrics_command(interaction: Interaction, product_id: str, hours: Optional[int] = 24):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # Dashboard command
        @self.tree.command(name="dashboard", description="Show comprehensive monitoring dashboard")
        async def dashboard_command(interaction: Interaction):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # Performance dashboard command
        @self.tree.command(name="performance", description="Show performance metrics dashboard")
        @app_commands.describe(
            hours="Time window in hours (default: 24)"
        )
        async def performance_dashboard_command(interaction: Interaction, hours: Optional[int] = 24):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # Product status command
        @self.tree.command(name="product_status", description="Show detailed status for a specific product")
        @app_commands.describe(
            product_id="The ID of the product to show status for",
            hours="Time window in hours (default: 24)"
        )
        async def product_status_command(interaction: Interaction, product_id: str, hours: Optional[int] = 24):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # Monitoring history command
        @self.tree.command(name="history", description="Show monitoring history for troubleshooting")
        @app_commands.describe(
            hours="Time window in hours (default: 24)"
        )
        async def monitoring_history_command(interaction: Interaction, hours: Optional[int] = 24):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # Real-time status command
        @self.tree.command(name="realtime", description="Show real-time monitoring status")
        async def realtime_status_command(interaction: Interaction):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # Configuration command group
        config_group = app_commands.Group(name="config", description="Manage bot configuration")
        
        # Get config command
        @config_group.command(name="get", description="Get a configuration value")
        @app_commands.describe(
            key="Configuration key (e.g. monitoring.default_interval)"
        )
        async def get_config(interaction: Interaction, key: str):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # Set config command
        @config_group.command(name="set", description="Set a configuration value")
        @app_commands.describe(
            key="Configuration key (e.g. monitoring.default_interval)",
            value="Configuration value"
        )
        async def set_config(interaction: Interaction, key: str, value: str):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # List config command
        @config_group.command(name="list", description="List configuration values")
        @app_commands.describe(
            section="Configuration section (e.g. monitoring, discord)"
        )
        async def list_config(interaction: Interaction, section: str = ""):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # Add the config group to the command tree
        self.tree.add_command(config_group)
        
        # Price threshold management commands
        threshold_group = app_commands.Group(name="threshold", description="Manage price thresholds for third-party seller detection")
        
        # Add threshold command
        @threshold_group.command(name="add", description="Add a new price threshold")
        @app_commands.describe(
            keyword="Product keyword to match (e.g. 'Elite Trainer Box')",
            max_price="Maximum reasonable price in euros"
        )
        async def add_threshold(interaction: Interaction, keyword: str, max_price: float):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # Update threshold command
        @threshold_group.command(name="update", description="Update an existing price threshold")
        @app_commands.describe(
            keyword="Product keyword to update",
            max_price="New maximum reasonable price in euros"
        )
        async def update_threshold(interaction: Interaction, keyword: str, max_price: float):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # Remove threshold command
        @threshold_group.command(name="remove", description="Remove a price threshold")
        @app_commands.describe(
            keyword="Product keyword to remove"
        )
        async def remove_threshold(interaction: Interaction, keyword: str):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # List thresholds command
        @threshold_group.command(name="list", description="List all price thresholds")
        @app_commands.describe(
            search="Optional search term to filter thresholds"
        )
        async def list_thresholds(interaction: Interaction, search: Optional[str] = None):
            await self._validate_admin_command(interaction)
            await self._handle_list_thresholds(interaction)
        
        # Add the threshold group to the command tree
        self.tree.add_command(threshold_group)
        
        # Website interval management commands
        website_group = app_commands.Group(name="website", description="Manage website monitoring intervals")
        
        # List website intervals command
        @website_group.command(name="list", description="List all website monitoring intervals")
        async def list_websites(interaction: Interaction):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # Set website interval command
        @website_group.command(name="set", description="Set monitoring interval for a website domain")
        @app_commands.describe(
            domain="Website domain (e.g. 'bol.com')",
            interval="Monitoring interval in seconds (minimum 1)"
        )
        async def set_website_interval(interaction: Interaction, domain: str, interval: int):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # Get website interval command
        @website_group.command(name="get", description="Get monitoring interval for a website domain")
        @app_commands.describe(
            domain="Website domain (e.g. 'bol.com')"
        )
        async def get_website_interval(interaction: Interaction, domain: str):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # Reset website interval command
        @website_group.command(name="reset", description="Reset website interval to default (10 seconds)")
        @app_commands.describe(
            domain="Website domain to reset"
        )
        async def reset_website_interval(interaction: Interaction, domain: str):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # Add the website group to the command tree
        self.tree.add_command(website_group)
        
        # Update product command
        @product_group.command(name="update", description="Update a monitored product")
        @app_commands.describe(
            product_id="The ID of the product to update",
            channel="The new channel to send notifications to",
            interval="New monitoring interval in seconds (minimum 30)",
            active="Set product active or inactive"
        )
        async def update_product(
            interaction: Interaction,
            product_id: str,
            channel: Optional[discord.TextChannel] = None,
            interval: Optional[int] = None,
            active: Optional[bool] = None
        ):
            await self._validate_admin_command(interaction)
            await self.handle_admin_command(interaction)
        
        # Register command handlers
        self.register_command_handler("add", self._handle_add_product)
        self.register_command_handler("remove", self._handle_remove_product)
        self.register_command_handler("list", self._handle_list_products)
        self.register_command_handler("update", self._handle_update_product)
        self.register_command_handler("status", self._handle_status)
        self.register_command_handler("metrics", self._handle_metrics)
        self.register_command_handler("product_metrics", self._handle_product_metrics)
        self.register_command_handler("dashboard", self._handle_dashboard)
        self.register_command_handler("performance", self._handle_performance_dashboard)
        self.register_command_handler("product_status", self._handle_product_status)
        self.register_command_handler("history", self._handle_monitoring_history)
        self.register_command_handler("realtime", self._handle_realtime_status)
        self.register_command_handler("config_get", self._handle_get_config)
        self.register_command_handler("config_set", self._handle_set_config)
        self.register_command_handler("config_list", self._handle_list_config)
        
        # Register threshold command handlers
        self.register_command_handler("threshold_add", self._handle_threshold_add)
        self.register_command_handler("threshold_update", self._handle_threshold_update)
        self.register_command_handler("threshold_remove", self._handle_threshold_remove)
        self.register_command_handler("threshold_list", self._handle_threshold_list)
        
        # Register website command handlers
        self.register_command_handler("website_list", self._handle_website_list)
        self.register_command_handler("website_set", self._handle_website_set)
        self.register_command_handler("website_get", self._handle_website_get)
        self.register_command_handler("website_reset", self._handle_website_reset)
        
        # Add the product group to the command tree
        self.tree.add_command(product_group)
        
        # Sync commands with Discord
        try:
            self.logger.info("Syncing commands with Discord")
            await self.tree.sync()
            self.logger.info("Commands synced successfully")
        except errors.HTTPException as e:
            self.logger.error(f"Error syncing commands: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error syncing commands: {e}")
    
    async def handle_admin_command(self, interaction: Interaction) -> None:
        """Handle admin commands."""
        try:
            command_name = interaction.command.name
            
            # For group commands, use the subcommand name
            if hasattr(interaction.command, 'parent') and interaction.command.parent:
                if interaction.command.parent.name == "product":
                    command_name = interaction.command.name
                elif interaction.command.parent.name == "config":
                    command_name = f"config_{interaction.command.name}"
                elif interaction.command.parent.name == "threshold":
                    command_name = f"threshold_{interaction.command.name}"
                elif interaction.command.parent.name == "website":
                    command_name = f"website_{interaction.command.name}"
            
            if command_name in self._command_handlers:
                await self._command_handlers[command_name](interaction)
            else:
                await interaction.response.send_message(
                    "Command not implemented yet.", ephemeral=True
                )
        except CommandError as e:
            # Handle expected command errors
            await interaction.response.send_message(
                f"Error: {str(e)}", ephemeral=True
            )
        except errors.DiscordException as e:
            # Handle Discord API errors
            self.logger.error(f"Discord API error in command {interaction.command.name}: {e}")
            await self._handle_discord_error(interaction, e)
        except Exception as e:
            # Handle unexpected errors
            self.logger.exception(f"Unexpected error in command {interaction.command.name}: {e}")
            await interaction.response.send_message(
                "An unexpected error occurred. Please try again later.", ephemeral=True
            )
    
    async def send_notification(self, channel_id: int, embed: Embed) -> bool:
        """Send notification to Discord channel."""
        try:
            channel = self.get_channel(channel_id)
            if not channel:
                self.logger.error(f"Channel not found: {channel_id}")
                return False
            
            await channel.send(embed=embed)
            return True
        except errors.DiscordException as e:
            self.logger.error(f"Discord API error sending notification: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")
            return False
    
    async def _handle_threshold_add(self, interaction: Interaction) -> None:
        """Handle add threshold command."""
        if not self._admin_manager:
            await interaction.response.send_message(
                "Threshold management requires admin manager. Please try again later.",
                ephemeral=True
            )
        else:
            await self._admin_manager.process_threshold_add_command(
                interaction,
                interaction.namespace.keyword,
                interaction.namespace.max_price
            )
    
    async def _handle_threshold_update(self, interaction: Interaction) -> None:
        """Handle update threshold command."""
        if not self._admin_manager:
            await interaction.response.send_message(
                "Threshold management requires admin manager. Please try again later.",
                ephemeral=True
            )
        else:
            await self._admin_manager.process_threshold_update_command(
                interaction,
                interaction.namespace.keyword,
                interaction.namespace.max_price
            )
    
    async def _handle_threshold_remove(self, interaction: Interaction) -> None:
        """Handle remove threshold command."""
        if not self._admin_manager:
            await interaction.response.send_message(
                "Threshold management requires admin manager. Please try again later.",
                ephemeral=True
            )
        else:
            await self._admin_manager.process_threshold_remove_command(
                interaction,
                interaction.namespace.keyword
            )
    
    async def _handle_threshold_list(self, interaction: Interaction) -> None:
        """Handle list thresholds command."""
        if not self._admin_manager:
            await interaction.response.send_message(
                "Threshold management requires admin manager. Please try again later.",
                ephemeral=True
            )
        else:
            # Use admin manager to handle the command
            await self._admin_manager.process_threshold_list_command(
                interaction,
                getattr(interaction.namespace, 'search', None)
            )
    
    async def _handle_list_thresholds(self, interaction: Interaction) -> None:
        """Handle list thresholds command (legacy method name)."""
        await self._handle_threshold_list(interaction)
    
    async def validate_permissions(self, user_id: int, guild_id: int) -> bool:
        """Validate user permissions."""
        try:
            guild = self.get_guild(guild_id)
            if not guild:
                self.logger.warning(f"Guild not found: {guild_id}")
                return False
            
            member = guild.get_member(user_id)
            if not member:
                self.logger.warning(f"Member not found in guild: {user_id}")
                return False
            
            # Check if user has admin role or is server owner
            if member.id == guild.owner_id:
                return True
                
            # Check if user has administrator permission
            if member.guild_permissions.administrator:
                return True
                
            # Check if user has configured admin roles
            admin_roles = self.config_manager.get('discord.admin_roles', ['Admin', 'Moderator'])
            has_admin_role = any(role.name in admin_roles for role in member.roles)
            
            if not has_admin_role:
                self.logger.info(f"User {member.name} ({member.id}) does not have required admin roles")
                
            return has_admin_role
            
        except Exception as e:
            self.logger.error(f"Error validating permissions: {e}")
            return False
    
    def register_command_handler(self, command_name: str, handler_func) -> None:
        """Register a command handler function."""
        self._command_handlers[command_name] = handler_func
        self.logger.info(f"Registered command handler for: {command_name}")
    
    async def _validate_admin_command(self, interaction: Interaction) -> None:
        """Validate if user has permission to use admin commands."""
        if not await self.validate_permissions(interaction.user.id, interaction.guild_id):
            self.logger.warning(
                f"Permission denied: User {interaction.user.name} ({interaction.user.id}) "
                f"attempted to use admin command {interaction.command.name}"
            )
            raise CommandError("You don't have permission to use this command.")
    
    async def _handle_discord_error(self, interaction: Interaction, error: errors.DiscordException) -> None:
        """Handle Discord API errors."""
        try:
            if isinstance(error, errors.Forbidden):
                await interaction.response.send_message(
                    "I don't have permission to perform this action.", ephemeral=True
                )
            elif isinstance(error, errors.NotFound):
                await interaction.response.send_message(
                    "The requested resource was not found.", ephemeral=True
                )
            elif isinstance(error, errors.HTTPException):
                if error.status == 429:  # Rate limited
                    await interaction.response.send_message(
                        "Rate limited by Discord. Please try again later.", ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"Discord API error: {error.status} {error.text}", ephemeral=True
                    )
            else:
                await interaction.response.send_message(
                    "An error occurred while communicating with Discord.", ephemeral=True
                )
        except errors.InteractionResponded:
            # Interaction was already responded to
            try:
                await interaction.followup.send(
                    "An error occurred while processing your command.", ephemeral=True
                )
            except:
                pass
    
    # Command handlers
    async def _handle_add_product(self, interaction: Interaction) -> None:
        """Handle add product command."""
        if not self._admin_manager:
            if not self._product_manager:
                raise CommandError("Product manager not initialized.")
            
            # Fallback to direct product manager if admin manager is not available
            # Defer the response to allow for longer processing time
            await interaction.response.defer(ephemeral=True)
            
            url = interaction.namespace.url
            channel = interaction.namespace.channel
            interval = interaction.namespace.interval or 60
            
            # Validate URL
            if not self._product_manager.validate_url(url):
                await interaction.followup.send(
                    "Invalid bol.com URL. Please provide a valid product or wishlist URL.", 
                    ephemeral=True
                )
                return
            
            # Validate interval
            if interval < 30:
                interval = 30
                await interaction.followup.send(
                    "Monitoring interval set to minimum value (30 seconds).",
                    ephemeral=True
                )
            
            # Add product
            product_id = await self._product_manager.add_product(
                url=url,
                channel_id=channel.id,
                guild_id=interaction.guild_id,
                monitoring_interval=interval
            )
            
            if product_id:
                # Send confirmation embed with product details
                await self._send_product_added_confirmation(interaction, product_id, url, channel)
            else:
                await interaction.followup.send(
                    "Failed to add product. Please check the URL and try again.",
                    ephemeral=True
                )
        else:
            # Use admin manager to handle the command
            await self._admin_manager.process_add_product_command(interaction)
    
    async def _handle_remove_product(self, interaction: Interaction) -> None:
        """Handle remove product command."""
        if not self._admin_manager:
            if not self._product_manager:
                raise CommandError("Product manager not initialized.")
            
            # Fallback to direct product manager if admin manager is not available
            await interaction.response.defer(ephemeral=True)
            
            product_id = interaction.namespace.product_id
            
            # Get product config to verify it exists and belongs to this guild
            product_config = await self._product_manager.get_product_config(product_id)
            if not product_config or product_config.guild_id != interaction.guild_id:
                await interaction.followup.send(
                    "Product not found. Please check the product ID and try again.",
                    ephemeral=True
                )
                return
            
            # Remove product
            success = await self._product_manager.remove_product(product_id)
            
            if success:
                await interaction.followup.send(
                    f"Product removed successfully: `{product_id}`",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "Failed to remove product. Please try again.",
                    ephemeral=True
                )
        else:
            # Use admin manager to handle the command
            await self._admin_manager.process_remove_product_command(interaction)
    
    async def _handle_list_products(self, interaction: Interaction) -> None:
        """Handle list products command."""
        if not self._admin_manager:
            if not self._product_manager:
                raise CommandError("Product manager not initialized.")
            
            # Fallback to direct product manager if admin manager is not available
            await interaction.response.defer(ephemeral=True)
            
            channel = interaction.namespace.channel
            
            if channel:
                products = await self._product_manager.get_products_by_channel(channel.id)
            else:
                products = await self._product_manager.get_products_by_guild(interaction.guild_id)
            
            if not products:
                await interaction.followup.send(
                    "No products are being monitored." + 
                    (f" in {channel.mention}" if channel else ""),
                    ephemeral=True
                )
                return
            
            # Create embed with product list
            embed = discord.Embed(
                title="Monitored Products",
                description=f"Total: {len(products)} products" + 
                           (f" in {channel.mention}" if channel else ""),
                color=0x00ff00
            )
            
            for i, product in enumerate(products[:10], 1):  # Limit to 10 products
                channel_mention = f"<#{product.channel_id}>"
                status = "Active" if product.is_active else "Inactive"
                
                # Truncate URL if too long for better display
                display_url = product.url
                if len(display_url) > 80:
                    display_url = display_url[:77] + "..."
                
                embed.add_field(
                    name=f"{i}. Product ID: {product.product_id}",
                    value=f"**URL:** {display_url}\n"
                          f"**Channel:** {channel_mention}\n"
                          f"**Status:** {status}",
                    inline=False
                )
            
            if len(products) > 10:
                embed.set_footer(text=f"Showing 10 of {len(products)} products")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            # Use admin manager to handle the command
            await self._admin_manager.process_list_products_command(interaction)
    
    async def _handle_status(self, interaction: Interaction) -> None:
        """Handle status command."""
        if not self._admin_manager:
            if not self._product_manager:
                raise CommandError("Product manager not initialized.")
            
            # Fallback to direct product manager if admin manager is not available
            await interaction.response.defer(ephemeral=True)
            
            # Get dashboard data
            dashboard_data = await self._product_manager.get_dashboard_data(interaction.guild_id)
            
            # Create status embed
            embed = discord.Embed(
                title="Monitoring Status",
                description="Current system status and metrics",
                color=0x00ff00
            )
            
            # Add summary fields
            embed.add_field(
                name="Summary",
                value=f"**Total Products:** {dashboard_data.total_products}\n"
                      f"**Active Products:** {dashboard_data.active_products}\n"
                      f"**Checks Today:** {dashboard_data.total_checks_today}\n"
                      f"**Success Rate:** {dashboard_data.success_rate:.1f}%",
                inline=False
            )
            
            # Add recent stock changes if any
            if dashboard_data.recent_stock_changes:
                changes_text = "\n".join([
                    f"• {change.current_status} - Product ID: `{change.product_id}`"
                    for change in dashboard_data.recent_stock_changes[:5]
                ])
                embed.add_field(
                    name="Recent Stock Changes",
                    value=changes_text,
                    inline=False
                )
            
            # Add error summary if any
            if dashboard_data.error_summary:
                errors_text = "\n".join([
                    f"• {error_type}: {count} occurrences"
                    for error_type, count in dashboard_data.error_summary.items()
                ])
                embed.add_field(
                    name="Error Summary",
                    value=errors_text or "No errors",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            # Use admin manager to handle the command
            await self._admin_manager.process_status_command(interaction)
    
    async def _handle_metrics(self, interaction: Interaction) -> None:
        """Handle metrics command."""
        if not self._admin_manager:
            await interaction.response.send_message(
                "Metrics command requires admin manager. Please try again later.",
                ephemeral=True
            )
        else:
            # Use admin manager to handle the command
            await self._admin_manager.process_metrics_command(interaction)
    
    async def _handle_product_metrics(self, interaction: Interaction) -> None:
        """Handle product metrics command."""
        if not self._admin_manager:
            await interaction.response.send_message(
                "Product metrics command requires admin manager. Please try again later.",
                ephemeral=True
            )
        else:
            # Use admin manager to handle the command
            await self._admin_manager.process_product_metrics_command(interaction)
    
    async def _handle_dashboard(self, interaction: Interaction) -> None:
        """Handle dashboard command."""
        if not self._admin_manager:
            await interaction.response.send_message(
                "Dashboard command requires admin manager. Please try again later.",
                ephemeral=True
            )
        else:
            # Use admin manager to handle the command
            await self._admin_manager.process_dashboard_command(interaction)
    
    async def _handle_performance_dashboard(self, interaction: Interaction) -> None:
        """Handle performance dashboard command."""
        if not self._admin_manager:
            await interaction.response.send_message(
                "Performance dashboard command requires admin manager. Please try again later.",
                ephemeral=True
            )
        else:
            # Use admin manager to handle the command
            await self._admin_manager.process_performance_dashboard_command(interaction)
    
    async def _handle_product_status(self, interaction: Interaction) -> None:
        """Handle product status command."""
        if not self._admin_manager:
            await interaction.response.send_message(
                "Product status command requires admin manager. Please try again later.",
                ephemeral=True
            )
        else:
            # Use admin manager to handle the command
            await self._admin_manager.process_product_status_command(interaction)
    
    async def _handle_monitoring_history(self, interaction: Interaction) -> None:
        """Handle monitoring history command."""
        if not self._admin_manager:
            await interaction.response.send_message(
                "Monitoring history command requires admin manager. Please try again later.",
                ephemeral=True
            )
        else:
            # Use admin manager to handle the command
            await self._admin_manager.process_monitoring_history_command(interaction)
    
    async def _handle_realtime_status(self, interaction: Interaction) -> None:
        """Handle real-time status command."""
        if not self._admin_manager:
            await interaction.response.send_message(
                "Real-time status command requires admin manager. Please try again later.",
                ephemeral=True
            )
        else:
            # Use admin manager to handle the command
            await self._admin_manager.process_realtime_status_command(interaction)
            
    async def _handle_update_product(self, interaction: Interaction) -> None:
        """Handle update product command."""
        if not self._admin_manager:
            if not self._product_manager:
                raise CommandError("Product manager not initialized.")
            
            # Fallback to direct product manager if admin manager is not available
            await interaction.response.defer(ephemeral=True)
            
            # Extract command parameters
            product_id = interaction.namespace.product_id
            channel = getattr(interaction.namespace, 'channel', None)
            interval = getattr(interaction.namespace, 'interval', None)
            active = getattr(interaction.namespace, 'active', None)
            
            # Get product config
            product_config = await self._product_manager.get_product_config(product_id)
            if not product_config or product_config.guild_id != interaction.guild_id:
                await interaction.followup.send(
                    "Product not found. Please check the product ID and try again.",
                    ephemeral=True
                )
                return
            
            # Update channel if provided
            if channel:
                success = await self._product_manager.update_channel_assignment(product_id, channel.id)
                if not success:
                    await interaction.followup.send(
                        "Failed to update channel assignment.",
                        ephemeral=True
                    )
                    return
            
            # Update interval if provided
            if interval:
                min_interval = self.config_manager.get('monitoring.min_interval', 30)
                if interval < min_interval:
                    interval = min_interval
                    await interaction.followup.send(
                        f"Monitoring interval set to minimum value ({min_interval} seconds).",
                        ephemeral=True
                    )
                
                product_config.monitoring_interval = interval
                await self._product_manager.update_product(product_id, product_config)
            
            # Update active status if provided
            if active is not None:
                await self._product_manager.set_product_active(product_id, active)
            
            # Get updated product config
            updated_config = await self._product_manager.get_product_config(product_id)
            
            # Create embed with updated product details
            embed = discord.Embed(
                title="Product Updated",
                description=f"Product ID: `{product_id}`",
                color=0x00ff00
            )
            
            channel_mention = f"<#{updated_config.channel_id}>"
            url_type = "Wishlist" if updated_config.url_type == URLType.WISHLIST.value else "Product"
            status = "Active" if updated_config.is_active else "Inactive"
            
            embed.add_field(
                name="Details",
                value=f"**URL Type:** {url_type}\n"
                      f"**Channel:** {channel_mention}\n"
                      f"**Status:** {status}\n"
                      f"**Interval:** {updated_config.monitoring_interval}s",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            # Use admin manager to handle the command
            await self._admin_manager.process_update_product_command(interaction)
    
    async def _handle_get_config(self, interaction: Interaction) -> None:
        """Handle get config command."""
        if not self._admin_manager:
            if not self.config_manager:
                raise CommandError("Config manager not initialized.")
            
            # Fallback to direct config manager if admin manager is not available
            await interaction.response.defer(ephemeral=True)
            
            # Get configuration value
            key = interaction.namespace.key
            value = self.config_manager.get(key, 'Not set')
            
            await interaction.followup.send(
                f"Configuration `{key}`: `{value}`",
                ephemeral=True
            )
        else:
            # Use admin manager to handle the command
            await self._admin_manager.process_config_command(interaction)
    
    async def _handle_set_config(self, interaction: Interaction) -> None:
        """Handle set config command."""
        if not self._admin_manager:
            if not self.config_manager:
                raise CommandError("Config manager not initialized.")
            
            # Fallback to direct config manager if admin manager is not available
            await interaction.response.defer(ephemeral=True)
            
            # Set configuration value
            key = interaction.namespace.key
            value = interaction.namespace.value
            
            # Convert value to appropriate type
            if value.lower() in ('true', 'false'):
                value = value.lower() == 'true'
            elif value.isdigit():
                value = int(value)
            elif value.replace('.', '').isdigit() and value.count('.') == 1:
                value = float(value)
            
            self.config_manager.set(key, value)
            
            await interaction.followup.send(
                f"Configuration `{key}` set to `{value}`",
                ephemeral=True
            )
        else:
            # Use admin manager to handle the command
            await self._admin_manager.process_config_command(interaction)
    
    async def _handle_list_config(self, interaction: Interaction) -> None:
        """Handle list config command."""
        if not self._admin_manager:
            if not self.config_manager:
                raise CommandError("Config manager not initialized.")
            
            # Fallback to direct config manager if admin manager is not available
            await interaction.response.defer(ephemeral=True)
            
            # List configuration sections
            section = interaction.namespace.section
            config_data = self.config_manager.get(section, {})
            
            if not config_data:
                await interaction.followup.send(
                    f"No configuration found for section `{section}`",
                    ephemeral=True
                )
                return
            
            # Create embed with configuration data
            embed = discord.Embed(
                title=f"Configuration: {section}",
                color=0x00ff00
            )
            
            # Add configuration values
            if isinstance(config_data, dict):
                for key, value in config_data.items():
                    if isinstance(value, dict):
                        # Summarize nested dictionaries
                        embed.add_field(
                            name=key,
                            value=f"*{len(value)} settings*",
                            inline=True
                        )
                    else:
                        embed.add_field(
                            name=key,
                            value=f"`{value}`",
                            inline=True
                        )
            else:
                embed.add_field(
                    name=section,
                    value=f"`{config_data}`",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            # Use admin manager to handle the command
            await self._admin_manager.process_config_command(interaction) 
   
    async def _handle_website_list(self, interaction: Interaction) -> None:
        """Handle list website intervals command."""
        if not self._admin_manager:
            await interaction.response.send_message(
                "Website management requires admin manager. Please try again later.",
                ephemeral=True
            )
        else:
            await self._admin_manager.process_website_list_command(interaction)
    
    async def _handle_website_set(self, interaction: Interaction) -> None:
        """Handle set website interval command."""
        if not self._admin_manager:
            await interaction.response.send_message(
                "Website management requires admin manager. Please try again later.",
                ephemeral=True
            )
        else:
            await self._admin_manager.process_website_set_command(
                interaction,
                interaction.namespace.domain,
                interaction.namespace.interval
            )
    
    async def _handle_website_get(self, interaction: Interaction) -> None:
        """Handle get website interval command."""
        if not self._admin_manager:
            await interaction.response.send_message(
                "Website management requires admin manager. Please try again later.",
                ephemeral=True
            )
        else:
            await self._admin_manager.process_website_get_command(
                interaction,
                interaction.namespace.domain
            )
    
    async def _handle_website_reset(self, interaction: Interaction) -> None:
        """Handle reset website interval command."""
        if not self._admin_manager:
            await interaction.response.send_message(
                "Website management requires admin manager. Please try again later.",
                ephemeral=True
            )
        else:
            await self._admin_manager.process_website_reset_command(
                interaction,
                interaction.namespace.domain
            )
    
    async def _send_product_added_confirmation(self, interaction: Interaction, product_id: str, url: str, channel) -> None:
        """
        Send a confirmation embed showing the added product details and current stock status.
        
        Args:
            interaction: Discord interaction object
            product_id: The ID of the added product
            url: The product URL
            channel: The Discord channel where notifications will be sent
        """
        try:
            # Get the monitoring engine to fetch current product data
            from ..services.monitoring_engine import MonitoringEngine
            from ..models.product_data import ProductConfig, URLType
            from datetime import datetime
            
            # Create a temporary product config to fetch data
            temp_config = ProductConfig(
                product_id=product_id,
                url=url,
                url_type=URLType.WISHLIST.value if "verlanglijstje" in url or "wishlist" in url else URLType.PRODUCT.value,
                channel_id=channel.id,
                guild_id=interaction.guild_id,
                is_active=True,
                monitoring_interval=60,
                role_mentions=[],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Initialize monitoring engine
            monitoring_engine = MonitoringEngine(self._config_manager)
            
            # Fetch current product data
            if URLType.is_wishlist(url):
                products = await monitoring_engine.monitor_wishlist(url)
                if products:
                    # For wishlist, show summary
                    in_stock_count = sum(1 for p in products if p.stock_status == "In Stock")
                    out_of_stock_count = len(products) - in_stock_count
                    
                    embed = discord.Embed(
                        title="✅ Wishlist Added Successfully!",
                        description=f"Monitoring has started for this wishlist",
                        color=0x00ff00,
                        timestamp=datetime.utcnow()
                    )
                    
                    # Truncate URL for display
                    display_url = url if len(url) <= 80 else url[:77] + "..."
                    
                    embed.add_field(
                        name="📋 Wishlist Details",
                        value=f"**URL:** {display_url}\n"
                              f"**Product ID:** `{product_id}`\n"
                              f"**Total Products:** {len(products)}\n"
                              f"**In Stock:** {in_stock_count}\n"
                              f"**Out of Stock:** {out_of_stock_count}",
                        inline=False
                    )
                    
                    embed.add_field(
                        name="🔔 Notifications",
                        value=f"Will be sent to {channel.mention}\n"
                              f"Only when products come **IN STOCK**",
                        inline=False
                    )
                    
                    if in_stock_count > 0:
                        embed.add_field(
                            name="📦 Currently In Stock",
                            value=f"{in_stock_count} product(s) are currently available",
                            inline=False
                        )
                else:
                    # Wishlist couldn't be parsed
                    embed = discord.Embed(
                        title="⚠️ Wishlist Added (Parsing Issue)",
                        description=f"Wishlist was added but couldn't fetch current status",
                        color=0xffaa00,
                        timestamp=datetime.utcnow()
                    )
                    
                    display_url = url if len(url) <= 80 else url[:77] + "..."
                    embed.add_field(
                        name="📋 Wishlist Details",
                        value=f"**URL:** {display_url}\n"
                              f"**Product ID:** `{product_id}`\n"
                              f"**Status:** Monitoring will retry automatically",
                        inline=False
                    )
            else:
                # Single product
                product = await monitoring_engine.monitor_product(temp_config)
                if product:
                    # Determine color based on stock status
                    if product.stock_status == "In Stock":
                        color = 0x00ff00  # Green
                        status_emoji = "✅"
                    else:
                        color = 0xff0000  # Red
                        status_emoji = "❌"
                    
                    embed = discord.Embed(
                        title=f"{status_emoji} Product Added Successfully!",
                        description=f"Monitoring has started for this product",
                        color=color,
                        timestamp=datetime.utcnow()
                    )
                    
                    embed.add_field(
                        name="📦 Product Details",
                        value=f"**Title:** {product.title}\n"
                              f"**Price:** {product.price}\n"
                              f"**Status:** {product.stock_status}\n"
                              f"**Product ID:** `{product_id}`",
                        inline=False
                    )
                    
                    embed.add_field(
                        name="🔔 Notifications",
                        value=f"Will be sent to {channel.mention}\n"
                              f"When stock status changes to **IN STOCK**",
                        inline=False
                    )
                    
                    # Add product image if available
                    if product.image_url:
                        embed.set_thumbnail(url=product.image_url)
                else:
                    # Product couldn't be parsed
                    embed = discord.Embed(
                        title="⚠️ Product Added (Parsing Issue)",
                        description=f"Product was added but couldn't fetch current status",
                        color=0xffaa00,
                        timestamp=datetime.utcnow()
                    )
                    
                    display_url = url if len(url) <= 80 else url[:77] + "..."
                    embed.add_field(
                        name="📦 Product Details",
                        value=f"**URL:** {display_url}\n"
                              f"**Product ID:** `{product_id}`\n"
                              f"**Status:** Monitoring will retry automatically",
                        inline=False
                    )
            
            embed.set_footer(text="🤖 Pokemon Monitor Bot - Product Added")
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            self.logger.error(f"Error sending product added confirmation: {e}")
            # Fallback to simple text message
            await interaction.followup.send(
                f"✅ Product added successfully! Product ID: `{product_id}`\n"
                f"Monitoring will begin shortly. Notifications will be sent to {channel.mention}.",
                ephemeral=True
            )