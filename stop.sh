#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  YoutubeTalker - Stopping Services${NC}"
echo -e "${BLUE}========================================${NC}\n"

STOP_DOCKER=false

# Check for --all flag
if [ "$1" == "--all" ]; then
    STOP_DOCKER=true
    print_info "Stopping all services including Docker containers"
else
    print_info "Stopping backend and frontend (use --all to stop Docker too)"
fi

# Stop backend
echo -e "\n${BLUE}[1/3]${NC} Stopping backend..."
if [ -f /tmp/youtube-talker-backend.pid ]; then
    BACKEND_PID=$(cat /tmp/youtube-talker-backend.pid)
    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        kill $BACKEND_PID
        sleep 2
        if ps -p $BACKEND_PID > /dev/null 2>&1; then
            print_warn "Forcing backend shutdown..."
            kill -9 $BACKEND_PID
        fi
        print_status "Backend stopped (PID: $BACKEND_PID)"
    else
        print_warn "Backend process not running"
    fi
    rm -f /tmp/youtube-talker-backend.pid
else
    print_warn "Backend PID file not found"
fi

# Also kill any remaining uvicorn processes
pkill -f "uvicorn app.main:app" 2>/dev/null && print_info "Cleaned up any remaining backend processes"

# Stop frontend
echo -e "\n${BLUE}[2/3]${NC} Stopping frontend..."
if [ -f /tmp/youtube-talker-frontend.pid ]; then
    FRONTEND_PID=$(cat /tmp/youtube-talker-frontend.pid)
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        kill $FRONTEND_PID
        sleep 2
        if ps -p $FRONTEND_PID > /dev/null 2>&1; then
            print_warn "Forcing frontend shutdown..."
            kill -9 $FRONTEND_PID
        fi
        print_status "Frontend stopped (PID: $FRONTEND_PID)"
    else
        print_warn "Frontend process not running"
    fi
    rm -f /tmp/youtube-talker-frontend.pid
else
    print_warn "Frontend PID file not found"
fi

# Also kill any remaining astro dev processes
pkill -f "astro dev" 2>/dev/null && print_info "Cleaned up any remaining frontend processes"

# Stop Docker services
echo -e "\n${BLUE}[3/3]${NC} Docker services..."
if [ "$STOP_DOCKER" = true ]; then
    docker compose down
    print_status "Docker containers stopped (PostgreSQL + Qdrant)"
else
    print_info "Docker containers still running (use --all to stop)"
fi

# Clean up log files (optional)
echo -e "\n${BLUE}Clean up logs?${NC}"
read -p "Remove log files? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f /tmp/youtube-talker-backend.log
    rm -f /tmp/youtube-talker-frontend.log
    print_status "Log files removed"
fi

# Summary
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  ✅ Services stopped${NC}"
echo -e "${GREEN}========================================${NC}\n"

if [ "$STOP_DOCKER" = false ]; then
    echo -e "${YELLOW}Note:${NC} PostgreSQL and Qdrant are still running."
    echo -e "      To stop them, run: ${BLUE}./stop.sh --all${NC}\n"
fi

echo -e "${BLUE}To start again:${NC} ${GREEN}./dev.sh${NC}\n"
