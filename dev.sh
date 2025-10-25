#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project paths
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  YoutubeTalker - Development Startup${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Function to print status
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check prerequisites
echo -e "${BLUE}[1/7]${NC} Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! docker info &> /dev/null; then
    print_error "Docker is not running. Please start Docker Desktop."
    exit 1
fi
print_status "Docker is running"

# Check Python
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3.11+."
    exit 1
fi
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
print_status "Python $PYTHON_VERSION detected"

# Check Node
if ! command -v node &> /dev/null; then
    print_error "Node.js is not installed. Please install Node.js 18+."
    exit 1
fi
NODE_VERSION=$(node --version)
print_status "Node.js $NODE_VERSION detected"

# Check backend .env
if [ ! -f "$BACKEND_DIR/.env" ]; then
    print_warning "Backend .env file not found. Copying from .env.example..."
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    print_info "Please edit backend/.env with your API keys before continuing."
    exit 1
fi
print_status "Backend .env found"

# Check frontend .env
if [ ! -f "$FRONTEND_DIR/.env" ]; then
    print_warning "Frontend .env file not found. Copying from .env.example..."
    cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"
    print_status "Frontend .env created"
fi
print_status "Frontend .env found"

# Start Docker services
echo -e "\n${BLUE}[2/7]${NC} Starting Docker services (PostgreSQL + Qdrant)..."
cd "$PROJECT_ROOT"
docker compose up -d

# Wait for services to be healthy
print_info "Waiting for services to be ready (max 30 seconds)..."
for i in {1..30}; do
    if docker compose ps | grep -q "postgres.*healthy" && docker compose ps | grep -q "qdrant.*healthy"; then
        print_status "PostgreSQL and Qdrant are healthy"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "Services failed to become healthy after 30 seconds"
        print_info "Check logs with: docker compose logs"
        exit 1
    fi
    sleep 1
done

# Setup backend
echo -e "\n${BLUE}[3/7]${NC} Setting up backend..."
cd "$BACKEND_DIR"

# Check if venv exists
if [ ! -d ".venv" ]; then
    print_info "Creating Python virtual environment..."
    python3 -m venv .venv
    print_status "Virtual environment created"
fi

# Activate venv and install dependencies
source .venv/bin/activate

if [ ! -f ".venv/.dependencies_installed" ]; then
    print_info "Installing backend dependencies (this may take a minute)..."
    pip install -q -e ".[dev]"
    touch .venv/.dependencies_installed
    print_status "Backend dependencies installed"
else
    print_status "Backend dependencies already installed"
fi

# Run migrations
print_info "Running database migrations..."
.venv/bin/alembic upgrade head &> /dev/null || {
    print_warning "Migration failed - this is OK for first run"
}
print_status "Database migrations complete"

# Setup Qdrant collection
if [ -f "scripts/setup_qdrant.py" ]; then
    print_info "Setting up Qdrant collection..."
    python scripts/setup_qdrant.py &> /dev/null || print_warning "Qdrant setup skipped (may already exist)"
    print_status "Qdrant collection ready"
fi

# Setup frontend
echo -e "\n${BLUE}[4/7]${NC} Setting up frontend..."
cd "$FRONTEND_DIR"

if [ ! -d "node_modules" ]; then
    print_info "Installing frontend dependencies (this may take a minute)..."
    npm install --silent
    print_status "Frontend dependencies installed"
else
    print_status "Frontend dependencies already installed"
fi

# Start backend server
echo -e "\n${BLUE}[5/7]${NC} Starting backend server..."
cd "$BACKEND_DIR"
source .venv/bin/activate

# Kill any existing backend process
pkill -f "uvicorn app.main:app" 2>/dev/null || true

# Start backend in background
nohup .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > /tmp/youtube-talker-backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > /tmp/youtube-talker-backend.pid

print_info "Backend starting (PID: $BACKEND_PID)..."
sleep 3

# Check if backend is running
if ps -p $BACKEND_PID > /dev/null; then
    print_status "Backend server started at http://localhost:8000"
else
    print_error "Backend failed to start. Check logs: tail -f /tmp/youtube-talker-backend.log"
    exit 1
fi

# Start frontend server
echo -e "\n${BLUE}[6/7]${NC} Starting frontend server..."
cd "$FRONTEND_DIR"

# Kill any existing frontend process
pkill -f "astro dev" 2>/dev/null || true

# Start frontend in background
nohup npm run dev > /tmp/youtube-talker-frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > /tmp/youtube-talker-frontend.pid

print_info "Frontend starting (PID: $FRONTEND_PID)..."
sleep 5

# Check if frontend is running
if ps -p $FRONTEND_PID > /dev/null; then
    print_status "Frontend server started at http://localhost:4321"
else
    print_error "Frontend failed to start. Check logs: tail -f /tmp/youtube-talker-frontend.log"
    exit 1
fi

# Summary
echo -e "\n${BLUE}[7/7]${NC} Startup complete!"
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  🎉 All services are running!${NC}"
echo -e "${GREEN}========================================${NC}\n"

echo -e "${BLUE}📍 Access Points:${NC}"
echo -e "  ${GREEN}Frontend:${NC}      http://localhost:4321"
echo -e "  ${GREEN}Backend API:${NC}   http://localhost:8000"
echo -e "  ${GREEN}API Docs:${NC}      http://localhost:8000/docs"
echo -e "  ${GREEN}Qdrant:${NC}        http://localhost:6335/dashboard"
echo -e "  ${GREEN}PostgreSQL:${NC}    localhost:5435\n"

echo -e "${BLUE}📋 Useful Commands:${NC}"
echo -e "  ${YELLOW}View backend logs:${NC}   tail -f /tmp/youtube-talker-backend.log"
echo -e "  ${YELLOW}View frontend logs:${NC}  tail -f /tmp/youtube-talker-frontend.log"
echo -e "  ${YELLOW}Health check:${NC}        ./health-check.sh"
echo -e "  ${YELLOW}Stop services:${NC}       ./stop.sh\n"

echo -e "${GREEN}✨ Happy coding!${NC}\n"
