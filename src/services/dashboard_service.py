"""
Dashboard service for monitoring status and metrics display.
Provides comprehensive monitoring dashboard functionality.
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import discord
from discord import Embed

from ..models.interfaces import IProductManager
from ..models.product_data import (
    ProductConfig, DashboardData, StockChange, MonitoringStatus, URLType
)
from ..config.config_manager import ConfigManager


class DashboardService:
    """Service for creating monitoring dashboards and status displays."""
    
    def __init__(self, config_manager, product_manager, performance_monitor=None):
        """Initialize dashboard service."""
        self.config_manager = config_manager
        self.product_manager = product_manager
        self.performance_monitor = performance_monitor
        self.logger = logging.getLogger(__name__)
        
        # Dashboard configuration
        self.max_products_per_embed = self.config_manager.get('dashboard.max_products_per_embed', 10)
        self.max_changes_displayed = self.config_manager.get('dashboard.max_changes_displayed', 5)
        self.max_errors_displayed = self.config_manager.get('dashboard.max_errors_displayed', 5)
        
        # Color scheme
        self.colors = {
            'success': 0x00ff00,  # Green
            'warning': 0xffaa00,  # Orange
            'error': 0xff0000,    # Red
            'info': 0x0099ff,     # Blue
            'neutral': 0x808080   # Gray
        }
    
    async def create_status_dashboard(self, guild_id: int) -> List[Embed]:
        """
        Create comprehensive status dashboard embeds.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            List of Discord embeds for the dashboard
            
        Requirements: 5.1, 5.2
        """
        try:
            embeds = []
            
            # Get dashboard data
            dashboard_data = await self.product_manager.get_dashboard_data(guild_id)
            
            # Create main status embed
            main_embed = await self._create_main_status_embed(dashboard_data)
            embeds.append(main_embed)
            
            # Create products overview embed if there are products
            if dashboard_data.total_products > 0:
                products_embed = await self._create_products_overview_embed(guild_id)
                embeds.append(products_embed)
            
            # Create recent changes embed if there are changes
            if dashboard_data.recent_stock_changes:
                changes_embed = await self._create_recent_changes_embed(dashboard_data.recent_stock_changes)
                embeds.append(changes_embed)
            
            # Create error summary embed if there are errors
            if dashboard_data.error_summary:
                errors_embed = await self._create_error_summary_embed(dashboard_data.error_summary)
                embeds.append(errors_embed)
            
            return embeds
            
        except Exception as e:
            self.logger.error(f"Error creating status dashboard: {e}")
            error_embed = Embed(
                title="Dashboard Error",
                description=f"Failed to generate dashboard: {str(e)}",
                color=self.colors['error']
            )
            return [error_embed]
    
    async def create_performance_dashboard(self, guild_id: int, hours: int = 24) -> List[Embed]:
        """
        Create performance metrics dashboard.
        
        Args:
            guild_id: Discord guild ID
            hours: Time window in hours
            
        Returns:
            List of Discord embeds for performance metrics
            
        Requirements: 5.3, 5.5
        """
        try:
            embeds = []
            
            if not self.performance_monitor:
                error_embed = Embed(
                    title="Performance Dashboard",
                    description="Performance monitoring is not available.",
                    color=self.colors['warning']
                )
                return [error_embed]
            
            # Get performance report
            report = await self.performance_monitor.get_performance_report(hours)
            
            if 'error' in report:
                error_embed = Embed(
                    title="Performance Dashboard Error",
                    description=f"Failed to generate performance report: {report['error']}",
                    color=self.colors['error']
                )
                return [error_embed]
            
            # Create system metrics embed
            system_embed = await self._create_system_metrics_embed(report, hours)
            embeds.append(system_embed)
            
            # Create product performance embed
            if report.get('product_metrics'):
                product_perf_embed = await self._create_product_performance_embed(
                    report['product_metrics'], guild_id, hours
                )
                embeds.append(product_perf_embed)
            
            # Create error distribution embed
            if report.get('error_distribution'):
                error_dist_embed = await self._create_error_distribution_embed(
                    report['error_distribution'], hours
                )
                embeds.append(error_dist_embed)
            
            # Create hourly trends embed
            if report.get('hourly_metrics'):
                trends_embed = await self._create_hourly_trends_embed(
                    report['hourly_metrics'], hours
                )
                embeds.append(trends_embed)
            
            return embeds
            
        except Exception as e:
            self.logger.error(f"Error creating performance dashboard: {e}")
            error_embed = Embed(
                title="Performance Dashboard Error",
                description=f"Failed to generate performance dashboard: {str(e)}",
                color=self.colors['error']
            )
            return [error_embed]
    
    async def create_product_status_embed(self, product_id: str, hours: int = 24) -> Embed:
        """
        Create detailed status embed for a specific product.
        
        Args:
            product_id: Product ID
            hours: Time window in hours
            
        Returns:
            Discord embed with product status
            
        Requirements: 5.1, 5.2
        """
        try:
            # Get product configuration
            product_config = await self.product_manager.get_product_config(product_id)
            if not product_config:
                return Embed(
                    title="Product Not Found",
                    description=f"Product ID `{product_id}` not found.",
                    color=self.colors['error']
                )
            
            # Get monitoring status
            monitoring_status = None
            if self.performance_monitor:
                monitoring_status = await self.performance_monitor.get_monitoring_status(product_id, hours)
            
            # Determine embed color based on status
            if not product_config.is_active:
                color = self.colors['neutral']
            elif monitoring_status and monitoring_status.success_rate >= 90:
                color = self.colors['success']
            elif monitoring_status and monitoring_status.success_rate >= 70:
                color = self.colors['warning']
            else:
                color = self.colors['error']
            
            embed = Embed(
                title=f"Product Status: {product_id}",
                description=f"Detailed status for the past {hours} hours",
                color=color
            )
            
            # Add basic product info
            url_type = "Wishlist" if product_config.url_type == URLType.WISHLIST.value else "Product"
            status = "Active" if product_config.is_active else "Inactive"
            
            embed.add_field(
                name="Product Information",
                value=f"**Type:** {url_type}\n"
                      f"**Status:** {status}\n"
                      f"**Channel:** <#{product_config.channel_id}>\n"
                      f"**Interval:** {product_config.monitoring_interval}s",
                inline=False
            )
            
            # Add monitoring metrics if available
            if monitoring_status:
                embed.add_field(
                    name="Monitoring Metrics",
                    value=f"**Success Rate:** {monitoring_status.success_rate:.1f}%\n"
                          f"**Error Count:** {monitoring_status.error_count}\n"
                          f"**Last Check:** {monitoring_status.last_check.strftime('%Y-%m-%d %H:%M:%S')}",
                    inline=True
                )
                
                # Add last error if available
                if monitoring_status.last_error:
                    error_preview = monitoring_status.last_error[:100] + "..." if len(monitoring_status.last_error) > 100 else monitoring_status.last_error
                    embed.add_field(
                        name="Last Error",
                        value=f"```{error_preview}```",
                        inline=False
                    )
            
            # Add timestamp
            embed.set_footer(text=f"Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            return embed
            
        except Exception as e:
            self.logger.error(f"Error creating product status embed: {e}")
            return Embed(
                title="Error",
                description=f"Failed to create product status: {str(e)}",
                color=self.colors['error']
            )
    
    async def create_monitoring_history_embed(self, guild_id: int, hours: int = 24) -> Embed:
        """
        Create monitoring history embed for troubleshooting.
        
        Args:
            guild_id: Discord guild ID
            hours: Time window in hours
            
        Returns:
            Discord embed with monitoring history
            
        Requirements: 5.5
        """
        try:
            embed = Embed(
                title="Monitoring History",
                description=f"System activity for the past {hours} hours",
                color=self.colors['info']
            )
            
            # Get dashboard data for recent changes
            dashboard_data = await self.product_manager.get_dashboard_data(guild_id)
            
            # Add recent stock changes
            if dashboard_data.recent_stock_changes:
                changes_text = ""
                for change in dashboard_data.recent_stock_changes[:10]:  # Last 10 changes
                    timestamp = change.timestamp.strftime('%H:%M')
                    changes_text += f"• `{timestamp}` - {change.product_id}: {change.previous_status} → {change.current_status}\n"
                
                embed.add_field(
                    name="Recent Stock Changes",
                    value=changes_text or "No recent changes",
                    inline=False
                )
            
            # Add system metrics if performance monitor is available
            if self.performance_monitor:
                system_metrics = await self.performance_monitor.get_system_metrics()
                
                embed.add_field(
                    name="System Activity",
                    value=f"**Total Checks Today:** {system_metrics.get('total_checks_today', 0)}\n"
                          f"**Success Rate:** {system_metrics.get('success_rate', 0):.1f}%\n"
                          f"**Avg Response Time:** {system_metrics.get('avg_response_time', 0):.2f}ms\n"
                          f"**Active Products:** {dashboard_data.active_products}",
                    inline=True
                )
                
                # Add Discord API metrics
                discord_metrics = system_metrics.get('discord_metrics', {})
                if discord_metrics:
                    embed.add_field(
                        name="Discord API",
                        value=f"**Avg Request Time:** {discord_metrics.get('avg_request_time', 0):.2f}ms\n"
                              f"**Rate Limits:** {discord_metrics.get('rate_limit_count', 0)}\n"
                              f"**API Errors:** {sum(discord_metrics.get('error_counts', {}).values())}",
                        inline=True
                    )
            
            # Add error summary
            if dashboard_data.error_summary:
                error_text = ""
                for error_type, count in list(dashboard_data.error_summary.items())[:5]:
                    error_text += f"• {error_type}: {count} occurrences\n"
                
                embed.add_field(
                    name="Error Summary",
                    value=error_text or "No errors",
                    inline=False
                )
            
            embed.set_footer(text=f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            return embed
            
        except Exception as e:
            self.logger.error(f"Error creating monitoring history embed: {e}")
            return Embed(
                title="History Error",
                description=f"Failed to generate monitoring history: {str(e)}",
                color=self.colors['error']
            )
    
    async def create_real_time_status_embed(self, guild_id: int) -> Embed:
        """
        Create real-time monitoring status embed.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Discord embed with real-time status
            
        Requirements: 5.1, 5.2
        """
        try:
            # Get current dashboard data
            dashboard_data = await self.product_manager.get_dashboard_data(guild_id)
            
            # Determine system health
            health_status, health_emoji = self._determine_system_health(dashboard_data)
            
            embed = Embed(
                title=f"{health_emoji} Real-Time Monitoring Status",
                description=f"System Health: **{health_status}**",
                color=self._get_health_color(health_status)
            )
            
            # Add live metrics
            embed.add_field(
                name="📊 Live Metrics",
                value=f"**Active Products:** {dashboard_data.active_products}/{dashboard_data.total_products}\n"
                      f"**Success Rate:** {dashboard_data.success_rate:.1f}%\n"
                      f"**Checks Today:** {dashboard_data.total_checks_today}",
                inline=True
            )
            
            # Add latest activity
            if dashboard_data.recent_stock_changes:
                latest_change = dashboard_data.recent_stock_changes[0]
                time_ago = datetime.utcnow() - latest_change.timestamp
                minutes_ago = int(time_ago.total_seconds() / 60)
                
                activity_text = f"**Latest Change:** {minutes_ago}m ago\n"
                activity_text += f"Product: `{latest_change.product_id}`\n"
                activity_text += f"Status: {latest_change.previous_status} → {latest_change.current_status}"
            else:
                activity_text = "No recent stock changes"
            
            embed.add_field(
                name="🔄 Latest Activity",
                value=activity_text,
                inline=True
            )
            
            # Add performance metrics if available
            if self.performance_monitor:
                system_metrics = await self.performance_monitor.get_system_metrics()
                avg_response = system_metrics.get('avg_response_time', 0)
                
                embed.add_field(
                    name="⚡ Performance",
                    value=f"**Avg Response:** {avg_response:.0f}ms\n"
                          f"**Error Rate:** {100 - dashboard_data.success_rate:.1f}%\n"
                          f"**Uptime:** {self._format_uptime(system_metrics.get('uptime_seconds', 0))}",
                    inline=True
                )
            
            # Add error summary if there are errors
            if dashboard_data.error_summary:
                error_count = sum(dashboard_data.error_summary.values())
                top_error = max(dashboard_data.error_summary.items(), key=lambda x: x[1])
                
                embed.add_field(
                    name="⚠️ Recent Issues",
                    value=f"**Total Errors:** {error_count}\n"
                          f"**Most Common:** {top_error[0]} ({top_error[1]}x)",
                    inline=False
                )
            
            # Add timestamp
            embed.set_footer(text=f"🕒 Last updated: {datetime.utcnow().strftime('%H:%M:%S UTC')}")
            
            return embed
            
        except Exception as e:
            self.logger.error(f"Error creating real-time status embed: {e}")
            return Embed(
                title="Real-Time Status Error",
                description=f"Failed to generate real-time status: {str(e)}",
                color=self.colors['error']
            )
    
    # Helper methods for embed creation
    
    async def _create_main_status_embed(self, dashboard_data: DashboardData) -> Embed:
        """Create main status overview embed."""
        embed = Embed(
            title="📊 Monitoring Dashboard",
            description="System overview and current status",
            color=self._get_status_color(dashboard_data.success_rate)
        )
        
        embed.add_field(
            name="System Overview",
            value=f"**Total Products:** {dashboard_data.total_products}\n"
                  f"**Active Products:** {dashboard_data.active_products}\n"
                  f"**Checks Today:** {dashboard_data.total_checks_today}\n"
                  f"**Success Rate:** {dashboard_data.success_rate:.1f}%",
            inline=False
        )
        
        # Add status indicator
        if dashboard_data.success_rate >= 95:
            status_text = "🟢 Excellent"
        elif dashboard_data.success_rate >= 85:
            status_text = "🟡 Good"
        elif dashboard_data.success_rate >= 70:
            status_text = "🟠 Fair"
        else:
            status_text = "🔴 Poor"
        
        embed.add_field(
            name="System Status",
            value=status_text,
            inline=True
        )
        
        embed.set_footer(text=f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        return embed
    
    async def _create_products_overview_embed(self, guild_id: int) -> Embed:
        """Create products overview embed."""
        embed = Embed(
            title="📦 Products Overview",
            description="Currently monitored products",
            color=self.colors['info']
        )
        
        # Get products for this guild
        products = await self.product_manager.get_products_by_guild(guild_id)
        
        # Group products by channel
        channel_groups = {}
        for product in products:
            channel_id = product.channel_id
            if channel_id not in channel_groups:
                channel_groups[channel_id] = []
            channel_groups[channel_id].append(product)
        
        # Add field for each channel
        for channel_id, channel_products in list(channel_groups.items())[:5]:  # Limit to 5 channels
            active_count = sum(1 for p in channel_products if p.is_active)
            
            product_list = []
            for product in channel_products[:3]:  # Show first 3 products
                status_emoji = "🟢" if product.is_active else "⚫"
                url_type = "W" if product.url_type == URLType.WISHLIST.value else "P"
                product_list.append(f"{status_emoji} `{product.product_id}` ({url_type})")
            
            if len(channel_products) > 3:
                product_list.append(f"... and {len(channel_products) - 3} more")
            
            embed.add_field(
                name=f"<#{channel_id}> ({active_count}/{len(channel_products)} active)",
                value="\n".join(product_list) or "No products",
                inline=True
            )
        
        return embed
    
    async def _create_recent_changes_embed(self, stock_changes: List[StockChange]) -> Embed:
        """Create recent stock changes embed."""
        embed = Embed(
            title="📈 Recent Stock Changes",
            description="Latest product status updates",
            color=self.colors['info']
        )
        
        changes_text = ""
        displayed_changes = 0
        for change in stock_changes:
            if displayed_changes >= self.max_changes_displayed:
                break
                
            time_ago = datetime.utcnow() - change.timestamp
            minutes_ago = int(time_ago.total_seconds() / 60)
            
            # Status change emoji
            if "In Stock" in change.current_status:
                emoji = "🟢"
            elif "Out of Stock" in change.current_status:
                emoji = "🔴"
            else:
                emoji = "🟡"
            
            changes_text += f"{emoji} **{change.product_id}** ({minutes_ago}m ago)\n"
            changes_text += f"   {change.previous_status} → {change.current_status}\n"
            displayed_changes += 1
            
            # Add separator except for last item
            if displayed_changes < self.max_changes_displayed and displayed_changes < len(stock_changes):
                changes_text += "\n"
        
        embed.add_field(
            name="Stock Changes",
            value=changes_text or "No recent changes",
            inline=False
        )
        
        return embed
    
    async def _create_error_summary_embed(self, error_summary: Dict[str, int]) -> Embed:
        """Create error summary embed."""
        embed = Embed(
            title="⚠️ Error Summary",
            description="Recent system errors",
            color=self.colors['warning']
        )
        
        error_text = ""
        total_errors = sum(error_summary.values())
        
        for error_type, count in list(error_summary.items())[:self.max_errors_displayed]:
            percentage = (count / total_errors) * 100 if total_errors > 0 else 0
            error_text += f"• **{error_type}:** {count} ({percentage:.1f}%)\n"
        
        embed.add_field(
            name=f"Error Distribution (Total: {total_errors})",
            value=error_text or "No errors",
            inline=False
        )
        
        return embed
    
    async def _create_system_metrics_embed(self, report: Dict[str, Any], hours: int) -> Embed:
        """Create system performance metrics embed."""
        system_metrics = report.get('system_metrics', {})
        
        embed = Embed(
            title="🖥️ System Performance Metrics",
            description=f"Performance data for the past {hours} hours",
            color=self.colors['info']
        )
        
        # Overall metrics
        embed.add_field(
            name="Overall Performance",
            value=f"**Success Rate:** {system_metrics.get('success_rate', 0):.1f}%\n"
                  f"**Avg Response Time:** {system_metrics.get('avg_response_time', 0):.2f}ms\n"
                  f"**Total Checks:** {system_metrics.get('success_count', 0) + system_metrics.get('error_count', 0)}\n"
                  f"**Error Count:** {system_metrics.get('error_count', 0)}",
            inline=True
        )
        
        # Database metrics
        db_metrics = system_metrics.get('database_metrics', {})
        if db_metrics:
            embed.add_field(
                name="Database Performance",
                value=f"**Avg Operation Time:** {db_metrics.get('avg_operation_time', 0):.2f}ms\n"
                      f"**Query Count:** {db_metrics.get('operation_counts', {}).get('query', 0)}\n"
                      f"**Insert Count:** {db_metrics.get('operation_counts', {}).get('insert', 0)}\n"
                      f"**DB Errors:** {sum(db_metrics.get('error_counts', {}).values())}",
                inline=True
            )
        
        # Discord API metrics
        discord_metrics = system_metrics.get('discord_metrics', {})
        if discord_metrics:
            embed.add_field(
                name="Discord API",
                value=f"**Avg Request Time:** {discord_metrics.get('avg_request_time', 0):.2f}ms\n"
                      f"**Rate Limits:** {discord_metrics.get('rate_limit_count', 0)}\n"
                      f"**API Errors:** {sum(discord_metrics.get('error_counts', {}).values())}",
                inline=True
            )
        
        return embed
    
    async def _create_product_performance_embed(self, product_metrics: Dict[str, Any], guild_id: int, hours: int) -> Embed:
        """Create product performance metrics embed."""
        embed = Embed(
            title="📦 Product Performance Metrics",
            description=f"Individual product performance for the past {hours} hours",
            color=self.colors['info']
        )
        
        # Get products for this guild to filter metrics
        products = await self.product_manager.get_products_by_guild(guild_id)
        guild_product_ids = {p.product_id for p in products}
        
        # Filter metrics to only include products from this guild
        filtered_metrics = {
            pid: metrics for pid, metrics in product_metrics.items() 
            if pid in guild_product_ids
        }
        
        if not filtered_metrics:
            embed.add_field(
                name="No Data",
                value="No performance data available for products in this server.",
                inline=False
            )
            return embed
        
        # Sort by success rate (best first)
        sorted_products = sorted(
            filtered_metrics.items(),
            key=lambda x: x[1].get('success_rate', 0),
            reverse=True
        )
        
        # Show top performing products
        for i, (product_id, metrics) in enumerate(sorted_products[:5]):
            success_rate = metrics.get('success_rate', 0)
            avg_duration = metrics.get('avg_duration_ms', 0)
            total_checks = metrics.get('total_checks', 0)
            error_count = metrics.get('error_count', 0)
            
            # Status emoji based on success rate
            if success_rate >= 95:
                emoji = "🟢"
            elif success_rate >= 85:
                emoji = "🟡"
            else:
                emoji = "🔴"
            
            embed.add_field(
                name=f"{emoji} {product_id}",
                value=f"**Success Rate:** {success_rate:.1f}%\n"
                      f"**Avg Time:** {avg_duration:.0f}ms\n"
                      f"**Checks:** {total_checks}\n"
                      f"**Errors:** {error_count}",
                inline=True
            )
        
        if len(sorted_products) > 5:
            embed.set_footer(text=f"Showing top 5 of {len(sorted_products)} products")
        
        return embed
    
    async def _create_error_distribution_embed(self, error_distribution: Dict[str, int], hours: int) -> Embed:
        """Create error distribution embed."""
        embed = Embed(
            title="🚨 Error Distribution",
            description=f"Error breakdown for the past {hours} hours",
            color=self.colors['warning']
        )
        
        total_errors = sum(error_distribution.values())
        
        if total_errors == 0:
            embed.add_field(
                name="No Errors",
                value="No errors recorded in the specified time period.",
                inline=False
            )
            return embed
        
        # Sort errors by frequency
        sorted_errors = sorted(error_distribution.items(), key=lambda x: x[1], reverse=True)
        
        error_text = ""
        for error_type, count in sorted_errors[:10]:  # Top 10 errors
            percentage = (count / total_errors) * 100
            bar_length = int(percentage / 10)  # Simple bar chart
            bar = "█" * bar_length + "░" * (10 - bar_length)
            
            error_text += f"**{error_type}**\n"
            error_text += f"`{bar}` {count} ({percentage:.1f}%)\n\n"
        
        embed.add_field(
            name=f"Error Types (Total: {total_errors})",
            value=error_text,
            inline=False
        )
        
        return embed
    
    async def _create_hourly_trends_embed(self, hourly_metrics: List[Dict[str, Any]], hours: int) -> Embed:
        """Create hourly performance trends embed."""
        embed = Embed(
            title="📊 Hourly Performance Trends",
            description=f"Performance trends over the past {hours} hours",
            color=self.colors['info']
        )
        
        if not hourly_metrics:
            embed.add_field(
                name="No Data",
                value="No hourly metrics available.",
                inline=False
            )
            return embed
        
        # Create simple text-based chart
        trend_text = ""
        for metric in hourly_metrics[-12:]:  # Last 12 hours
            hour = datetime.fromisoformat(metric['hour']).strftime('%H:00')
            success_rate = metric.get('success_rate', 0)
            total_checks = metric.get('total_checks', 0)
            avg_duration = metric.get('avg_duration_ms', 0)
            
            # Simple bar for success rate
            bar_length = int(success_rate / 10)
            bar = "█" * bar_length + "░" * (10 - bar_length)
            
            trend_text += f"`{hour}` {bar} {success_rate:.0f}% ({total_checks} checks, {avg_duration:.0f}ms)\n"
        
        embed.add_field(
            name="Hourly Success Rates",
            value=trend_text,
            inline=False
        )
        
        return embed
    
    def _determine_system_health(self, dashboard_data: DashboardData) -> tuple[str, str]:
        """Determine system health status and emoji."""
        success_rate = dashboard_data.success_rate
        active_ratio = dashboard_data.active_products / max(dashboard_data.total_products, 1)
        
        if success_rate >= 95 and active_ratio >= 0.8:
            return "Excellent", "🟢"
        elif success_rate >= 85 and active_ratio >= 0.6:
            return "Good", "🟡"
        elif success_rate >= 70 and active_ratio >= 0.4:
            return "Fair", "🟠"
        else:
            return "Poor", "🔴"
    
    def _get_health_color(self, health_status: str) -> int:
        """Get color based on health status."""
        health_colors = {
            "Excellent": self.colors['success'],
            "Good": self.colors['success'],
            "Fair": self.colors['warning'],
            "Poor": self.colors['error']
        }
        return health_colors.get(health_status, self.colors['neutral'])
    
    def _get_status_color(self, success_rate: float) -> int:
        """Get color based on success rate."""
        if success_rate >= 90:
            return self.colors['success']
        elif success_rate >= 70:
            return self.colors['warning']
        else:
            return self.colors['error']
    
    def _format_uptime(self, uptime_seconds: int) -> str:
        """Format uptime in human readable format."""
        if uptime_seconds < 60:
            return f"{uptime_seconds}s"
        elif uptime_seconds < 3600:
            return f"{uptime_seconds // 60}m"
        elif uptime_seconds < 86400:
            return f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m"
        else:
            days = uptime_seconds // 86400
            hours = (uptime_seconds % 86400) // 3600
            return f"{days}d {hours}h"