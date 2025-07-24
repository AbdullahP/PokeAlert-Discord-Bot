"""
Health check endpoints for monitoring system status.

This module provides health check endpoints and status monitoring
for the Pokemon Discord Bot system.
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from aiohttp import web
import socket
import threading

from .error_handler import error_handler
from ..config.config_manager import config
from ..database.connection import db


class HealthCheckServer:
    """Health check HTTP server for monitoring system status."""
    
    def __init__(self, host: str = '127.0.0.1', port: int = 8080):
        """Initialize health check server."""
        self.host = host
        self.port = port
        self.app = web.Application()
        self.logger = logging.getLogger(__name__)
        self.setup_routes()
        self._server = None
        self._runner = None
        self._thread = None
        self._running = False
    
    def setup_routes(self) -> None:
        """Set up HTTP routes for health checks."""
        self.app.add_routes([
            web.get('/health', self.health_handler),
            web.get('/health/detailed', self.detailed_health_handler),
            web.get('/metrics', self.metrics_handler),
            web.get('/status', self.status_handler)
        ])
    
    async def health_handler(self, request: web.Request) -> web.Response:
        """Simple health check endpoint."""
        health_status = error_handler.get_health_status()
        
        # Simple response with just the status
        response = {
            "status": health_status["status"],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        status_code = 200
        if health_status["status"] == "critical":
            status_code = 503  # Service Unavailable
        elif health_status["status"] in ("degraded", "warning"):
            status_code = 200  # Still OK but with warning
            
        return web.json_response(response, status=status_code)
    
    async def detailed_health_handler(self, request: web.Request) -> web.Response:
        """Detailed health check endpoint."""
        # Run a comprehensive health check
        health_data = await error_handler.run_health_check()
        
        status_code = 200
        if health_data["status"] == "critical":
            status_code = 503  # Service Unavailable
        elif health_data["status"] in ("degraded", "warning"):
            status_code = 200  # Still OK but with warning
            
        return web.json_response(health_data, status=status_code)
    
    async def metrics_handler(self, request: web.Request) -> web.Response:
        """Metrics endpoint for monitoring."""
        try:
            # Get error summary
            error_summary = error_handler.get_error_summary()
            
            # Get database metrics
            db_metrics = self._get_database_metrics()
            
            # Combine metrics
            metrics = {
                "timestamp": datetime.utcnow().isoformat(),
                "errors": error_summary,
                "database": db_metrics,
                "uptime": self._get_uptime()
            }
            
            return web.json_response(metrics)
        except Exception as e:
            self.logger.error(f"Error generating metrics: {e}")
            return web.json_response(
                {"error": "Failed to generate metrics", "message": str(e)},
                status=500
            )
    
    async def status_handler(self, request: web.Request) -> web.Response:
        """System status endpoint."""
        try:
            # Get monitoring status from database
            monitoring_status = self._get_monitoring_status()
            
            # Get health status
            health_status = error_handler.get_health_status()
            
            # Combine status information
            status = {
                "timestamp": datetime.utcnow().isoformat(),
                "system": {
                    "status": health_status["status"],
                    "components": health_status["components"]
                },
                "monitoring": monitoring_status
            }
            
            return web.json_response(status)
        except Exception as e:
            self.logger.error(f"Error generating status: {e}")
            return web.json_response(
                {"error": "Failed to generate status", "message": str(e)},
                status=500
            )
    
    def _get_database_metrics(self) -> Dict[str, Any]:
        """Get database metrics."""
        try:
            # Get product count
            cursor = db.execute("SELECT COUNT(*) FROM products")
            product_count = cursor.fetchone()[0]
            
            # Get active product count
            cursor = db.execute("SELECT COUNT(*) FROM products WHERE is_active = 1")
            active_product_count = cursor.fetchone()[0]
            
            # Get today's check count
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            cursor = db.execute(
                "SELECT COUNT(*) FROM monitoring_metrics WHERE timestamp >= ?",
                (today.isoformat(),)
            )
            checks_today = cursor.fetchone()[0]
            
            # Get success rate
            cursor = db.execute(
                "SELECT COUNT(*) FROM monitoring_metrics WHERE success = 1 AND timestamp >= ?",
                (today.isoformat(),)
            )
            successful_checks = cursor.fetchone()[0]
            
            success_rate = 100.0
            if checks_today > 0:
                success_rate = (successful_checks / checks_today) * 100
            
            return {
                "product_count": product_count,
                "active_product_count": active_product_count,
                "checks_today": checks_today,
                "success_rate": round(success_rate, 2)
            }
        except Exception as e:
            self.logger.error(f"Error getting database metrics: {e}")
            return {
                "error": str(e)
            }
    
    def _get_monitoring_status(self) -> Dict[str, Any]:
        """Get monitoring status from database."""
        try:
            # Get recent stock changes
            cursor = db.execute(
                """
                SELECT sc.*, ps.title, ps.price
                FROM stock_changes sc
                JOIN product_status ps ON sc.product_id = ps.product_id
                ORDER BY sc.timestamp DESC
                LIMIT 5
                """
            )
            
            recent_changes = []
            for row in cursor.fetchall():
                recent_changes.append({
                    "product_id": row["product_id"],
                    "title": row["title"],
                    "previous_status": row["previous_status"],
                    "current_status": row["current_status"],
                    "timestamp": row["timestamp"],
                    "notification_sent": bool(row["notification_sent"])
                })
            
            # Get error counts by type
            cursor = db.execute(
                """
                SELECT error_message, COUNT(*) as count
                FROM monitoring_metrics
                WHERE success = 0 AND timestamp >= ?
                GROUP BY error_message
                ORDER BY count DESC
                LIMIT 5
                """,
                ((datetime.utcnow() - timedelta(days=1)).isoformat(),)
            )
            
            error_counts = {}
            for row in cursor.fetchall():
                error_message = row["error_message"] or "Unknown error"
                error_counts[error_message] = row["count"]
            
            return {
                "recent_changes": recent_changes,
                "error_counts": error_counts
            }
        except Exception as e:
            self.logger.error(f"Error getting monitoring status: {e}")
            return {
                "error": str(e)
            }
    
    def _get_uptime(self) -> Dict[str, Any]:
        """Get system uptime information."""
        # This is a placeholder - in a real system you'd track actual start time
        return {
            "start_time": "Unknown",  # Would be replaced with actual start time
            "uptime_seconds": 0  # Would be replaced with actual uptime
        }
    
    async def start(self) -> None:
        """Start the health check server."""
        if self._running:
            return
            
        try:
            self._runner = web.AppRunner(self.app)
            await self._runner.setup()
            self._server = web.TCPSite(self._runner, self.host, self.port)
            await self._server.start()
            self._running = True
            self.logger.info(f"Health check server started on http://{self.host}:{self.port}")
        except Exception as e:
            self.logger.error(f"Failed to start health check server: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the health check server."""
        if not self._running:
            return
            
        try:
            if self._runner:
                await self._runner.cleanup()
            self._running = False
            self.logger.info("Health check server stopped")
        except Exception as e:
            self.logger.error(f"Error stopping health check server: {e}")
    
    def start_in_thread(self) -> None:
        """Start health check server in a separate thread."""
        if self._thread and self._thread.is_alive():
            return
            
        def run_server():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.start())
                loop.run_forever()
            except Exception as e:
                self.logger.error(f"Health check server thread error: {e}")
            finally:
                loop.run_until_complete(self.stop())
                loop.close()
        
        self._thread = threading.Thread(target=run_server, daemon=True)
        self._thread.start()
        self.logger.info("Health check server started in background thread")
    
    def stop_thread(self) -> None:
        """Stop the health check server thread."""
        if not self._thread or not self._thread.is_alive():
            return
            
        # Signal the thread to stop
        asyncio.run(self.stop())
        
        # Wait for thread to terminate
        self._thread.join(timeout=5)
        if self._thread.is_alive():
            self.logger.warning("Health check server thread did not terminate gracefully")
        else:
            self.logger.info("Health check server thread stopped")


# Global health check server instance
# Use Render's PORT environment variable or fallback
import os
render_port = int(os.getenv('PORT', '8080'))
health_server = HealthCheckServer(
    host=config.get('health_check.host', '0.0.0.0'),  # Render requires 0.0.0.0
    port=config.get('health_check.port', render_port)
)