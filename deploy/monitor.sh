#!/bin/bash
# Monitoring Script for PokeAlert Discord Bot

cd /opt/pokealert

echo "🤖 PokeAlert Discord Bot Status"
echo "================================"

# Check if containers are running
echo "📦 Container Status:"
docker-compose ps

echo ""
echo "💾 Resource Usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

echo ""
echo "📊 Health Check:"
curl -s http://localhost:8080/health | python3 -m json.tool || echo "❌ Health check failed"

echo ""
echo "📈 Recent Logs (last 10 lines):"
docker-compose logs --tail=10

echo ""
echo "💽 Disk Usage:"
df -h /opt/pokealert

echo ""
echo "🔧 Quick Commands:"
echo "  View logs:    docker-compose logs -f"
echo "  Restart bot:  docker-compose restart"
echo "  Update bot:   ./deploy/update.sh"
echo "  Stop bot:     docker-compose down"