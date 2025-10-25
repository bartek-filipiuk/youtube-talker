#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print status
print_pass() {
    echo -e "${GREEN}✅${NC} $1"
}

print_fail() {
    echo -e "${RED}❌${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}⚠️${NC}  $1"
}

print_info() {
    echo -e "${BLUE}ℹ️${NC}  $1"
}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  🔍 YoutubeTalker - Health Check${NC}"
echo -e "${BLUE}========================================${NC}\n"

FAILED=0

# Check Docker
echo -e "${BLUE}Checking Docker services...${NC}"
if command -v docker &> /dev/null && docker info &> /dev/null; then
    print_pass "Docker is running"
else
    print_fail "Docker is not running"
    FAILED=1
fi

# Check PostgreSQL
if docker compose ps | grep -q "postgres.*healthy"; then
    print_pass "PostgreSQL is healthy (port 5435)"

    # Try to connect
    if docker exec youtube-talker-postgres pg_isready -U postgres &> /dev/null; then
        print_info "Database connection verified"
    fi
else
    print_fail "PostgreSQL is not healthy"
    FAILED=1
fi

# Check Qdrant
if docker compose ps | grep -q "qdrant.*healthy"; then
    print_pass "Qdrant is healthy (port 6335)"

    # Try HTTP request
    if curl -s http://localhost:6335/collections &> /dev/null; then
        print_info "Qdrant API responding"
    fi
else
    print_fail "Qdrant is not healthy"
    FAILED=1
fi

# Check Backend
echo -e "\n${BLUE}Checking Backend API...${NC}"
if curl -s http://localhost:8000/api/health &> /dev/null; then
    print_pass "Backend API is responding (http://localhost:8000)"

    # Check specific health endpoints
    DB_HEALTH=$(curl -s http://localhost:8000/api/health/db 2>/dev/null)
    if [ $? -eq 0 ]; then
        print_info "Database health endpoint: OK"
    fi

    QDRANT_HEALTH=$(curl -s http://localhost:8000/api/health/qdrant 2>/dev/null)
    if [ $? -eq 0 ]; then
        print_info "Qdrant health endpoint: OK"
    fi
else
    print_fail "Backend API is not responding"
    print_info "Check logs: tail -f /tmp/youtube-talker-backend.log"
    FAILED=1
fi

# Check Frontend
echo -e "\n${BLUE}Checking Frontend...${NC}"
if curl -s http://localhost:4321 &> /dev/null; then
    print_pass "Frontend is accessible (http://localhost:4321)"
else
    print_fail "Frontend is not accessible"
    print_info "Check logs: tail -f /tmp/youtube-talker-frontend.log"
    FAILED=1
fi

# Check process PIDs
echo -e "\n${BLUE}Checking Running Processes...${NC}"
if [ -f /tmp/youtube-talker-backend.pid ]; then
    BACKEND_PID=$(cat /tmp/youtube-talker-backend.pid)
    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        print_pass "Backend process running (PID: $BACKEND_PID)"
    else
        print_fail "Backend process not found (PID: $BACKEND_PID)"
        FAILED=1
    fi
else
    print_warn "Backend PID file not found (may not be started via dev.sh)"
fi

if [ -f /tmp/youtube-talker-frontend.pid ]; then
    FRONTEND_PID=$(cat /tmp/youtube-talker-frontend.pid)
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        print_pass "Frontend process running (PID: $FRONTEND_PID)"
    else
        print_fail "Frontend process not found (PID: $FRONTEND_PID)"
        FAILED=1
    fi
else
    print_warn "Frontend PID file not found (may not be started via dev.sh)"
fi

# Summary
echo -e "\n${BLUE}========================================${NC}"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}  🎉 All systems operational!${NC}"
    echo -e "${GREEN}========================================${NC}\n"

    echo -e "${BLUE}📍 Quick Access:${NC}"
    echo -e "  Frontend:    ${GREEN}http://localhost:4321${NC}"
    echo -e "  Backend:     ${GREEN}http://localhost:8000${NC}"
    echo -e "  API Docs:    ${GREEN}http://localhost:8000/docs${NC}"
    echo -e "  Qdrant:      ${GREEN}http://localhost:6335/dashboard${NC}\n"

    exit 0
else
    echo -e "${RED}  ⚠️  Some services are not healthy${NC}"
    echo -e "${RED}========================================${NC}\n"

    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo -e "  1. Check Docker logs:   ${BLUE}docker compose logs${NC}"
    echo -e "  2. Check backend logs:  ${BLUE}tail -f /tmp/youtube-talker-backend.log${NC}"
    echo -e "  3. Check frontend logs: ${BLUE}tail -f /tmp/youtube-talker-frontend.log${NC}"
    echo -e "  4. Restart services:    ${BLUE}./stop.sh && ./dev.sh${NC}\n"

    exit 1
fi
