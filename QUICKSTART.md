# YoutubeTalker - Quick Start Guide

**Get the full stack running in 2 minutes!**

---

## 🚀 One-Command Startup (Recommended)

```bash
./dev.sh
```

That's it! The script will:
- ✅ Check all prerequisites
- ✅ Start PostgreSQL + Qdrant (Docker)
- ✅ Run database migrations
- ✅ Set up Qdrant collection
- ✅ Start backend API (http://localhost:8000)
- ✅ Start frontend (http://localhost:4321)

**Access Points:**
- **Frontend:** http://localhost:4321
- **Backend API:** http://localhost:8000
- **API Docs (Swagger):** http://localhost:8000/docs
- **Qdrant Dashboard:** http://localhost:6335/dashboard

---

## 📋 Prerequisites

Before running `./dev.sh`, ensure you have:

- [x] **Docker** (for PostgreSQL + Qdrant)
- [x] **Python 3.11+** (check: `python3 --version`)
- [x] **Node.js 18+** (check: `node --version`)
- [x] **Backend .env file** (copy from `backend/.env.example`)
- [x] **Frontend .env file** (copy from `frontend/.env.example`)

**API Keys Required (in backend/.env):**
- `OPENROUTER_API_KEY` - Get from https://openrouter.ai
- `OPENAI_API_KEY` - Get from https://platform.openai.com
- `SUPADATA_API_KEY` - Get from https://supadata.ai

---

## 🛠️ Manual Startup (If Script Fails)

### Step 1: Start Docker Services

```bash
# From project root
docker compose up -d

# Verify services are running
docker compose ps
```

### Step 2: Setup Backend

```bash
cd backend

# Activate virtual environment
source .venv/bin/activate

# Install dependencies (first time only)
pip install -e ".[dev]"

# Copy .env.example to .env (first time only)
cp .env.example .env
# Then edit .env with your API keys

# Run migrations (first time only)
.venv/bin/alembic upgrade head

# Setup Qdrant collection (first time only)
python scripts/setup_qdrant.py

# Start backend server
.venv/bin/uvicorn app.main:app --reload
```

Backend will be available at http://localhost:8000

### Step 3: Setup Frontend

```bash
# Open a new terminal
cd frontend

# Install dependencies (first time only)
npm install

# Copy .env.example to .env (first time only)
cp .env.example .env

# Start frontend dev server
npm run dev
```

Frontend will be available at http://localhost:4321

---

## 🩺 Health Check

Run the health check script to verify all services:

```bash
./health-check.sh
```

Expected output:
```
🔍 YoutubeTalker - Health Check

✅ Docker is running
✅ PostgreSQL is healthy (port 5435)
✅ Qdrant is healthy (port 6335)
✅ Backend API is responding
✅ Frontend is accessible

🎉 All systems operational!
```

---

## 🛑 Stopping Services

```bash
# Stop backend + frontend (keeps Docker running)
./stop.sh

# Stop everything including Docker
./stop.sh --all
```

Or manually:
```bash
# Stop backend/frontend (Ctrl+C in their terminals)

# Stop Docker services
docker compose down
```

---

## 🧪 Testing the App

Once everything is running:

1. **Open Frontend:** http://localhost:4321
2. **Register a new user** (any email + password)
3. **Login** with your credentials
4. **Create a conversation** (should auto-create and redirect)
5. **Try the chat** (websocket connection should establish)

**Test YouTube Ingestion:**
1. Get a test video URL (e.g., https://www.youtube.com/watch?v=dQw4w9WgXcQ)
2. Use the API to ingest: `POST http://localhost:8000/api/transcripts/ingest`
   ```bash
   curl -X POST http://localhost:8000/api/transcripts/ingest \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
   ```
3. Ask questions about the video in the chat

---

## 🐛 Troubleshooting

### Issue: "Docker is not running"
```bash
# Start Docker Desktop (macOS/Windows)
# Or start Docker daemon (Linux)
sudo systemctl start docker
```

### Issue: "Port 5435 already in use"
```bash
# Find what's using the port
lsof -i :5435

# Kill the process or change port in docker-compose.yml
```

### Issue: "Backend won't start - ModuleNotFoundError"
```bash
cd backend
source .venv/bin/activate
pip install -e ".[dev]"
```

### Issue: "Frontend shows 'Failed to fetch'"
- Check backend is running on port 8000
- Check `frontend/.env` has `PUBLIC_API_BASE=http://localhost:8000/api`
- Check browser console for CORS errors

### Issue: "Database migration errors"
```bash
cd backend
source .venv/bin/activate
alembic downgrade base  # Reset
alembic upgrade head    # Reapply
```

### Issue: "Qdrant collection not found"
```bash
cd backend
source .venv/bin/activate
python scripts/setup_qdrant.py
```

---

## 📚 Additional Documentation

- **Backend Details:** See `backend/README.md`
- **Frontend Details:** See `frontend/README.md`
- **Development Workflow:** See `DEVELOPMENT_RULES.md`
- **Full Handoff Checklist:** See `PROJECT_FLOW_DOCS/HANDOFF.md`
- **Database Schema:** See `PROJECT_FLOW_DOCS/DATABASE_SCHEMA.md`

---

## 🎯 Quick Commands Reference

```bash
# Start everything
./dev.sh

# Check health
./health-check.sh

# Stop everything
./stop.sh --all

# View logs
docker compose logs -f postgres
docker compose logs -f qdrant

# Run tests
cd backend && pytest tests/ --cov=app

# Database operations
cd backend
.venv/bin/alembic upgrade head      # Apply migrations
.venv/bin/alembic revision --autogenerate -m "msg"  # Create migration
python scripts/seed_database.py     # Seed test data

# Code quality
cd backend
black app/ tests/                   # Format
ruff check app/ tests/              # Lint
```

---

**Need Help?**
- Check `TROUBLESHOOTING.md` for common issues
- Review API docs: http://localhost:8000/docs
- Check Docker logs: `docker compose logs`

**Last Updated:** 2025-10-24
