"""
Tests for the dashboard service.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import discord

from src.services.dashboard_service import DashboardService
from src.models.product_data import (
    DashboardData, StockChange, ProductConfig, MonitoringStatus, URLType
)
from src.config.config_manager import ConfigManager
from src.services.performance_monitor import PerformanceMonitor


@pytest.fixture
def mock_config_manager():
    """Create mock config manager."""
    config = Mock(spec=ConfigManager)
    config.get.side_effect = lambda key, default=None: {
        'dashboard.max_products_per_embed': 10,
        'dashboard.max_changes_displayed': 5,
        'dashboard.max_errors_displayed': 5
    }.get(key, default)
    return config


@pytest.fixture
def mock_product_manager():
    """Create mock product manager."""
    manager = AsyncMock()
    
    # Mock dashboard data
    stock_changes = [
        StockChange(
            product_id="test-product-1",
            previous_status="Out of Stock",
            current_status="In Stock",
            timestamp=datetime.utcnow() - timedelta(minutes=5)
        ),
        StockChange(
            product_id="test-product-2",
            previous_status="In Stock",
            current_status="Out of Stock",
            timestamp=datetime.utcnow() - timedelta(minutes=10)
        )
    ]
    
    dashboard_data = DashboardData(
        total_products=5,
        active_products=4,
        total_checks_today=150,
        success_rate=95.5,
        recent_stock_changes=stock_changes,
        error_summary={"Network Error": 2, "Parse Error": 1}
    )
    
    manager.get_dashboard_data.return_value = dashboard_data
    
    # Mock product configs
    products = [
        ProductConfig(
            product_id="test-product-1",
            url="https://www.bol.com/nl/nl/p/test/123/",
            url_type=URLType.PRODUCT.value,
            channel_id=12345,
            guild_id=67890,
            monitoring_interval=60,
            is_active=True,
            created_at=datetime.utcnow() - timedelta(days=1)
        ),
        ProductConfig(
            product_id="test-product-2",
            url="https://www.bol.com/nl/nl/rnwy/account/wenslijst/456/",
            url_type=URLType.WISHLIST.value,
            channel_id=12345,
            guild_id=67890,
            monitoring_interval=30,
            is_active=True,
            created_at=datetime.utcnow() - timedelta(hours=2)
        )
    ]
    
    manager.get_products_by_guild.return_value = products
    manager.get_product_config.return_value = products[0]
    
    return manager


@pytest.fixture
def mock_performance_monitor():
    """Create mock performance monitor."""
    monitor = AsyncMock(spec=PerformanceMonitor)
    
    # Mock monitoring status
    monitoring_status = MonitoringStatus(
        product_id="test-product-1",
        is_active=True,
        last_check=datetime.utcnow() - timedelta(minutes=1),
        success_rate=98.5,
        error_count=1,
        last_error="Connection timeout"
    )
    
    monitor.get_monitoring_status.return_value = monitoring_status
    
    # Mock system metrics
    system_metrics = {
        'timestamp': datetime.utcnow().isoformat(),
        'uptime_seconds': 86400,
        'success_rate': 95.5,
        'avg_response_time': 250.5,
        'success_count': 145,
        'error_count': 5,
        'total_checks_today': 150,
        'domain_metrics': {
            'bol.com': {
                'success_rate': 95.5,
                'avg_response_time': 250.5,
                'success_count': 145,
                'error_count': 5
            }
        },
        'database_metrics': {
            'avg_operation_time': 15.2,
            'operation_counts': {'query': 100, 'insert': 50},
            'error_counts': {'timeout': 1}
        },
        'discord_metrics': {
            'avg_request_time': 180.3,
            'rate_limit_count': 0,
            'error_counts': {},
            'recent_rate_limits': []
        }
    }
    
    monitor.get_system_metrics.return_value = system_metrics
    
    # Mock performance report
    performance_report = {
        'timestamp': datetime.utcnow().isoformat(),
        'time_window_hours': 24,
        'system_metrics': system_metrics,
        'product_metrics': {
            'test-product-1': {
                'total_checks': 50,
                'success_count': 48,
                'error_count': 2,
                'success_rate': 96.0,
                'avg_duration_ms': 245.5
            },
            'test-product-2': {
                'total_checks': 30,
                'success_count': 29,
                'error_count': 1,
                'success_rate': 96.7,
                'avg_duration_ms': 220.3
            }
        },
        'error_distribution': {
            'Connection timeout': 2,
            'Parse error': 1
        },
        'hourly_metrics': [
            {
                'hour': (datetime.utcnow() - timedelta(hours=1)).strftime('%Y-%m-%d %H:00:00'),
                'total_checks': 10,
                'success_rate': 100.0,
                'avg_duration_ms': 230.5
            },
            {
                'hour': datetime.utcnow().strftime('%Y-%m-%d %H:00:00'),
                'total_checks': 8,
                'success_rate': 87.5,
                'avg_duration_ms': 280.2
            }
        ]
    }
    
    monitor.get_performance_report.return_value = performance_report
    
    return monitor


@pytest.fixture
def dashboard_service(mock_config_manager, mock_product_manager, mock_performance_monitor):
    """Create dashboard service instance."""
    return DashboardService(
        config_manager=mock_config_manager,
        product_manager=mock_product_manager,
        performance_monitor=mock_performance_monitor
    )


@pytest.mark.asyncio
class TestDashboardService:
    """Test cases for DashboardService."""
    
    async def test_create_status_dashboard_success(self, dashboard_service):
        """Test successful status dashboard creation."""
        guild_id = 67890
        
        embeds = await dashboard_service.create_status_dashboard(guild_id)
        
        assert len(embeds) >= 1
        assert embeds[0].title == "📊 Monitoring Dashboard"
        assert "System Overview" in [field.name for field in embeds[0].fields]
        
        # Check that dashboard data was requested
        dashboard_service.product_manager.get_dashboard_data.assert_called_once_with(guild_id)
    
    async def test_create_status_dashboard_with_changes(self, dashboard_service):
        """Test status dashboard with recent changes."""
        guild_id = 67890
        
        embeds = await dashboard_service.create_status_dashboard(guild_id)
        
        # Should have multiple embeds including recent changes
        assert len(embeds) >= 3
        
        # Find the recent changes embed
        changes_embed = next((e for e in embeds if "Recent Stock Changes" in e.title), None)
        assert changes_embed is not None
        assert changes_embed.color == dashboard_service.colors['info']
    
    async def test_create_status_dashboard_with_errors(self, dashboard_service):
        """Test status dashboard with error summary."""
        guild_id = 67890
        
        embeds = await dashboard_service.create_status_dashboard(guild_id)
        
        # Find the error summary embed
        error_embed = next((e for e in embeds if "Error Summary" in e.title), None)
        assert error_embed is not None
        assert error_embed.color == dashboard_service.colors['warning']
    
    async def test_create_status_dashboard_error_handling(self, dashboard_service):
        """Test status dashboard error handling."""
        guild_id = 67890
        
        # Make product manager raise an exception
        dashboard_service.product_manager.get_dashboard_data.side_effect = Exception("Test error")
        
        embeds = await dashboard_service.create_status_dashboard(guild_id)
        
        assert len(embeds) == 1
        assert embeds[0].title == "Dashboard Error"
        assert embeds[0].color == dashboard_service.colors['error']
        assert "Test error" in embeds[0].description
    
    async def test_create_performance_dashboard_success(self, dashboard_service):
        """Test successful performance dashboard creation."""
        guild_id = 67890
        hours = 24
        
        embeds = await dashboard_service.create_performance_dashboard(guild_id, hours)
        
        assert len(embeds) >= 1
        
        # Check system metrics embed
        system_embed = embeds[0]
        assert "System Performance Metrics" in system_embed.title
        assert system_embed.color == dashboard_service.colors['info']
        
        # Verify performance monitor was called
        dashboard_service.performance_monitor.get_performance_report.assert_called_once_with(hours)
    
    async def test_create_performance_dashboard_no_monitor(self, mock_config_manager, mock_product_manager):
        """Test performance dashboard without performance monitor."""
        service = DashboardService(
            config_manager=mock_config_manager,
            product_manager=mock_product_manager,
            performance_monitor=None
        )
        
        embeds = await service.create_performance_dashboard(67890, 24)
        
        assert len(embeds) == 1
        assert "Performance monitoring is not available" in embeds[0].description
        assert embeds[0].color == service.colors['warning']
    
    async def test_create_performance_dashboard_error(self, dashboard_service):
        """Test performance dashboard with error in report."""
        guild_id = 67890
        
        # Make performance monitor return error
        dashboard_service.performance_monitor.get_performance_report.return_value = {
            'error': 'Database connection failed'
        }
        
        embeds = await dashboard_service.create_performance_dashboard(guild_id, 24)
        
        assert len(embeds) == 1
        assert "Performance Dashboard Error" in embeds[0].title
        assert embeds[0].color == dashboard_service.colors['error']
    
    async def test_create_product_status_embed_success(self, dashboard_service):
        """Test successful product status embed creation."""
        product_id = "test-product-1"
        hours = 24
        
        embed = await dashboard_service.create_product_status_embed(product_id, hours)
        
        assert embed.title == f"Product Status: {product_id}"
        assert embed.color == dashboard_service.colors['success']  # High success rate
        
        # Check fields
        field_names = [field.name for field in embed.fields]
        assert "Product Information" in field_names
        assert "Monitoring Metrics" in field_names
        
        # Verify calls
        dashboard_service.product_manager.get_product_config.assert_called_once_with(product_id)
        dashboard_service.performance_monitor.get_monitoring_status.assert_called_once_with(product_id, hours)
    
    async def test_create_product_status_embed_not_found(self, dashboard_service):
        """Test product status embed for non-existent product."""
        product_id = "non-existent"
        
        # Make product manager return None
        dashboard_service.product_manager.get_product_config.return_value = None
        
        embed = await dashboard_service.create_product_status_embed(product_id, 24)
        
        assert embed.title == "Product Not Found"
        assert embed.color == dashboard_service.colors['error']
        assert product_id in embed.description
    
    async def test_create_product_status_embed_inactive_product(self, dashboard_service):
        """Test product status embed for inactive product."""
        product_id = "test-product-1"
        
        # Mock inactive product
        inactive_product = ProductConfig(
            product_id=product_id,
            url="https://www.bol.com/nl/nl/p/test/123/",
            url_type=URLType.PRODUCT.value,
            channel_id=12345,
            guild_id=67890,
            monitoring_interval=60,
            is_active=False
        )
        
        dashboard_service.product_manager.get_product_config.return_value = inactive_product
        
        embed = await dashboard_service.create_product_status_embed(product_id, 24)
        
        assert embed.color == dashboard_service.colors['neutral']
        assert "Inactive" in embed.fields[0].value
    
    async def test_create_monitoring_history_embed_success(self, dashboard_service):
        """Test successful monitoring history embed creation."""
        guild_id = 67890
        hours = 24
        
        embed = await dashboard_service.create_monitoring_history_embed(guild_id, hours)
        
        assert embed.title == "Monitoring History"
        assert embed.color == dashboard_service.colors['info']
        
        # Check fields
        field_names = [field.name for field in embed.fields]
        assert "Recent Stock Changes" in field_names
        assert "System Activity" in field_names
        
        # Verify calls
        dashboard_service.product_manager.get_dashboard_data.assert_called_with(guild_id)
        dashboard_service.performance_monitor.get_system_metrics.assert_called_once()
    
    async def test_create_real_time_status_embed_excellent_health(self, dashboard_service):
        """Test real-time status embed with excellent health."""
        guild_id = 67890
        
        embed = await dashboard_service.create_real_time_status_embed(guild_id)
        
        assert "🟢" in embed.title
        assert "Excellent" in embed.description
        assert embed.color == dashboard_service.colors['success']
        
        # Check fields
        field_names = [field.name for field in embed.fields]
        assert "📊 Live Metrics" in field_names
        assert "🔄 Latest Activity" in field_names
        assert "⚡ Performance" in field_names
    
    async def test_create_real_time_status_embed_poor_health(self, dashboard_service):
        """Test real-time status embed with poor health."""
        guild_id = 67890
        
        # Mock poor dashboard data
        poor_dashboard = DashboardData(
            total_products=5,
            active_products=2,
            total_checks_today=50,
            success_rate=65.0,  # Poor success rate
            recent_stock_changes=[],
            error_summary={"Network Error": 10, "Parse Error": 5}
        )
        
        dashboard_service.product_manager.get_dashboard_data.return_value = poor_dashboard
        
        embed = await dashboard_service.create_real_time_status_embed(guild_id)
        
        assert "🔴" in embed.title
        assert "Poor" in embed.description
        assert embed.color == dashboard_service.colors['error']
    
    async def test_create_real_time_status_embed_no_recent_activity(self, dashboard_service):
        """Test real-time status embed with no recent activity."""
        guild_id = 67890
        
        # Mock dashboard data with no changes
        no_changes_dashboard = DashboardData(
            total_products=5,
            active_products=4,
            total_checks_today=150,
            success_rate=95.5,
            recent_stock_changes=[],  # No changes
            error_summary={}
        )
        
        dashboard_service.product_manager.get_dashboard_data.return_value = no_changes_dashboard
        
        embed = await dashboard_service.create_real_time_status_embed(guild_id)
        
        # Find the latest activity field
        activity_field = next((f for f in embed.fields if "Latest Activity" in f.name), None)
        assert activity_field is not None
        assert "No recent stock changes" in activity_field.value
    
    async def test_color_determination_based_on_success_rate(self, dashboard_service):
        """Test color determination based on success rates."""
        # Test different success rates
        test_cases = [
            (98.0, dashboard_service.colors['success']),  # Excellent
            (92.0, dashboard_service.colors['success']),  # Good
            (75.0, dashboard_service.colors['warning']),  # Fair
            (60.0, dashboard_service.colors['error'])     # Poor
        ]
        
        for success_rate, expected_color in test_cases:
            dashboard_data = DashboardData(
                total_products=5,
                active_products=4,
                total_checks_today=100,
                success_rate=success_rate,
                recent_stock_changes=[],
                error_summary={}
            )
            
            dashboard_service.product_manager.get_dashboard_data.return_value = dashboard_data
            
            embed = await dashboard_service.create_real_time_status_embed(67890)
            assert embed.color == expected_color
    
    async def test_embed_field_limits(self, dashboard_service):
        """Test that embeds respect field limits."""
        guild_id = 67890
        
        # Create many stock changes
        many_changes = [
            StockChange(
                product_id=f"product-{i}",
                previous_status="Out of Stock",
                current_status="In Stock",
                timestamp=datetime.utcnow() - timedelta(minutes=i)
            )
            for i in range(20)  # More than max_changes_displayed
        ]
        
        dashboard_data = DashboardData(
            total_products=20,
            active_products=18,
            total_checks_today=500,
            success_rate=95.5,
            recent_stock_changes=many_changes,
            error_summary={}
        )
        
        dashboard_service.product_manager.get_dashboard_data.return_value = dashboard_data
        
        embeds = await dashboard_service.create_status_dashboard(guild_id)
        
        # Find the recent changes embed
        changes_embed = next((e for e in embeds if "Recent Stock Changes" in e.title), None)
        assert changes_embed is not None
        
        # Should only show max_changes_displayed (5) changes
        changes_field = changes_embed.fields[0]
        change_lines = changes_field.value.split('\n')
        assert len(change_lines) <= dashboard_service.max_changes_displayed
    
    async def test_error_handling_in_embed_creation(self, dashboard_service):
        """Test error handling in individual embed creation methods."""
        # Test product status embed error
        dashboard_service.product_manager.get_product_config.side_effect = Exception("DB error")
        
        embed = await dashboard_service.create_product_status_embed("test-product", 24)
        
        assert embed.title == "Error"
        assert embed.color == dashboard_service.colors['error']
        assert "DB error" in embed.description
    
    async def test_performance_dashboard_with_all_components(self, dashboard_service):
        """Test performance dashboard includes all expected components."""
        guild_id = 67890
        hours = 24
        
        embeds = await dashboard_service.create_performance_dashboard(guild_id, hours)
        
        # Should have multiple embeds for different metrics
        assert len(embeds) >= 4
        
        embed_titles = [embed.title for embed in embeds]
        
        # Check for expected embed types
        assert any("System Performance" in title for title in embed_titles)
        assert any("Product Performance" in title for title in embed_titles)
        assert any("Error Distribution" in title for title in embed_titles)
        assert any("Hourly Performance" in title for title in embed_titles)
    
    async def test_dashboard_service_configuration(self, mock_config_manager, mock_product_manager):
        """Test dashboard service respects configuration."""
        # Test custom configuration
        mock_config_manager.get.side_effect = lambda key, default=None: {
            'dashboard.max_products_per_embed': 5,
            'dashboard.max_changes_displayed': 3,
            'dashboard.max_errors_displayed': 2
        }.get(key, default)
        
        service = DashboardService(
            config_manager=mock_config_manager,
            product_manager=mock_product_manager,
            performance_monitor=None
        )
        
        assert service.max_products_per_embed == 5
        assert service.max_changes_displayed == 3
        assert service.max_errors_displayed == 2


@pytest.mark.asyncio
class TestDashboardServiceIntegration:
    """Integration tests for dashboard service."""
    
    async def test_full_dashboard_workflow(self, dashboard_service):
        """Test complete dashboard workflow."""
        guild_id = 67890
        
        # Test status dashboard
        status_embeds = await dashboard_service.create_status_dashboard(guild_id)
        assert len(status_embeds) >= 1
        
        # Test performance dashboard
        perf_embeds = await dashboard_service.create_performance_dashboard(guild_id, 24)
        assert len(perf_embeds) >= 1
        
        # Test product status
        product_embed = await dashboard_service.create_product_status_embed("test-product-1", 24)
        assert product_embed.title.startswith("Product Status:")
        
        # Test monitoring history
        history_embed = await dashboard_service.create_monitoring_history_embed(guild_id, 24)
        assert history_embed.title == "Monitoring History"
        
        # Test real-time status
        realtime_embed = await dashboard_service.create_real_time_status_embed(guild_id)
        assert "Real-Time Monitoring Status" in realtime_embed.title
    
    async def test_dashboard_with_no_data(self, mock_config_manager):
        """Test dashboard behavior with no data."""
        # Mock empty product manager
        empty_product_manager = AsyncMock()
        empty_dashboard = DashboardData(
            total_products=0,
            active_products=0,
            total_checks_today=0,
            success_rate=0.0,
            recent_stock_changes=[],
            error_summary={}
        )
        empty_product_manager.get_dashboard_data.return_value = empty_dashboard
        empty_product_manager.get_products_by_guild.return_value = []
        
        service = DashboardService(
            config_manager=mock_config_manager,
            product_manager=empty_product_manager,
            performance_monitor=None
        )
        
        embeds = await service.create_status_dashboard(67890)
        
        # Should still create main embed
        assert len(embeds) >= 1
        assert embeds[0].title == "📊 Monitoring Dashboard"
        
        # Should show zero values
        main_field = embeds[0].fields[0]
        assert "Total Products:** 0" in main_field.value