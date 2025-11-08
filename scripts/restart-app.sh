#!/bin/bash

# YouTube Talker Application Restart Script
# This script safely restarts all application components in the correct order

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo ""
echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}🔄 YouTube Talker Application Restart${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

# =======================
# 1. Stop Application Services
# =======================
echo -e "${YELLOW}⏸️  Stopping application services...${NC}"

# Stop frontend service
if sudo systemctl is-active --quiet youtubetalker-frontend; then
    echo "  Stopping frontend service..."
    sudo systemctl stop youtubetalker-frontend
    echo -e "  ${GREEN}✓${NC} Frontend stopped"
else
    echo -e "  ${YELLOW}ℹ${NC}  Frontend was not running"
fi

# Stop backend service
if sudo systemctl is-active --quiet youtubetalker-backend; then
    echo "  Stopping backend service..."
    sudo systemctl stop youtubetalker-backend
    echo -e "  ${GREEN}✓${NC} Backend stopped"
else
    echo -e "  ${YELLOW}ℹ${NC}  Backend was not running"
fi

echo ""

# =======================
# 2. Restart Docker Services
# =======================
echo -e "${YELLOW}🐳 Restarting Docker services...${NC}"

cd "$PROJECT_ROOT"

# Restart PostgreSQL and Qdrant
docker compose restart postgres qdrant

# Wait for databases to be healthy
echo "  Waiting for databases to be healthy..."
sleep 10

# Check if containers are healthy
POSTGRES_STATUS=$(docker inspect --format='{{.State.Health.Status}}' youtube-talker-postgres 2>/dev/null || echo "unknown")
QDRANT_STATUS=$(docker inspect --format='{{.State.Health.Status}}' youtube-talker-qdrant 2>/dev/null || echo "unknown")

if [ "$POSTGRES_STATUS" = "healthy" ]; then
    echo -e "  ${GREEN}✓${NC} PostgreSQL is healthy"
else
    echo -e "  ${RED}✗${NC} PostgreSQL health: $POSTGRES_STATUS"
fi

if [ "$QDRANT_STATUS" = "healthy" ]; then
    echo -e "  ${GREEN}✓${NC} Qdrant is healthy"
else
    echo -e "  ${YELLOW}⚠${NC}  Qdrant health: $QDRANT_STATUS (may still be starting)"
fi

echo ""

# =======================
# 3. Start Application Services
# =======================
echo -e "${YELLOW}▶️  Starting application services...${NC}"

# Start backend service
echo "  Starting backend service..."
sudo systemctl start youtubetalker-backend
sleep 3

if sudo systemctl is-active --quiet youtubetalker-backend; then
    echo -e "  ${GREEN}✓${NC} Backend started"
else
    echo -e "  ${RED}✗${NC} Backend failed to start"
    echo "  Check logs: sudo journalctl -u youtubetalker-backend -n 50"
fi

# Start frontend service
echo "  Starting frontend service..."
sudo systemctl start youtubetalker-frontend
sleep 3

if sudo systemctl is-active --quiet youtubetalker-frontend; then
    echo -e "  ${GREEN}✓${NC} Frontend started"
else
    echo -e "  ${RED}✗${NC} Frontend failed to start"
    echo "  Check logs: sudo journalctl -u youtubetalker-frontend -n 50"
fi

echo ""

# =======================
# 4. Run Health Checks
# =======================
echo -e "${YELLOW}🏥 Running health checks...${NC}"

# Wait a bit for services to fully start
sleep 5

# Check backend health
BACKEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health 2>/dev/null || echo "000")
if [ "$BACKEND_STATUS" -eq 200 ]; then
    echo -e "  ${GREEN}✓${NC} Backend API is healthy (HTTP $BACKEND_STATUS)"
else
    echo -e "  ${RED}✗${NC} Backend health check failed (HTTP $BACKEND_STATUS)"
    echo "  Check logs: sudo journalctl -u youtubetalker-backend -n 50"
fi

# Check frontend health
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:4321 2>/dev/null || echo "000")
if [ "$FRONTEND_STATUS" -eq 200 ] || [ "$FRONTEND_STATUS" -eq 301 ] || [ "$FRONTEND_STATUS" -eq 302 ]; then
    echo -e "  ${GREEN}✓${NC} Frontend is healthy (HTTP $FRONTEND_STATUS)"
else
    echo -e "  ${RED}✗${NC} Frontend health check failed (HTTP $FRONTEND_STATUS)"
    echo "  Check logs: sudo journalctl -u youtubetalker-frontend -n 50"
fi

echo ""

# =======================
# 5. Summary
# =======================
echo -e "${BLUE}=========================================${NC}"
echo -e "${GREEN}✨ Restart Complete!${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

echo -e "${BLUE}Service Status:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
sudo systemctl status youtubetalker-backend --no-pager | head -3
echo ""
sudo systemctl status youtubetalker-frontend --no-pager | head -3
echo ""
docker ps --filter "name=youtube-talker" --format "table {{.Names}}\t{{.Status}}" | head -3

echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  View backend logs:   sudo journalctl -u youtubetalker-backend -f"
echo "  View frontend logs:  sudo journalctl -u youtubetalker-frontend -f"
echo "  View Docker logs:    docker compose logs -f"
echo "  Check health:        curl http://localhost:8000/api/health"
echo ""
