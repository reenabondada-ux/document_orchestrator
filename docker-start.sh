#!/bin/bash
# Quick start script for document orchestrator in Docker
#
# Usage:
#   ./docker-start.sh       # Start services
#   ./docker-start.sh logs  # View logs
#   ./docker-start.sh stop  # Stop services
#   ./docker-start.sh clean # Stop and remove volumes

set -euo pipefail

cd "$(dirname "$0")"

ACTION="${1:-start}"

case "$ACTION" in
  start)
    echo "🚀 Starting document orchestrator in Docker..."
    docker compose up -d
    echo ""
    echo "✅ Services started!"
    echo ""
    echo "📊 API: http://localhost:8010/docs"
    echo "💾 Database: postgresql://postgres_user:postgres_pass@localhost:5432/postgres_db"
    echo ""
    echo "To view logs: ./docker-start.sh logs"
    ;;
  
  logs)
    echo "📋 Streaming logs (Ctrl+C to exit)..."
    docker compose logs -f
    ;;
  
  stop)
    echo "🛑 Stopping document orchestrator..."
    docker compose down
    echo "✅ Stopped"
    ;;
  
  clean)
    echo "🧹 Stopping and removing volumes (clean slate)..."
    docker compose down -v
    echo "✅ Cleaned"
    ;;
  
  rebuild)
    echo "🔨 Rebuilding and restarting..."
    docker compose up -d --build
    echo "✅ Rebuilt and restarted"
    ;;
  
  *)
    echo "Usage: $0 {start|logs|stop|clean|rebuild}"
    echo ""
    echo "  start   - Start services (default)"
    echo "  logs    - View streaming logs"
    echo "  stop    - Stop services (keep volumes)"
    echo "  clean   - Stop and remove volumes (fresh start)"
    echo "  rebuild - Rebuild images and restart"
    exit 1
    ;;
esac
