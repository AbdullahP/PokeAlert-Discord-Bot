"""
Performance monitoring and metrics collection service.
"""
import logging
import time
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import sqlite3
from collections import defaultdict, deque

from ..config.config_manager import ConfigManager
from ..database.repository import MetricsRepository
from ..models.product_data import MonitoringStatus


class PerformanceMetrics:
    """Container for performance metrics data."""
    
    def __init__(self):
        """Initialize performance metrics."""
        # Response time tracking
        self.response_times = deque(maxlen=1000)  # Store last 1000 response times
        self.response_time_by_domain = defaultdict(lambda: deque(maxlen=100))
        
        # Success rate tracking
        self.success_count = 0
        self.error_count = 0
        self.success_by_domain = defaultdict(int)
        self.error_by_domain = defaultdict(int)
        
        # Database metrics
        self.db_operation_times = deque(maxlen=1000)
        self.db_operation_counts = defaultdict(int)
        self.db_error_counts = defaultdict(int)
        
        # Discord API metrics
        self.discord_request_times = deque(maxlen=100)
        self.discord_rate_limits = []  # List of rate limit events
        self.discord_error_counts = defaultdict(int)
        
        # Last reset time
        self.last_reset = datetime.utcnow()
    
    def reset(self):
        """Reset all metrics."""
        self.__init__()


class PerformanceMonitor:
    """Service for monitoring and reporting on system performance."""
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize performance monitor."""
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.metrics_repo = MetricsRepository()
        self.metrics = PerformanceMetrics()
        
        # Configuration
        self.metrics_interval = self.config_manager.get('monitoring.metrics_interval', 60)  # seconds
        self.metrics_retention = self.config_manager.get('monitoring.metrics_retention', 7)  # days
        self.alert_threshold = self.config_manager.get('monitoring.alert_threshold', 80.0)  # percentage
        
        # Monitoring task
        self.monitoring_task = None
        self.running = False
    
    async def start(self):
        """Start performance monitoring."""
        if self.running:
            return
            
        self.running = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("Performance monitoring started")
    
    async def stop(self):
        """Stop performance monitoring."""
        if not self.running:
            return
            
        self.running = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
            self.monitoring_task = None
        self.logger.info("Performance monitoring stopped")
    
    async def _monitoring_loop(self):
        """Background task for periodic metrics collection and cleanup."""
        try:
            while self.running:
                # Collect and store metrics
                await self._collect_metrics()
                
                # Clean up old metrics periodically
                if datetime.utcnow() - self.metrics.last_reset > timedelta(hours=24):
                    await self._cleanup_old_metrics()
                    self.metrics.reset()
                
                # Wait for next collection interval
                await asyncio.sleep(self.metrics_interval)
        except asyncio.CancelledError:
            self.logger.info("Performance monitoring loop cancelled")
        except Exception as e:
            self.logger.error(f"Error in performance monitoring loop: {e}")
    
    async def _collect_metrics(self):
        """Collect and store current metrics."""
        try:
            # Calculate current success rate
            total = self.metrics.success_count + self.metrics.error_count
            success_rate = (self.metrics.success_count / total * 100) if total > 0 else 100.0
            
            # Calculate average response time
            avg_response_time = sum(self.metrics.response_times) / len(self.metrics.response_times) if self.metrics.response_times else 0
            
            # Calculate average database operation time
            avg_db_time = sum(self.metrics.db_operation_times) / len(self.metrics.db_operation_times) if self.metrics.db_operation_times else 0
            
            # Log metrics summary
            self.logger.info(
                f"Performance metrics - Success rate: {success_rate:.1f}%, "
                f"Avg response time: {avg_response_time:.2f}ms, "
                f"Avg DB time: {avg_db_time:.2f}ms"
            )
            
            # Check for alert conditions
            if success_rate < self.alert_threshold:
                self.logger.warning(
                    f"Performance alert: Success rate ({success_rate:.1f}%) "
                    f"below threshold ({self.alert_threshold}%)"
                )
                
            # Store metrics in database if needed
            # This is handled by individual components calling record_* methods
            
        except Exception as e:
            self.logger.error(f"Error collecting metrics: {e}")
    
    async def _cleanup_old_metrics(self):
        """Clean up old metrics from the database."""
        try:
            # Calculate cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=self.metrics_retention)
            
            # Execute cleanup query
            conn = self.metrics_repo.db.connect()
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM monitoring_metrics WHERE timestamp < ?",
                (cutoff_date.isoformat(),)
            )
            deleted_count = cursor.rowcount
            conn.commit()
            
            self.logger.info(f"Cleaned up {deleted_count} old metrics records")
        except sqlite3.Error as e:
            self.logger.error(f"Database error during metrics cleanup: {e}")
        except Exception as e:
            self.logger.error(f"Error cleaning up old metrics: {e}")
    
    def record_response_time(self, product_id: str, domain: str, duration_ms: float, success: bool):
        """
        Record a response time measurement.
        
        Args:
            product_id: The product ID
            domain: The domain (e.g., 'bol.com')
            duration_ms: Response time in milliseconds
            success: Whether the request was successful
        """
        # Store in memory metrics
        self.metrics.response_times.append(duration_ms)
        self.metrics.response_time_by_domain[domain].append(duration_ms)
        
        if success:
            self.metrics.success_count += 1
            self.metrics.success_by_domain[domain] += 1
        else:
            self.metrics.error_count += 1
            self.metrics.error_by_domain[domain] += 1
        
        # Store in database
        asyncio.create_task(self._store_response_metric(product_id, duration_ms, success))
    
    async def _store_response_metric(self, product_id: str, duration_ms: float, success: bool, error_message: str = None):
        """Store response metric in database."""
        try:
            await asyncio.to_thread(
                self.metrics_repo.add_metric,
                product_id,
                int(duration_ms),
                success,
                error_message
            )
        except Exception as e:
            self.logger.error(f"Error storing response metric: {e}")
    
    def record_db_operation(self, operation: str, duration_ms: float, success: bool):
        """
        Record a database operation.
        
        Args:
            operation: The operation type (e.g., 'query', 'insert')
            duration_ms: Operation time in milliseconds
            success: Whether the operation was successful
        """
        # Store in memory metrics
        self.metrics.db_operation_times.append(duration_ms)
        self.metrics.db_operation_counts[operation] += 1
        
        if not success:
            self.metrics.db_error_counts[operation] += 1
    
    def record_discord_request(self, endpoint: str, duration_ms: float, status_code: int):
        """
        Record a Discord API request.
        
        Args:
            endpoint: The API endpoint
            duration_ms: Response time in milliseconds
            status_code: HTTP status code
        """
        # Store in memory metrics
        self.metrics.discord_request_times.append(duration_ms)
        
        # Track rate limits
        if status_code == 429:  # Rate limited
            self.metrics.discord_rate_limits.append({
                'endpoint': endpoint,
                'timestamp': datetime.utcnow(),
                'duration_ms': duration_ms
            })
            self.metrics.discord_error_counts['rate_limit'] += 1
        elif status_code >= 400:
            self.metrics.discord_error_counts[f'status_{status_code}'] += 1
    
    async def get_monitoring_status(self, product_id: str, hours: int = 24) -> MonitoringStatus:
        """
        Get monitoring status for a product.
        
        Args:
            product_id: The product ID
            hours: Time window in hours
            
        Returns:
            MonitoringStatus object with metrics
        """
        return await asyncio.to_thread(
            self.metrics_repo.get_monitoring_status,
            product_id,
            hours
        )
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get overall system metrics.
        
        Returns:
            Dictionary with system metrics
        """
        try:
            # Calculate success rate
            total = self.metrics.success_count + self.metrics.error_count
            success_rate = (self.metrics.success_count / total * 100) if total > 0 else 100.0
            
            # Calculate average response times
            avg_response_time = sum(self.metrics.response_times) / len(self.metrics.response_times) if self.metrics.response_times else 0
            
            # Get domain-specific metrics
            domain_metrics = {}
            for domain in self.metrics.response_time_by_domain:
                domain_total = self.metrics.success_by_domain[domain] + self.metrics.error_by_domain[domain]
                domain_success_rate = (self.metrics.success_by_domain[domain] / domain_total * 100) if domain_total > 0 else 100.0
                domain_avg_time = sum(self.metrics.response_time_by_domain[domain]) / len(self.metrics.response_time_by_domain[domain]) if self.metrics.response_time_by_domain[domain] else 0
                
                domain_metrics[domain] = {
                    'success_rate': domain_success_rate,
                    'avg_response_time': domain_avg_time,
                    'success_count': self.metrics.success_by_domain[domain],
                    'error_count': self.metrics.error_by_domain[domain]
                }
            
            # Get database metrics
            db_metrics = {
                'avg_operation_time': sum(self.metrics.db_operation_times) / len(self.metrics.db_operation_times) if self.metrics.db_operation_times else 0,
                'operation_counts': dict(self.metrics.db_operation_counts),
                'error_counts': dict(self.metrics.db_error_counts)
            }
            
            # Get Discord API metrics
            discord_metrics = {
                'avg_request_time': sum(self.metrics.discord_request_times) / len(self.metrics.discord_request_times) if self.metrics.discord_request_times else 0,
                'rate_limit_count': len(self.metrics.discord_rate_limits),
                'error_counts': dict(self.metrics.discord_error_counts),
                'recent_rate_limits': [
                    {
                        'endpoint': rl['endpoint'],
                        'timestamp': rl['timestamp'].isoformat(),
                        'duration_ms': rl['duration_ms']
                    }
                    for rl in self.metrics.discord_rate_limits[-5:]  # Last 5 rate limits
                ]
            }
            
            # Get total checks today from database
            total_checks_today = await asyncio.to_thread(
                self.metrics_repo.get_total_checks_today
            )
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'uptime_seconds': (datetime.utcnow() - self.metrics.last_reset).total_seconds(),
                'success_rate': success_rate,
                'avg_response_time': avg_response_time,
                'success_count': self.metrics.success_count,
                'error_count': self.metrics.error_count,
                'total_checks_today': total_checks_today,
                'domain_metrics': domain_metrics,
                'database_metrics': db_metrics,
                'discord_metrics': discord_metrics
            }
            
        except Exception as e:
            self.logger.error(f"Error getting system metrics: {e}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }
    
    async def get_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """
        Generate a comprehensive performance report.
        
        Args:
            hours: Time window in hours
            
        Returns:
            Dictionary with performance report data
        """
        try:
            # Get current system metrics
            system_metrics = await self.get_system_metrics()
            
            # Get product-specific metrics from database
            conn = self.metrics_repo.db.connect()
            cursor = conn.cursor()
            
            # Get success rates by product
            cursor.execute(
                """
                SELECT 
                    product_id,
                    COUNT(*) as total,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                    AVG(check_duration_ms) as avg_duration
                FROM monitoring_metrics
                WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                GROUP BY product_id
                """,
                (hours,)
            )
            
            product_metrics = {}
            for row in cursor.fetchall():
                product_id = row['product_id']
                total = row['total']
                successes = row['successes']
                success_rate = (successes / total * 100) if total > 0 else 100.0
                
                product_metrics[product_id] = {
                    'total_checks': total,
                    'success_count': successes,
                    'error_count': total - successes,
                    'success_rate': success_rate,
                    'avg_duration_ms': row['avg_duration']
                }
            
            # Get error distribution
            cursor.execute(
                """
                SELECT 
                    error_message,
                    COUNT(*) as count
                FROM monitoring_metrics
                WHERE success = 0 AND timestamp >= datetime('now', '-' || ? || ' hours')
                GROUP BY error_message
                ORDER BY count DESC
                LIMIT 10
                """,
                (hours,)
            )
            
            error_distribution = {}
            for row in cursor.fetchall():
                error_message = row['error_message'] or 'Unknown error'
                error_distribution[error_message] = row['count']
            
            # Get performance over time (hourly)
            cursor.execute(
                """
                SELECT 
                    strftime('%Y-%m-%d %H:00:00', timestamp) as hour,
                    COUNT(*) as total,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                    AVG(check_duration_ms) as avg_duration
                FROM monitoring_metrics
                WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                GROUP BY hour
                ORDER BY hour
                """,
                (hours,)
            )
            
            hourly_metrics = []
            for row in cursor.fetchall():
                total = row['total']
                successes = row['successes']
                success_rate = (successes / total * 100) if total > 0 else 100.0
                
                hourly_metrics.append({
                    'hour': row['hour'],
                    'total_checks': total,
                    'success_rate': success_rate,
                    'avg_duration_ms': row['avg_duration']
                })
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'time_window_hours': hours,
                'system_metrics': system_metrics,
                'product_metrics': product_metrics,
                'error_distribution': error_distribution,
                'hourly_metrics': hourly_metrics
            }
            
        except sqlite3.Error as e:
            self.logger.error(f"Database error generating performance report: {e}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'error': f"Database error: {str(e)}"
            }
        except Exception as e:
            self.logger.error(f"Error generating performance report: {e}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }