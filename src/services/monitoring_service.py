"""
Production monitoring service for Pokemon Discord Bot.

This service provides comprehensive monitoring capabilities including:
- Health checks and metrics collection
- Performance monitoring and alerting
- Resource usage tracking
- Error monitoring and notification
- Uptime monitoring
"""
import asyncio
import logging
import time
import psutil
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import yaml
import json

from ..config.environment import Environment


@dataclass
class HealthStatus:
    """Health status information."""
    status: str
    timestamp: datetime
    uptime: float
    version: str
    metrics: Dict[str, Any]
    database: Dict[str, Any]
    discord: Dict[str, Any]


@dataclass
class Alert:
    """Alert information."""
    name: str
    severity: str
    message: str
    timestamp: datetime
    resolved: bool = False
    cooldown: int = 300


class MonitoringService:
    """Production monitoring service."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.start_time = time.time()
        self.config = self._load_config()
        self.metrics = {}
        self.alerts = {}
        self.last_alert_times = {}
        
    def _load_config(self) -> Dict[str, Any]:
        """Load monitoring configuration."""
        config_path = Path("config/monitoring.yaml")
        if config_path.exists():
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        return {}
    
    async def get_health_status(self) -> HealthStatus:
        """Get comprehensive health status."""
        try:
            # Basic metrics
            uptime = time.time() - self.start_time
            
            # System metrics
            process = psutil.Process()
            memory_info = process.memory_info()
            cpu_percent = process.cpu_percent()
            
            # Database metrics
            db_status = await self._check_database_health()
            
            # Discord metrics (placeholder - would need actual Discord client)
            discord_status = {
                "status": "connected",
                "latency_ms": 45,  # Would get from actual client
                "guilds": 1
            }
            
            # Performance metrics
            metrics = {
                "products_monitored": await self._get_products_count(),
                "active_monitors": await self._get_active_monitors_count(),
                "success_rate": await self._get_success_rate(),
                "avg_response_time": await self._get_avg_response_time(),
                "notifications_sent_24h": await self._get_notifications_count(),
                "errors_24h": await self._get_errors_count(),
                "memory_usage_mb": memory_info.rss / 1024 / 1024,
                "cpu_usage_percent": cpu_percent
            }
            
            # Determine overall status
            status = "healthy"
            if metrics["success_rate"] < 90:
                status = "degraded"
            if metrics["success_rate"] < 80 or not db_status["connected"]:
                status = "unhealthy"
            
            return HealthStatus(
                status=status,
                timestamp=datetime.utcnow(),
                uptime=uptime,
                version="1.0.0",  # Would get from actual version
                metrics=metrics,
                database=db_status,
                discord=discord_status
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get health status: {e}")
            return HealthStatus(
                status="error",
                timestamp=datetime.utcnow(),
                uptime=time.time() - self.start_time,
                version="1.0.0",
                metrics={},
                database={"status": "error", "error": str(e)},
                discord={"status": "error", "error": str(e)}
            )
    
    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database health and metrics."""
        try:
            db_path = Environment.get_database_url().replace("sqlite:///", "")
            
            # Check if database file exists
            if not Path(db_path).exists():
                return {"status": "error", "error": "Database file not found"}
            
            # Get database size
            db_size = Path(db_path).stat().st_size / 1024 / 1024  # MB
            
            # Test database connection
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            
            # Run a simple query
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
            table_count = cursor.fetchone()[0]
            
            # Check last backup
            backup_dir = Path("backups")
            last_backup = None
            if backup_dir.exists():
                backup_files = list(backup_dir.glob("pokemon_bot_*.db*"))
                if backup_files:
                    latest_backup = max(backup_files, key=lambda x: x.stat().st_mtime)
                    last_backup = datetime.fromtimestamp(latest_backup.stat().st_mtime)
            
            conn.close()
            
            return {
                "status": "connected",
                "size_mb": round(db_size, 2),
                "tables": table_count,
                "last_backup": last_backup.isoformat() if last_backup else None
            }
            
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _get_products_count(self) -> int:
        """Get total number of monitored products."""
        try:
            db_path = Environment.get_database_url().replace("sqlite:///", "")
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM products WHERE is_active = 1;")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0
    
    async def _get_active_monitors_count(self) -> int:
        """Get number of actively running monitors."""
        # This would integrate with actual monitoring engine
        return await self._get_products_count()
    
    async def _get_success_rate(self) -> float:
        """Get monitoring success rate for last 24 hours."""
        try:
            db_path = Environment.get_database_url().replace("sqlite:///", "")
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            
            # Get metrics from last 24 hours
            yesterday = datetime.utcnow() - timedelta(hours=24)
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
                FROM monitoring_metrics 
                WHERE timestamp > ?
            """, (yesterday,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0] > 0:
                return (result[1] / result[0]) * 100
            return 100.0
            
        except Exception:
            return 0.0
    
    async def _get_avg_response_time(self) -> float:
        """Get average response time for last 24 hours."""
        try:
            db_path = Environment.get_database_url().replace("sqlite:///", "")
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            
            yesterday = datetime.utcnow() - timedelta(hours=24)
            cursor.execute("""
                SELECT AVG(check_duration_ms) / 1000.0
                FROM monitoring_metrics 
                WHERE timestamp > ? AND success = 1
            """, (yesterday,))
            
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result and result[0] else 0.0
            
        except Exception:
            return 0.0
    
    async def _get_notifications_count(self) -> int:
        """Get number of notifications sent in last 24 hours."""
        try:
            db_path = Environment.get_database_url().replace("sqlite:///", "")
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            
            yesterday = datetime.utcnow() - timedelta(hours=24)
            cursor.execute("""
                SELECT COUNT(*)
                FROM stock_changes 
                WHERE timestamp > ? AND notification_sent = 1
            """, (yesterday,))
            
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else 0
            
        except Exception:
            return 0
    
    async def _get_errors_count(self) -> int:
        """Get number of errors in last 24 hours."""
        try:
            db_path = Environment.get_database_url().replace("sqlite:///", "")
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            
            yesterday = datetime.utcnow() - timedelta(hours=24)
            cursor.execute("""
                SELECT COUNT(*)
                FROM monitoring_metrics 
                WHERE timestamp > ? AND success = 0
            """, (yesterday,))
            
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else 0
            
        except Exception:
            return 0
    
    def get_prometheus_metrics(self) -> str:
        """Generate Prometheus-compatible metrics."""
        try:
            # This would be populated by actual monitoring data
            metrics = [
                f"# HELP pokemon_bot_uptime_seconds Bot uptime in seconds",
                f"# TYPE pokemon_bot_uptime_seconds gauge",
                f"pokemon_bot_uptime_seconds {time.time() - self.start_time}",
                "",
                f"# HELP pokemon_bot_products_total Total number of monitored products",
                f"# TYPE pokemon_bot_products_total gauge",
                f"pokemon_bot_products_total {self.metrics.get('products_monitored', 0)}",
                "",
                f"# HELP pokemon_bot_success_rate Success rate of monitoring checks",
                f"# TYPE pokemon_bot_success_rate gauge",
                f"pokemon_bot_success_rate {self.metrics.get('success_rate', 0) / 100}",
                "",
                f"# HELP pokemon_bot_response_time_seconds Average response time",
                f"# TYPE pokemon_bot_response_time_seconds gauge",
                f"pokemon_bot_response_time_seconds {self.metrics.get('avg_response_time', 0)}",
                "",
                f"# HELP pokemon_bot_notifications_total Total notifications sent",
                f"# TYPE pokemon_bot_notifications_total counter",
                f"pokemon_bot_notifications_total {self.metrics.get('notifications_sent_24h', 0)}",
                "",
                f"# HELP pokemon_bot_errors_total Total errors encountered",
                f"# TYPE pokemon_bot_errors_total counter",
                f"pokemon_bot_errors_total {self.metrics.get('errors_24h', 0)}",
                "",
                f"# HELP pokemon_bot_memory_usage_bytes Memory usage in bytes",
                f"# TYPE pokemon_bot_memory_usage_bytes gauge",
                f"pokemon_bot_memory_usage_bytes {self.metrics.get('memory_usage_mb', 0) * 1024 * 1024}",
            ]
            
            return "\n".join(metrics)
            
        except Exception as e:
            self.logger.error(f"Failed to generate Prometheus metrics: {e}")
            return ""
    
    async def check_alerts(self):
        """Check for alert conditions and send notifications."""
        if not self.config.get("alerting", {}).get("enabled", False):
            return
        
        try:
            health = await self.get_health_status()
            current_time = datetime.utcnow()
            
            # Check alert rules
            rules = self.config.get("alerting", {}).get("rules", [])
            
            for rule in rules:
                alert_name = rule["name"]
                condition = rule["condition"]
                severity = rule["severity"]
                cooldown = rule.get("cooldown", 300)
                message = rule["message"]
                
                # Check if alert is in cooldown
                last_alert = self.last_alert_times.get(alert_name)
                if last_alert and (current_time - last_alert).total_seconds() < cooldown:
                    continue
                
                # Evaluate condition (simplified - would need proper expression parser)
                should_alert = False
                
                if "error_rate >" in condition:
                    threshold = float(condition.split(">")[1].strip())
                    if health.metrics.get("errors_24h", 0) > threshold:
                        should_alert = True
                        
                elif "success_rate <" in condition:
                    threshold = float(condition.split("<")[1].strip())
                    if health.metrics.get("success_rate", 100) < threshold:
                        should_alert = True
                        
                elif "avg_response_time >" in condition:
                    threshold = float(condition.split(">")[1].strip())
                    if health.metrics.get("avg_response_time", 0) > threshold:
                        should_alert = True
                        
                elif "memory_usage >" in condition:
                    threshold = float(condition.split(">")[1].strip())
                    if health.metrics.get("memory_usage_mb", 0) > threshold:
                        should_alert = True
                        
                elif "uptime_status == false" in condition:
                    if health.status == "unhealthy":
                        should_alert = True
                
                if should_alert:
                    # Format message with actual values
                    formatted_message = message.format(**health.metrics)
                    
                    # Create alert
                    alert = Alert(
                        name=alert_name,
                        severity=severity,
                        message=formatted_message,
                        timestamp=current_time,
                        cooldown=cooldown
                    )
                    
                    # Send alert
                    await self._send_alert(alert)
                    
                    # Update last alert time
                    self.last_alert_times[alert_name] = current_time
                    
        except Exception as e:
            self.logger.error(f"Alert checking failed: {e}")
    
    async def _send_alert(self, alert: Alert):
        """Send alert notification."""
        try:
            alert_config = self.config.get("alerting", {})
            channels = alert_config.get("channels", {})
            
            # Discord alerts
            if channels.get("discord", {}).get("enabled", False):
                await self._send_discord_alert(alert, channels["discord"])
            
            # Email alerts
            if channels.get("email", {}).get("enabled", False):
                await self._send_email_alert(alert, channels["email"])
            
            # Webhook alerts
            if channels.get("webhook", {}).get("enabled", False):
                await self._send_webhook_alert(alert, channels["webhook"])
                
            self.logger.info(f"Alert sent: {alert.name} - {alert.message}")
            
        except Exception as e:
            self.logger.error(f"Failed to send alert: {e}")
    
    async def _send_discord_alert(self, alert: Alert, config: Dict[str, Any]):
        """Send alert to Discord channel."""
        # This would integrate with actual Discord client
        self.logger.info(f"Discord alert: {alert.message}")
    
    async def _send_email_alert(self, alert: Alert, config: Dict[str, Any]):
        """Send alert via email."""
        # This would integrate with SMTP client
        self.logger.info(f"Email alert: {alert.message}")
    
    async def _send_webhook_alert(self, alert: Alert, config: Dict[str, Any]):
        """Send alert to webhook endpoint."""
        # This would send HTTP POST to webhook URL
        self.logger.info(f"Webhook alert: {alert.message}")
    
    async def generate_daily_report(self) -> Dict[str, Any]:
        """Generate daily monitoring report."""
        try:
            health = await self.get_health_status()
            
            # Get historical data for trends
            yesterday = datetime.utcnow() - timedelta(days=1)
            
            report = {
                "date": datetime.utcnow().date().isoformat(),
                "summary": {
                    "uptime_percentage": min(100, (health.uptime / 86400) * 100),
                    "total_products_monitored": health.metrics.get("products_monitored", 0),
                    "notifications_sent": health.metrics.get("notifications_sent_24h", 0),
                    "success_rate": health.metrics.get("success_rate", 0),
                    "avg_response_time": health.metrics.get("avg_response_time", 0),
                    "total_errors": health.metrics.get("errors_24h", 0)
                },
                "performance": {
                    "peak_memory_usage": health.metrics.get("memory_usage_mb", 0),
                    "avg_cpu_usage": health.metrics.get("cpu_usage_percent", 0),
                    "database_size_mb": health.database.get("size_mb", 0)
                },
                "alerts": {
                    "total_alerts": len(self.alerts),
                    "critical_alerts": len([a for a in self.alerts.values() if a.severity == "critical"]),
                    "warning_alerts": len([a for a in self.alerts.values() if a.severity == "warning"])
                }
            }
            
            return report
            
        except Exception as e:
            self.logger.error(f"Failed to generate daily report: {e}")
            return {}
    
    async def start_monitoring(self):
        """Start the monitoring service."""
        self.logger.info("Starting monitoring service")
        
        # Start monitoring tasks
        tasks = [
            self._health_check_loop(),
            self._metrics_collection_loop(),
            self._alert_check_loop()
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _health_check_loop(self):
        """Continuous health checking."""
        interval = self.config.get("health_check", {}).get("interval", 30)
        
        while True:
            try:
                health = await self.get_health_status()
                self.metrics.update(health.metrics)
                await asyncio.sleep(interval)
            except Exception as e:
                self.logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(interval)
    
    async def _metrics_collection_loop(self):
        """Continuous metrics collection."""
        interval = self.config.get("metrics", {}).get("collection_interval", 60)
        
        while True:
            try:
                # Collect and store metrics
                await self._collect_metrics()
                await asyncio.sleep(interval)
            except Exception as e:
                self.logger.error(f"Metrics collection loop error: {e}")
                await asyncio.sleep(interval)
    
    async def _alert_check_loop(self):
        """Continuous alert checking."""
        interval = 60  # Check alerts every minute
        
        while True:
            try:
                await self.check_alerts()
                await asyncio.sleep(interval)
            except Exception as e:
                self.logger.error(f"Alert check loop error: {e}")
                await asyncio.sleep(interval)
    
    async def _collect_metrics(self):
        """Collect and store metrics."""
        try:
            health = await self.get_health_status()
            
            # Store metrics in database for historical analysis
            db_path = Environment.get_database_url().replace("sqlite:///", "")
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            
            # Create metrics table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    uptime REAL,
                    memory_usage_mb REAL,
                    cpu_usage_percent REAL,
                    success_rate REAL,
                    avg_response_time REAL,
                    products_monitored INTEGER,
                    notifications_sent INTEGER,
                    errors_count INTEGER
                )
            """)
            
            # Insert current metrics
            cursor.execute("""
                INSERT INTO system_metrics (
                    uptime, memory_usage_mb, cpu_usage_percent, success_rate,
                    avg_response_time, products_monitored, notifications_sent, errors_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                health.uptime,
                health.metrics.get("memory_usage_mb", 0),
                health.metrics.get("cpu_usage_percent", 0),
                health.metrics.get("success_rate", 0),
                health.metrics.get("avg_response_time", 0),
                health.metrics.get("products_monitored", 0),
                health.metrics.get("notifications_sent_24h", 0),
                health.metrics.get("errors_24h", 0)
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Failed to collect metrics: {e}")


# Global monitoring service instance
monitoring_service = MonitoringService()