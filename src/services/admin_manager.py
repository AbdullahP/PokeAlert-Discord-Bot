"""
Admin management interface for the Pokemon Discord Bot.
Handles permission validation, command processing, and dashboard data.
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

import discord
from discord import Interaction, Embed, app_commands

from ..models.interfaces import IAdminManager, IProductManager, IDiscordBotClient
from ..models.product_data import DashboardData, ProductConfig, URLType
from ..config.config_manager import ConfigManager
from .dashboard_service import DashboardService


class AdminManager(IAdminManager):
    """Admin management implementation with permission validation and command handling."""
    
    def __init__(self, config_manager: ConfigManager, discord_client: IDiscordBotClient, 
                 product_manager: IProductManager, performance_monitor=None):
        """Initialize admin manager with required dependencies."""
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self.discord_client = discord_client
        self.product_manager = product_manager
        self.performance_monitor = performance_monitor
        
        # Initialize dashboard service
        self.dashboard_service = DashboardService(
            config_manager=config_manager,
            product_manager=product_manager,
            performance_monitor=performance_monitor
        )
    
    async def validate_admin_permissions(self, user_id: int, guild_id: int) -> bool:
        """
        Validate if user has admin permissions.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            
        Returns:
            True if user has admin permissions, False otherwise
            
        Requirements: 7.1, 7.2, 7.3
        """
        return await self.discord_client.validate_permissions(user_id, guild_id)
    
    async def process_add_product_command(self, interaction: Interaction) -> None:
        """
        Process add product admin command.
        
        Args:
            interaction: Discord interaction object
            
        Requirements: 2.3, 2.4
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        # Extract command parameters first
        url = interaction.namespace.url
        channel = interaction.namespace.channel
        interval = getattr(interaction.namespace, 'interval', None) or 60  # Default to 60 if None
        
        # Validate URL before deferring
        if not self.product_manager.validate_url(url):
            await interaction.response.send_message(
                "Invalid bol.com URL. Please provide a valid product or wishlist URL.", 
                ephemeral=True
            )
            return
        
        # Defer response to allow for longer processing time
        await interaction.response.defer(ephemeral=True)
        
        # Validate interval
        min_interval = self.config_manager.get('monitoring.min_interval', 30)
        if interval and interval < min_interval:
            interval = min_interval
            await interaction.followup.send(
                f"Monitoring interval set to minimum value ({min_interval} seconds).",
                ephemeral=True
            )
        
        # Add product
        product_id = await self.product_manager.add_product(
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
    
    async def process_remove_product_command(self, interaction: Interaction) -> None:
        """
        Process remove product admin command.
        
        Args:
            interaction: Discord interaction object
            
        Requirements: 2.3, 2.4
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        product_id = interaction.namespace.product_id
        
        # Get product config to verify it exists and belongs to this guild
        product_config = await self.product_manager.get_product_config(product_id)
        if not product_config or product_config.guild_id != interaction.guild_id:
            await interaction.followup.send(
                "Product not found. Please check the product ID and try again.",
                ephemeral=True
            )
            return
        
        # Remove product
        success = await self.product_manager.remove_product(product_id)
        
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
    
    async def process_list_products_command(self, interaction: Interaction) -> None:
        """
        Process list products admin command.
        
        Args:
            interaction: Discord interaction object
            
        Requirements: 5.1, 5.2
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        channel = getattr(interaction.namespace, 'channel', None)
        
        if channel:
            products = await self.product_manager.get_products_by_channel(channel.id)
        else:
            products = await self.product_manager.get_products_by_guild(interaction.guild_id)
        
        if not products:
            await interaction.followup.send(
                "No products are being monitored." + 
                (f" in {channel.mention}" if channel else ""),
                ephemeral=True
            )
            return
        
        # Create embed with product list
        embed = await self._create_product_list_embed(products, channel)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def process_status_command(self, interaction: Interaction) -> None:
        """
        Process status admin command.
        
        Args:
            interaction: Discord interaction object
            
        Requirements: 5.1, 5.2, 5.5
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get dashboard data
        dashboard_data = await self.get_dashboard_data(interaction.guild_id)
        
        # Create status embed
        embed = await self._create_status_embed(dashboard_data)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def process_metrics_command(self, interaction: Interaction) -> None:
        """
        Process metrics admin command.
        
        Args:
            interaction: Discord interaction object
            
        Requirements: 5.3, 5.5, 10.5
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Check if performance monitor is available
        if not self.performance_monitor:
            await interaction.followup.send(
                "Performance monitoring is not available.", ephemeral=True
            )
            return
        
        # Get time window parameter
        hours = getattr(interaction.namespace, 'hours', 24)
        
        # Get performance report
        try:
            report = await self.performance_monitor.get_performance_report(hours)
            
            # Check for errors
            if 'error' in report:
                await interaction.followup.send(
                    f"Error retrieving performance metrics: {report['error']}", ephemeral=True
                )
                return
                
            # Create metrics embeds
            embeds = await self._create_metrics_embeds(report)
            
            # Send embeds (up to 10 per message)
            for i in range(0, len(embeds), 10):
                batch = embeds[i:i+10]
                await interaction.followup.send(embeds=batch, ephemeral=True)
                
        except Exception as e:
            self.logger.error(f"Error processing metrics command: {e}")
            await interaction.followup.send(
                f"An error occurred while retrieving performance metrics: {str(e)}", ephemeral=True
            )
    
    async def process_product_metrics_command(self, interaction: Interaction) -> None:
        """
        Process product metrics admin command.
        
        Args:
            interaction: Discord interaction object
            
        Requirements: 5.3, 5.5, 10.5
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Check if performance monitor is available
        if not self.performance_monitor:
            await interaction.followup.send(
                "Performance monitoring is not available.", ephemeral=True
            )
            return
        
        # Get product ID and time window parameters
        product_id = interaction.namespace.product_id
        hours = getattr(interaction.namespace, 'hours', 24)
        
        # Get product config to verify it exists and belongs to this guild
        product_config = await self.product_manager.get_product_config(product_id)
        if not product_config or product_config.guild_id != interaction.guild_id:
            await interaction.followup.send(
                "Product not found. Please check the product ID and try again.",
                ephemeral=True
            )
            return
        
        # Get monitoring status for the product
        try:
            status = await self.performance_monitor.get_monitoring_status(product_id, hours)
            
            # Create product metrics embed
            embed = discord.Embed(
                title=f"Product Metrics: {product_id}",
                description=f"Performance metrics for the past {hours} hours",
                color=0x00ff00 if status.success_rate >= 90 else 0xffaa00 if status.success_rate >= 70 else 0xff0000
            )
            
            # Add status fields
            embed.add_field(
                name="Monitoring Status",
                value=f"**Active:** {'Yes' if status.is_active else 'No'}\n"
                      f"**Success Rate:** {status.success_rate:.1f}%\n"
                      f"**Error Count:** {status.error_count}\n"
                      f"**Last Check:** {status.last_check.strftime('%Y-%m-%d %H:%M:%S')}",
                inline=False
            )
            
            # Add last error if available
            if status.last_error:
                embed.add_field(
                    name="Last Error",
                    value=f"```{status.last_error[:500]}```",
                    inline=False
                )
            
            # Get detailed metrics
            metrics = await self.performance_monitor.metrics_repo.get_metrics_by_product(product_id, hours)
            
            # Calculate average response time
            if metrics:
                avg_time = sum(m['check_duration_ms'] for m in metrics) / len(metrics)
                embed.add_field(
                    name="Response Time",
                    value=f"**Average:** {avg_time:.2f}ms\n"
                          f"**Checks:** {len(metrics)}",
                    inline=True
                )
            
            # Add timestamp
            embed.set_footer(text=f"Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            self.logger.error(f"Error processing product metrics command: {e}")
            await interaction.followup.send(
                f"An error occurred while retrieving product metrics: {str(e)}", ephemeral=True
            )
    
    async def process_dashboard_command(self, interaction: Interaction) -> None:
        """
        Process dashboard admin command.
        
        Args:
            interaction: Discord interaction object
            
        Requirements: 5.1, 5.2, 5.5
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Create comprehensive status dashboard
            embeds = await self.dashboard_service.create_status_dashboard(interaction.guild_id)
            
            # Send embeds (up to 10 per message)
            for i in range(0, len(embeds), 10):
                batch = embeds[i:i+10]
                if i == 0:
                    await interaction.followup.send(embeds=batch, ephemeral=True)
                else:
                    await interaction.followup.send(embeds=batch, ephemeral=True)
                    
        except Exception as e:
            self.logger.error(f"Error processing dashboard command: {e}")
            await interaction.followup.send(
                f"An error occurred while generating dashboard: {str(e)}", ephemeral=True
            )
    
    async def process_performance_dashboard_command(self, interaction: Interaction) -> None:
        """
        Process performance dashboard admin command.
        
        Args:
            interaction: Discord interaction object
            
        Requirements: 5.3, 5.5
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get time window parameter
        hours = getattr(interaction.namespace, 'hours', 24)
        
        try:
            # Create performance dashboard
            embeds = await self.dashboard_service.create_performance_dashboard(interaction.guild_id, hours)
            
            # Send embeds (up to 10 per message)
            for i in range(0, len(embeds), 10):
                batch = embeds[i:i+10]
                if i == 0:
                    await interaction.followup.send(embeds=batch, ephemeral=True)
                else:
                    await interaction.followup.send(embeds=batch, ephemeral=True)
                    
        except Exception as e:
            self.logger.error(f"Error processing performance dashboard command: {e}")
            await interaction.followup.send(
                f"An error occurred while generating performance dashboard: {str(e)}", ephemeral=True
            )
    
    async def process_product_status_command(self, interaction: Interaction) -> None:
        """
        Process product status admin command.
        
        Args:
            interaction: Discord interaction object
            
        Requirements: 5.1, 5.2
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get parameters
        product_id = interaction.namespace.product_id
        hours = getattr(interaction.namespace, 'hours', 24)
        
        # Verify product belongs to this guild
        product_config = await self.product_manager.get_product_config(product_id)
        if not product_config or product_config.guild_id != interaction.guild_id:
            await interaction.followup.send(
                "Product not found. Please check the product ID and try again.",
                ephemeral=True
            )
            return
        
        try:
            # Create product status embed
            embed = await self.dashboard_service.create_product_status_embed(product_id, hours)
            await interaction.followup.send(embed=embed, ephemeral=True)
                    
        except Exception as e:
            self.logger.error(f"Error processing product status command: {e}")
            await interaction.followup.send(
                f"An error occurred while generating product status: {str(e)}", ephemeral=True
            )
    
    async def process_monitoring_history_command(self, interaction: Interaction) -> None:
        """
        Process monitoring history admin command.
        
        Args:
            interaction: Discord interaction object
            
        Requirements: 5.5
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get time window parameter
        hours = getattr(interaction.namespace, 'hours', 24)
        
        try:
            # Create monitoring history embed
            embed = await self.dashboard_service.create_monitoring_history_embed(interaction.guild_id, hours)
            await interaction.followup.send(embed=embed, ephemeral=True)
                    
        except Exception as e:
            self.logger.error(f"Error processing monitoring history command: {e}")
            await interaction.followup.send(
                f"An error occurred while generating monitoring history: {str(e)}", ephemeral=True
            )
    
    async def process_realtime_status_command(self, interaction: Interaction) -> None:
        """
        Process real-time status admin command.
        
        Args:
            interaction: Discord interaction object
            
        Requirements: 5.1, 5.2
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Create real-time status embed
            embed = await self.dashboard_service.create_real_time_status_embed(interaction.guild_id)
            await interaction.followup.send(embed=embed, ephemeral=True)
                    
        except Exception as e:
            self.logger.error(f"Error processing real-time status command: {e}")
            await interaction.followup.send(
                f"An error occurred while generating real-time status: {str(e)}", ephemeral=True
            )
    
    async def process_config_command(self, interaction: Interaction) -> None:
        """
        Process configuration admin command.
        
        Args:
            interaction: Discord interaction object
            
        Requirements: 2.4
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get subcommand
        subcommand = interaction.data.get('options', [{}])[0].get('name')
        
        if subcommand == 'get':
            # Get configuration value
            key = interaction.namespace.key
            value = self.config_manager.get(key, 'Not set')
            
            await interaction.followup.send(
                f"Configuration `{key}`: `{value}`",
                ephemeral=True
            )
        
        elif subcommand == 'set':
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
        
        elif subcommand == 'list':
            # List configuration sections
            section = getattr(interaction.namespace, 'section', None)
            if section:
                config_data = self.config_manager.get(section, {})
            else:
                # Show all available sections if no section specified
                config_data = self.config_manager._config
            
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
    
    async def process_update_product_command(self, interaction: Interaction) -> None:
        """
        Process update product admin command.
        
        Args:
            interaction: Discord interaction object
            
        Requirements: 2.1, 2.3, 2.4
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Extract command parameters
        product_id = interaction.namespace.product_id
        channel = getattr(interaction.namespace, 'channel', None)
        interval = getattr(interaction.namespace, 'interval', None)
        active = getattr(interaction.namespace, 'active', None)
        
        # Get product config
        product_config = await self.product_manager.get_product_config(product_id)
        if not product_config or product_config.guild_id != interaction.guild_id:
            await interaction.followup.send(
                "Product not found. Please check the product ID and try again.",
                ephemeral=True
            )
            return
        
        # Update channel if provided
        if channel:
            success = await self.product_manager.update_channel_assignment(product_id, channel.id)
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
            await self.product_manager.update_product(product_id, product_config)
        
        # Update active status if provided
        if active is not None:
            await self.product_manager.set_product_active(product_id, active)
        
        # Get updated product config
        updated_config = await self.product_manager.get_product_config(product_id)
        
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
    
    async def get_dashboard_data(self, guild_id: int) -> DashboardData:
        """
        Get dashboard data for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Dashboard data with metrics and recent changes
            
        Requirements: 5.1, 5.2, 5.5
        """
        return await self.product_manager.get_dashboard_data(guild_id)
    
    async def _create_product_list_embed(self, products: List[ProductConfig], 
                                        channel: Optional[discord.TextChannel] = None) -> Embed:
        """Create embed for product list."""
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
        
        return embed
    
    async def _create_status_embed(self, dashboard_data: DashboardData) -> Embed:
        """Create embed for monitoring status."""
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
        
        # Add timestamp
        embed.set_footer(text=f"Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        return embed
    
    async def _create_metrics_embeds(self, report: Dict[str, Any]) -> List[Embed]:
        """Create embeds for performance metrics report."""
        embeds = []
        
        # System metrics overview embed
        system_metrics = report.get('system_metrics', {})
        overview_embed = discord.Embed(
            title="Performance Metrics Overview",
            description=f"Performance metrics for the past {report.get('time_window_hours', 24)} hours",
            color=0x00ff00
        )
        
        # Add system metrics
        success_rate = system_metrics.get('success_rate', 0)
        overview_embed.add_field(
            name="System Metrics",
            value=f"**Success Rate:** {success_rate:.1f}%\n"
                  f"**Avg Response Time:** {system_metrics.get('avg_response_time', 0):.2f}ms\n"
                  f"**Total Checks Today:** {system_metrics.get('total_checks_today', 0)}\n"
                  f"**Uptime:** {timedelta(seconds=int(system_metrics.get('uptime_seconds', 0)))}",
            inline=False
        )
        
        # Add Discord API metrics
        discord_metrics = system_metrics.get('discord_metrics', {})
        if discord_metrics:
            overview_embed.add_field(
                name="Discord API Metrics",
                value=f"**Avg Request Time:** {discord_metrics.get('avg_request_time', 0):.2f}ms\n"
                      f"**Rate Limit Count:** {discord_metrics.get('rate_limit_count', 0)}\n"
                      f"**Error Count:** {sum(discord_metrics.get('error_counts', {}).values())}",
                inline=True
            )
        
        # Add database metrics
        db_metrics = system_metrics.get('database_metrics', {})
        if db_metrics:
            overview_embed.add_field(
                name="Database Metrics",
                value=f"**Avg Operation Time:** {db_metrics.get('avg_operation_time', 0):.2f}ms\n"
                      f"**Operation Count:** {sum(db_metrics.get('operation_counts', {}).values())}\n"
                      f"**Error Count:** {sum(db_metrics.get('error_counts', {}).values())}",
                inline=True
            )
        
        # Add timestamp
        overview_embed.set_footer(text=f"Last updated: {datetime.fromisoformat(report.get('timestamp', datetime.utcnow().isoformat())).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        embeds.append(overview_embed)
        
        # Product metrics embed
        product_metrics = report.get('product_metrics', {})
        if product_metrics:
            product_embed = discord.Embed(
                title="Product Performance Metrics",
                description=f"Top 10 products by check count",
                color=0x00ff00
            )
            
            # Sort products by check count
            sorted_products = sorted(
                product_metrics.items(),
                key=lambda x: x[1].get('total_checks', 0),
                reverse=True
            )[:10]
            
            for product_id, metrics in sorted_products:
                success_rate = metrics.get('success_rate', 0)
                product_embed.add_field(
                    name=f"Product: {product_id}",
                    value=f"**Success Rate:** {success_rate:.1f}%\n"
                          f"**Checks:** {metrics.get('total_checks', 0)}\n"
                          f"**Errors:** {metrics.get('error_count', 0)}\n"
                          f"**Avg Time:** {metrics.get('avg_duration_ms', 0):.2f}ms",
                    inline=True
                )
            
            embeds.append(product_embed)
        
        # Error distribution embed
        error_distribution = report.get('error_distribution', {})
        if error_distribution:
            error_embed = discord.Embed(
                title="Error Distribution",
                description=f"Top errors in the past {report.get('time_window_hours', 24)} hours",
                color=0xffaa00
            )
            
            error_text = "\n".join([
                f"• **{count}x** {error[:100]}{'...' if len(error) > 100 else ''}"
                for error, count in error_distribution.items()
            ])
            
            error_embed.add_field(
                name="Errors",
                value=error_text or "No errors",
                inline=False
            )
            
            embeds.append(error_embed)
        
        # Hourly metrics embed
        hourly_metrics = report.get('hourly_metrics', [])
        if hourly_metrics:
            hourly_embed = discord.Embed(
                title="Hourly Performance Metrics",
                description=f"Performance trends over the past {report.get('time_window_hours', 24)} hours",
                color=0x00ff00
            )
            
            # Format hourly data
            hours_text = ""
            success_rates_text = ""
            durations_text = ""
            
            for i, hour_data in enumerate(hourly_metrics[-12:]):  # Last 12 hours
                hour = datetime.fromisoformat(hour_data['hour']).strftime('%H:%M')
                success_rate = hour_data.get('success_rate', 0)
                avg_duration = hour_data.get('avg_duration_ms', 0)
                
                hours_text += f"{hour}\n"
                success_rates_text += f"{success_rate:.1f}%\n"
                durations_text += f"{avg_duration:.1f}ms\n"
            
            hourly_embed.add_field(name="Hour", value=hours_text or "No data", inline=True)
            hourly_embed.add_field(name="Success Rate", value=success_rates_text or "No data", inline=True)
            hourly_embed.add_field(name="Avg Duration", value=durations_text or "No data", inline=True)
            
            embeds.append(hourly_embed)
        
        return embeds
    
    # Price Threshold Management Commands
    
    async def process_threshold_add_command(self, interaction: Interaction, keyword: str, max_price: float) -> None:
        """
        Process add price threshold admin command.
        
        Args:
            interaction: Discord interaction object
            keyword: Product keyword to match
            max_price: Maximum reasonable price
            
        Requirements: 7.1, 7.2
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            from ..database.price_threshold_repository import PriceThresholdRepository
            threshold_repo = PriceThresholdRepository()
            
            # Check if threshold already exists
            existing = threshold_repo.get_threshold(keyword)
            if existing:
                await interaction.followup.send(
                    f"❌ Price threshold for '{keyword}' already exists (€{existing[1]}). Use `/threshold update` to modify it.",
                    ephemeral=True
                )
                return
            
            # Add the threshold
            success = threshold_repo.add_threshold(keyword, max_price, str(interaction.user))
            
            if success:
                embed = discord.Embed(
                    title="✅ Price Threshold Added",
                    description=f"Successfully added price threshold",
                    color=0x00ff00
                )
                embed.add_field(name="Keyword", value=f"`{keyword}`", inline=True)
                embed.add_field(name="Max Price", value=f"€{max_price}", inline=True)
                embed.add_field(name="Added By", value=interaction.user.mention, inline=True)
                embed.set_footer(text="Products exceeding this price will be marked as third-party sellers")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"❌ Failed to add price threshold for '{keyword}'. Please try again.",
                    ephemeral=True
                )
                
        except Exception as e:
            self.logger.error(f"Error processing threshold add command: {e}")
            await interaction.followup.send(
                f"An error occurred while adding the price threshold: {str(e)}", ephemeral=True
            )
    
    async def process_threshold_update_command(self, interaction: Interaction, keyword: str, max_price: float) -> None:
        """
        Process update price threshold admin command.
        
        Args:
            interaction: Discord interaction object
            keyword: Product keyword to update
            max_price: New maximum reasonable price
            
        Requirements: 7.1, 7.2
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            from ..database.price_threshold_repository import PriceThresholdRepository
            threshold_repo = PriceThresholdRepository()
            
            # Check if threshold exists
            existing = threshold_repo.get_threshold(keyword)
            if not existing:
                await interaction.followup.send(
                    f"❌ Price threshold for '{keyword}' not found. Use `/threshold add` to create it.",
                    ephemeral=True
                )
                return
            
            old_price = existing[1]
            
            # Update the threshold
            success = threshold_repo.update_threshold(keyword, max_price, str(interaction.user))
            
            if success:
                embed = discord.Embed(
                    title="✅ Price Threshold Updated",
                    description=f"Successfully updated price threshold",
                    color=0x00ff00
                )
                embed.add_field(name="Keyword", value=f"`{keyword}`", inline=True)
                embed.add_field(name="Old Price", value=f"€{old_price}", inline=True)
                embed.add_field(name="New Price", value=f"€{max_price}", inline=True)
                embed.add_field(name="Updated By", value=interaction.user.mention, inline=False)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"❌ Failed to update price threshold for '{keyword}'. Please try again.",
                    ephemeral=True
                )
                
        except Exception as e:
            self.logger.error(f"Error processing threshold update command: {e}")
            await interaction.followup.send(
                f"An error occurred while updating the price threshold: {str(e)}", ephemeral=True
            )
    
    async def process_threshold_remove_command(self, interaction: Interaction, keyword: str) -> None:
        """
        Process remove price threshold admin command.
        
        Args:
            interaction: Discord interaction object
            keyword: Product keyword to remove
            
        Requirements: 7.1, 7.2
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            from ..database.price_threshold_repository import PriceThresholdRepository
            threshold_repo = PriceThresholdRepository()
            
            # Check if threshold exists
            existing = threshold_repo.get_threshold(keyword)
            if not existing:
                await interaction.followup.send(
                    f"❌ Price threshold for '{keyword}' not found.",
                    ephemeral=True
                )
                return
            
            old_price = existing[1]
            
            # Remove the threshold
            success = threshold_repo.remove_threshold(keyword)
            
            if success:
                embed = discord.Embed(
                    title="✅ Price Threshold Removed",
                    description=f"Successfully removed price threshold",
                    color=0xff0000
                )
                embed.add_field(name="Keyword", value=f"`{keyword}`", inline=True)
                embed.add_field(name="Price", value=f"€{old_price}", inline=True)
                embed.add_field(name="Removed By", value=interaction.user.mention, inline=True)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"❌ Failed to remove price threshold for '{keyword}'. Please try again.",
                    ephemeral=True
                )
                
        except Exception as e:
            self.logger.error(f"Error processing threshold remove command: {e}")
            await interaction.followup.send(
                f"An error occurred while removing the price threshold: {str(e)}", ephemeral=True
            )
    
    async def process_threshold_list_command(self, interaction: Interaction, search: Optional[str] = None) -> None:
        """
        Process list price thresholds admin command.
        
        Args:
            interaction: Discord interaction object
            search: Optional search term to filter thresholds
            
        Requirements: 7.1, 7.2
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            from ..database.price_threshold_repository import PriceThresholdRepository
            threshold_repo = PriceThresholdRepository()
            
            # Get thresholds
            if search:
                thresholds = threshold_repo.search_thresholds(search)
                title = f"🔍 Price Thresholds (Search: '{search}')"
            else:
                thresholds = threshold_repo.get_all_thresholds()
                title = "📋 All Price Thresholds"
            
            if not thresholds:
                search_text = f" matching '{search}'" if search else ""
                await interaction.followup.send(
                    f"No price thresholds found{search_text}.",
                    ephemeral=True
                )
                return
            
            # Create embed(s) for thresholds
            embeds = []
            items_per_embed = 10
            
            for i in range(0, len(thresholds), items_per_embed):
                batch = thresholds[i:i + items_per_embed]
                
                embed = discord.Embed(
                    title=title if i == 0 else f"{title} (Page {i//items_per_embed + 1})",
                    description=f"Showing {len(batch)} threshold{'s' if len(batch) != 1 else ''}",
                    color=0x0099ff
                )
                
                for keyword, max_price, created_by, created_at in batch:
                    # Format datetime properly
                    date_str = created_at.strftime('%Y-%m-%d') if hasattr(created_at, 'strftime') else str(created_at)[:10]
                    embed.add_field(
                        name=f"`{keyword}`",
                        value=f"**Max Price:** €{max_price}\n**Added by:** {created_by}\n**Date:** {date_str}",
                        inline=True
                    )
                
                if len(thresholds) > items_per_embed:
                    embed.set_footer(text=f"Showing {i+1}-{min(i+len(batch), len(thresholds))} of {len(thresholds)} thresholds")
                
                embeds.append(embed)
            
            # Send embeds
            for embed in embeds:
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            self.logger.error(f"Error processing threshold list command: {e}")
            await interaction.followup.send(
                f"An error occurred while listing price thresholds: {str(e)}", ephemeral=True
            )
    
    # Website Interval Management Commands
    
    async def process_website_list_command(self, interaction: Interaction) -> None:
        """
        Process list website intervals admin command.
        
        Args:
            interaction: Discord interaction object
            
        Requirements: 7.1, 7.2
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            from ..database.website_interval_repository import WebsiteIntervalRepository
            website_repo = WebsiteIntervalRepository()
            
            # Get all website intervals
            intervals = website_repo.get_all_intervals()
            
            # Get unique domains from products to show all monitored websites
            from ..database.connection import db
            cursor = db.execute(
                "SELECT DISTINCT url FROM products WHERE is_active = 1"
            )
            product_urls = [row[0] for row in cursor.fetchall()]
            
            # Extract domains from product URLs
            monitored_domains = set()
            for url in product_urls:
                domain = website_repo.extract_domain(url)
                if domain and domain != "unknown":
                    monitored_domains.add(domain)
            
            # Create embed
            embed = discord.Embed(
                title="🌐 Website Monitoring Intervals",
                description="Monitoring intervals for different website domains",
                color=0x0099ff
            )
            
            if not monitored_domains and not intervals:
                embed.add_field(
                    name="No Websites",
                    value="No websites are currently being monitored.",
                    inline=False
                )
            else:
                # Show all monitored domains with their intervals
                all_domains = monitored_domains.union({interval[0] for interval in intervals})
                
                for domain in sorted(all_domains):
                    stats = website_repo.get_domain_stats(domain)
                    
                    interval_text = f"{stats['interval_seconds']}s"
                    if stats['is_custom']:
                        interval_text += " (custom)"
                        updated_info = f"Set by {stats['created_by']}"
                        if stats['updated_at']:
                            date_str = stats['updated_at'].strftime('%Y-%m-%d') if hasattr(stats['updated_at'], 'strftime') else str(stats['updated_at'])[:10]
                            updated_info += f" on {date_str}"
                    else:
                        interval_text += " (default)"
                        updated_info = "Using default interval"
                    
                    embed.add_field(
                        name=f"📍 {domain}",
                        value=f"**Interval:** {interval_text}\n"
                              f"**Products:** {stats['product_count']}\n"
                              f"**Status:** {updated_info}",
                        inline=True
                    )
            
            embed.set_footer(text="Use /website set to customize intervals • Default: 10s")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            self.logger.error(f"Error processing website list command: {e}")
            await interaction.followup.send(
                f"An error occurred while listing website intervals: {str(e)}", ephemeral=True
            )
    
    async def process_website_set_command(self, interaction: Interaction, domain: str, interval: int) -> None:
        """
        Process set website interval admin command.
        
        Args:
            interaction: Discord interaction object
            domain: Website domain
            interval: Monitoring interval in seconds
            
        Requirements: 7.1, 7.2
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            from ..database.website_interval_repository import WebsiteIntervalRepository
            website_repo = WebsiteIntervalRepository()
            
            # Validate interval
            if interval < 1:
                await interaction.followup.send(
                    "❌ Interval must be at least 1 second.", ephemeral=True
                )
                return
            
            # Clean domain name
            domain = domain.lower().strip()
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Get current stats
            old_stats = website_repo.get_domain_stats(domain)
            old_interval = old_stats['interval_seconds']
            
            # Set the interval
            success = website_repo.set_interval(domain, interval, str(interaction.user))
            
            if success:
                # Get updated stats
                new_stats = website_repo.get_domain_stats(domain)
                
                embed = discord.Embed(
                    title="✅ Website Interval Updated",
                    description=f"Successfully updated monitoring interval for **{domain}**",
                    color=0x00ff00
                )
                
                embed.add_field(name="Domain", value=f"`{domain}`", inline=True)
                embed.add_field(name="Old Interval", value=f"{old_interval}s", inline=True)
                embed.add_field(name="New Interval", value=f"{interval}s", inline=True)
                embed.add_field(name="Products Affected", value=f"{new_stats['product_count']}", inline=True)
                embed.add_field(name="Updated By", value=interaction.user.mention, inline=True)
                embed.add_field(name="⚠️ Note", value="Restart monitoring to apply changes", inline=False)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"❌ Failed to set interval for '{domain}'. Please try again.",
                    ephemeral=True
                )
                
        except Exception as e:
            self.logger.error(f"Error processing website set command: {e}")
            await interaction.followup.send(
                f"An error occurred while setting website interval: {str(e)}", ephemeral=True
            )
    
    async def process_website_get_command(self, interaction: Interaction, domain: str) -> None:
        """
        Process get website interval admin command.
        
        Args:
            interaction: Discord interaction object
            domain: Website domain
            
        Requirements: 7.1, 7.2
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            from ..database.website_interval_repository import WebsiteIntervalRepository
            website_repo = WebsiteIntervalRepository()
            
            # Clean domain name
            domain = domain.lower().strip()
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Get domain stats
            stats = website_repo.get_domain_stats(domain)
            
            embed = discord.Embed(
                title=f"🌐 Website Interval: {domain}",
                color=0x0099ff
            )
            
            interval_text = f"{stats['interval_seconds']} seconds"
            if stats['is_custom']:
                interval_text += " (custom setting)"
            else:
                interval_text += " (default)"
            
            embed.add_field(name="Current Interval", value=interval_text, inline=False)
            embed.add_field(name="Products Monitored", value=f"{stats['product_count']}", inline=True)
            
            if stats['is_custom'] and stats['created_by']:
                embed.add_field(name="Set By", value=stats['created_by'], inline=True)
                if stats['updated_at']:
                    date_str = stats['updated_at'].strftime('%Y-%m-%d %H:%M') if hasattr(stats['updated_at'], 'strftime') else str(stats['updated_at'])
                    embed.add_field(name="Last Updated", value=date_str, inline=True)
            
            embed.set_footer(text="Use /website set to change interval • /website reset to use default")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            self.logger.error(f"Error processing website get command: {e}")
            await interaction.followup.send(
                f"An error occurred while getting website interval: {str(e)}", ephemeral=True
            )
    
    async def process_website_reset_command(self, interaction: Interaction, domain: str) -> None:
        """
        Process reset website interval admin command.
        
        Args:
            interaction: Discord interaction object
            domain: Website domain to reset
            
        Requirements: 7.1, 7.2
        """
        # Validate permissions
        if not await self.validate_admin_permissions(interaction.user.id, interaction.guild_id):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            from ..database.website_interval_repository import WebsiteIntervalRepository
            website_repo = WebsiteIntervalRepository()
            
            # Clean domain name
            domain = domain.lower().strip()
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Get current stats before reset
            old_stats = website_repo.get_domain_stats(domain)
            old_interval = old_stats['interval_seconds']
            was_custom = old_stats['is_custom']
            
            if not was_custom:
                await interaction.followup.send(
                    f"ℹ️ Domain '{domain}' is already using the default interval ({old_interval}s).",
                    ephemeral=True
                )
                return
            
            # Remove custom interval (will use default)
            success = website_repo.remove_interval(domain)
            
            if success:
                # Get new stats
                new_stats = website_repo.get_domain_stats(domain)
                
                embed = discord.Embed(
                    title="✅ Website Interval Reset",
                    description=f"Successfully reset monitoring interval for **{domain}** to default",
                    color=0x00ff00
                )
                
                embed.add_field(name="Domain", value=f"`{domain}`", inline=True)
                embed.add_field(name="Old Interval", value=f"{old_interval}s (custom)", inline=True)
                embed.add_field(name="New Interval", value=f"{new_stats['interval_seconds']}s (default)", inline=True)
                embed.add_field(name="Products Affected", value=f"{new_stats['product_count']}", inline=True)
                embed.add_field(name="Reset By", value=interaction.user.mention, inline=True)
                embed.add_field(name="⚠️ Note", value="Restart monitoring to apply changes", inline=False)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"❌ Failed to reset interval for '{domain}'. Domain may not have a custom interval set.",
                    ephemeral=True
                )
                
        except Exception as e:
            self.logger.error(f"Error processing website reset command: {e}")
            await interaction.followup.send(
                f"An error occurred while resetting website interval: {str(e)}", ephemeral=True
            )