#!/bin/bash

# Production Deployment Script for YoutubeTalker
# This script is executed on the production server after code is pulled from git

set -e  # Exit on any error

echo "========================================="
echo "🚀 YoutubeTalker Production Deployment"
echo "========================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_ROOT"

echo -e "${YELLOW}📂 Working directory: $PROJECT_ROOT${NC}"

# =======================
# 1. Stop running services
# =======================
echo ""
echo -e "${YELLOW}⏸️  Stopping services...${NC}"

# Stop backend service
if systemctl is-active --quiet youtubetalker-backend; then
    sudo systemctl stop youtubetalker-backend
    echo "✅ Backend service stopped"
else
    echo "ℹ️  Backend service was not running"
fi

# Stop frontend service
if systemctl is-active --quiet youtubetalker-frontend; then
    sudo systemctl stop youtubetalker-frontend
    echo "✅ Frontend service stopped"
else
    echo "ℹ️  Frontend service was not running"
fi

# =======================
# 2. Backend deployment
# =======================
echo ""
echo -e "${YELLOW}🔧 Deploying backend...${NC}"

cd "$PROJECT_ROOT/backend"

# Activate or create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3.12 -m venv .venv
fi

source .venv/bin/activate

# Install/update dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -e .
pip install psycopg2-binary  # Ensure PostgreSQL driver is installed

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

echo -e "${GREEN}✅ Backend deployed${NC}"

# =======================
# 3. Frontend deployment
# =======================
echo ""
echo -e "${YELLOW}🎨 Deploying frontend...${NC}"

cd "$PROJECT_ROOT/frontend"

# Install dependencies
echo "Installing frontend dependencies..."
npm ci --production=false

# Build frontend
echo "Building frontend..."
npm run build

echo -e "${GREEN}✅ Frontend deployed${NC}"

# =======================
# 4. Docker services
# =======================
echo ""
echo -e "${YELLOW}🐳 Managing Docker services...${NC}"

cd "$PROJECT_ROOT"

# Start Docker Compose services (PostgreSQL, Qdrant)
if [ -f "docker-compose.yml" ]; then
    echo "Starting Docker services..."
    docker compose up -d postgres qdrant

    # Wait for services to be healthy
    echo "Waiting for services to be healthy..."
    sleep 5

    echo -e "${GREEN}✅ Docker services started${NC}"
else
    echo -e "${RED}⚠️  docker-compose.yml not found${NC}"
fi

# =======================
# 5. Start services
# =======================
echo ""
echo -e "${YELLOW}▶️  Starting services...${NC}"

# Start backend service
sudo systemctl start youtubetalker-backend
sudo systemctl enable youtubetalker-backend

# Wait a moment for backend to start
sleep 3

# Start frontend service
sudo systemctl start youtubetalker-frontend
sudo systemctl enable youtubetalker-frontend

echo -e "${GREEN}✅ Services started${NC}"

# =======================
# 6. Health checks
# =======================
echo ""
echo -e "${YELLOW}🏥 Running health checks...${NC}"

# Check backend
sleep 5
backend_status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health || echo "000")
if [ "$backend_status" -eq 200 ]; then
    echo -e "${GREEN}✅ Backend is healthy (HTTP $backend_status)${NC}"
else
    echo -e "${RED}❌ Backend health check failed (HTTP $backend_status)${NC}"
    echo "Check logs: sudo journalctl -u youtubetalker-backend -n 50"
fi

# Check frontend
sleep 2
frontend_status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:4321 || echo "000")
if [ "$frontend_status" -eq 200 ]; then
    echo -e "${GREEN}✅ Frontend is healthy (HTTP $frontend_status)${NC}"
else
    echo -e "${RED}❌ Frontend health check failed (HTTP $frontend_status)${NC}"
    echo "Check logs: sudo journalctl -u youtubetalker-frontend -n 50"
fi

# =======================
# 7. Summary
# =======================
echo ""
echo "========================================="
echo -e "${GREEN}🎉 Deployment completed!${NC}"
echo "========================================="
echo ""
echo "Service status:"
sudo systemctl status youtubetalker-backend --no-pager | head -3
sudo systemctl status youtubetalker-frontend --no-pager | head -3
echo ""
echo "To view logs:"
echo "  Backend:  sudo journalctl -u youtubetalker-backend -f"
echo "  Frontend: sudo journalctl -u youtubetalker-frontend -f"
echo ""
