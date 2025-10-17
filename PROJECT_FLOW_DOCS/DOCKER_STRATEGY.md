# Docker Strategy & Deployment Architecture
## YoutubeTalker MVP

**Last Updated:** 2025-10-17

---

## Overview

This document defines the containerization strategy for YoutubeTalker, ensuring **local/production parity** while maintaining simplicity and best practices.

**Core Principle:** What runs in containers locally should run in containers in production (with minimal exceptions).

---

## Container Architecture

### What Goes in Containers

**Always Containerized (Local + Production):**
1. **PostgreSQL** - Database
2. **Qdrant** - Vector database
3. **Backend (FastAPI)** - API server

**Environment-Specific:**
- **Frontend (Astro):**
  - **Local:** Dev server in container (hot reload)
  - **Production:** Built static files served by Caddy (no container)

**Not Containerized:**
- **Caddy (Production only):** Runs on host as reverse proxy/web server
- **Local proxy:** Not needed (direct access to services)

---

## Why This Architecture?

### PostgreSQL & Qdrant in Containers
- **Isolation:** Database state isolated from host
- **Consistency:** Same versions in local/prod
- **Portability:** Easy to backup, migrate, restore
- **Simplicity:** No host-level database installation

### Backend in Container
- **Dependency isolation:** Python environment contained
- **Reproducibility:** Same runtime environment everywhere
- **Easy scaling:** Can run multiple instances in prod
- **Fast deployment:** Build once, deploy anywhere

### Frontend Deployment

**Local (Dev Server in Container):**
- Hot module reload for development
- Isolated Node.js environment
- Consistent dev experience

**Production (Static Build + Caddy on Host):**
- Astro builds to static HTML/CSS/JS
- No Node.js needed in production
- Caddy serves static files directly (very fast)
- Caddy on host simplifies SSL/TLS management
- Single reverse proxy for API + static files

### Caddy on Host (Production)

**Why not containerize Caddy:**
1. **SSL Certificate Management:** Easier to manage Let's Encrypt certs on host
2. **Port 80/443 Binding:** Direct binding to privileged ports without Docker networking complexity
3. **Configuration Flexibility:** Simple to update Caddyfile without rebuilding containers
4. **Standard Practice:** Most production servers run reverse proxy on host
5. **Logging:** Direct access to access logs on host filesystem

---

## Local Development Setup

### Docker Compose Configuration

**File:** `docker-compose.yml` (project root)

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    container_name: youtubetalker-postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: youtube_talker
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Qdrant Vector Database
  qdrant:
    image: qdrant/qdrant:latest
    container_name: youtubetalker-qdrant
    ports:
      - "6333:6333"  # REST API
      - "6334:6334"  # gRPC (optional)
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Backend API (FastAPI)
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    container_name: youtubetalker-backend
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:${POSTGRES_PASSWORD:-postgres}@postgres:5432/youtube_talker
      - QDRANT_URL=http://qdrant:6333
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - SUPADATA_API_KEY=${SUPADATA_API_KEY}
      - PYTHONUNBUFFERED=1
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app  # Hot reload
      - /app/.venv  # Prevent overwriting venv
    depends_on:
      postgres:
        condition: service_healthy
      qdrant:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  # Frontend (Astro Dev Server)
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    container_name: youtubetalker-frontend
    environment:
      - PUBLIC_API_URL=http://localhost:8000
    ports:
      - "4321:4321"
    volumes:
      - ./frontend:/app
      - /app/node_modules  # Prevent overwriting node_modules
    depends_on:
      - backend
    command: npm run dev -- --host 0.0.0.0

volumes:
  postgres_data:
    driver: local
  qdrant_data:
    driver: local
```

### Backend Dockerfile (Development)

**File:** `backend/Dockerfile.dev`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Command specified in docker-compose.yml
```

### Frontend Dockerfile (Development)

**File:** `frontend/Dockerfile.dev`

```dockerfile
FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy application code
COPY . .

# Expose port
EXPOSE 4321

# Command specified in docker-compose.yml
```

### Local Usage

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f backend
docker compose logs -f frontend

# Stop all services
docker compose down

# Rebuild after dependency changes
docker compose up -d --build

# Access services:
# - Frontend: http://localhost:4321
# - Backend API: http://localhost:8000
# - Backend Docs: http://localhost:8000/docs
# - Qdrant Dashboard: http://localhost:6333/dashboard
# - PostgreSQL: localhost:5432
```

---

## Production Deployment

### Architecture Diagram

```
Internet
   |
   | HTTPS (443)
   ↓
[Caddy on Host]
   |
   |-- /api/* → http://localhost:8000 (Backend Container)
   |-- /*     → Static files from /var/www/youtubetalker/dist
   |
   ↓ (Internal Docker Network)
   |
   |-- Backend Container :8000
   |      ↓
   |-- PostgreSQL Container :5432
   |-- Qdrant Container :6333
```

### Production Docker Compose

**File:** `docker-compose.prod.yml`

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: youtubetalker-postgres-prod
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: youtube_talker
    volumes:
      - /var/lib/youtubetalker/postgres:/var/lib/postgresql/data
    networks:
      - app-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 30s
      timeout: 10s
      retries: 3

  qdrant:
    image: qdrant/qdrant:latest
    container_name: youtubetalker-qdrant-prod
    volumes:
      - /var/lib/youtubetalker/qdrant:/qdrant/storage
    networks:
      - app-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    container_name: youtubetalker-backend-prod
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/youtube_talker
      - QDRANT_URL=http://qdrant:6333
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - SUPADATA_API_KEY=${SUPADATA_API_KEY}
      - ENVIRONMENT=production
    ports:
      - "127.0.0.1:8000:8000"  # Only localhost (Caddy proxy)
    depends_on:
      postgres:
        condition: service_healthy
      qdrant:
        condition: service_healthy
    networks:
      - app-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  app-network:
    driver: bridge
```

### Backend Dockerfile (Production)

**File:** `backend/Dockerfile.prod`

```dockerfile
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production image
FROM python:3.11-slim

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run with production server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Frontend Build Process

**Build static files locally or in CI/CD:**

```bash
cd frontend
npm install
npm run build
# Output: frontend/dist/
```

**Deploy to server:**

```bash
# Copy built files to server
rsync -avz frontend/dist/ user@server:/var/www/youtubetalker/dist/
```

### Caddy Configuration (Host)

**File:** `/etc/caddy/Caddyfile`

```
youtubetalker.com {
    # API reverse proxy
    handle /api/* {
        reverse_proxy localhost:8000
    }

    # WebSocket support
    handle /api/chat/* {
        reverse_proxy localhost:8000 {
            transport http {
                versions 1.1
            }
        }
    }

    # Static files (Frontend)
    handle /* {
        root * /var/www/youtubetalker/dist
        try_files {path} /index.html
        file_server
    }

    # Logging
    log {
        output file /var/log/caddy/youtubetalker.log
    }

    # Automatic HTTPS
    tls {
        protocols tls1.2 tls1.3
    }

    # Security headers
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "strict-origin-when-cross-origin"
    }

    # Compression
    encode gzip zstd
}
```

**Install and start Caddy:**

```bash
# Install Caddy (Ubuntu/Debian)
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/caddy-stable-archive-keyring.gpg] https://dl.cloudsmith.io/public/caddy/stable/deb/debian any-version main" | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy

# Enable and start
sudo systemctl enable caddy
sudo systemctl start caddy

# Reload after config changes
sudo systemctl reload caddy
```

---

## Deployment Workflow

### Initial Server Setup

```bash
# 1. Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# 2. Install Docker Compose
sudo apt install docker-compose-plugin

# 3. Install Caddy (see above)

# 4. Create directories
sudo mkdir -p /var/lib/youtubetalker/{postgres,qdrant}
sudo mkdir -p /var/www/youtubetalker/dist
sudo mkdir -p /var/log/caddy

# 5. Clone repository
git clone https://github.com/yourusername/youtubetalker.git
cd youtubetalker

# 6. Create .env file
cp .env.example .env
nano .env  # Fill in production values

# 7. Build and start containers
docker compose -f docker-compose.prod.yml up -d

# 8. Run database migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# 9. Seed database (if needed)
docker compose -f docker-compose.prod.yml exec backend python scripts/seed_production.py
```

### Continuous Deployment

**Option 1: GitHub Actions (Recommended)**

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Build Frontend
        run: |
          cd frontend
          npm install
          npm run build

      - name: Deploy to Server
        uses: appleboy/scp-action@master
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SERVER_SSH_KEY }}
          source: "backend/,frontend/dist/,docker-compose.prod.yml"
          target: "/home/deploy/youtubetalker"

      - name: SSH and Deploy
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SERVER_SSH_KEY }}
          script: |
            cd /home/deploy/youtubetalker
            docker compose -f docker-compose.prod.yml pull
            docker compose -f docker-compose.prod.yml up -d --build
            docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
            rsync -a frontend/dist/ /var/www/youtubetalker/dist/
```

**Option 2: Manual Deployment**

```bash
# On local machine
git pull origin main
cd frontend && npm run build && cd ..
rsync -avz --exclude='.git' . user@server:/home/deploy/youtubetalker/

# On server
cd /home/deploy/youtubetalker
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
rsync -a frontend/dist/ /var/www/youtubetalker/dist/
sudo systemctl reload caddy
```

---

## Environment Variables

### Local (.env)

```bash
# Database
POSTGRES_PASSWORD=postgres

# OpenRouter
OPENROUTER_API_KEY=your-dev-key

# SUPADATA
SUPADATA_API_KEY=your-dev-key
SUPADATA_BASE_URL=https://api.supadata.ai
```

### Production (.env)

```bash
# Database
POSTGRES_USER=youtubetalker
POSTGRES_PASSWORD=<strong-random-password>

# OpenRouter
OPENROUTER_API_KEY=<production-key>

# SUPADATA
SUPADATA_API_KEY=<production-key>
SUPADATA_BASE_URL=https://api.supadata.ai

# App
ENVIRONMENT=production
ALLOWED_ORIGINS=https://youtubetalker.com
```

---

## Monitoring & Maintenance

### Health Checks

```bash
# Check all containers
docker compose -f docker-compose.prod.yml ps

# Check backend health
curl http://localhost:8000/api/health

# Check database connection
docker compose -f docker-compose.prod.yml exec postgres pg_isready

# Check Qdrant
curl http://localhost:6333/health
```

### Logs

```bash
# View backend logs
docker compose -f docker-compose.prod.yml logs -f backend

# View Caddy logs
sudo tail -f /var/log/caddy/youtubetalker.log

# View all container logs
docker compose -f docker-compose.prod.yml logs -f
```

### Backups

**PostgreSQL:**
```bash
# Backup
docker compose -f docker-compose.prod.yml exec postgres pg_dump -U youtubetalker youtube_talker > backup.sql

# Restore
cat backup.sql | docker compose -f docker-compose.prod.yml exec -T postgres psql -U youtubetalker youtube_talker
```

**Qdrant:**
```bash
# Backup (copy volume)
sudo tar -czf qdrant-backup.tar.gz /var/lib/youtubetalker/qdrant/

# Restore
sudo tar -xzf qdrant-backup.tar.gz -C /
```

---

## Security Considerations

1. **Container Security:**
   - Run containers as non-root user (production Dockerfile)
   - Minimal base images (alpine, slim)
   - No unnecessary packages

2. **Network Isolation:**
   - Backend only accessible via Caddy (127.0.0.1 binding)
   - PostgreSQL and Qdrant not exposed to internet
   - Internal Docker network for service communication

3. **Secrets Management:**
   - Never commit .env files
   - Use strong passwords
   - Rotate API keys regularly

4. **Updates:**
   - Regularly update base images
   - Apply security patches
   - Monitor CVE databases

---

## Troubleshooting

**Container won't start:**
```bash
docker compose logs <service-name>
docker compose ps
```

**Database connection issues:**
```bash
# Check if PostgreSQL is ready
docker compose exec postgres pg_isready

# Check connection string
docker compose exec backend env | grep DATABASE_URL
```

**Frontend not updating:**
```bash
# Rebuild frontend
cd frontend && npm run build

# Re-sync to server
rsync -a frontend/dist/ /var/www/youtubetalker/dist/

# Clear browser cache
```

**Caddy issues:**
```bash
# Check config syntax
caddy validate --config /etc/caddy/Caddyfile

# View Caddy logs
sudo journalctl -u caddy -f
```

---

## Summary

**Local Development:**
- PostgreSQL, Qdrant, Backend, Frontend all in containers
- Direct access to services (no proxy)
- Hot reload for development

**Production:**
- PostgreSQL, Qdrant, Backend in containers
- Frontend built to static files
- Caddy on host serves static files + proxies API
- Automatic HTTPS with Let's Encrypt
- Security headers and compression

**Key Benefits:**
- ✅ Local/prod parity (same container images)
- ✅ Simple deployment (docker compose up)
- ✅ Easy rollback (container versioning)
- ✅ Isolated dependencies
- ✅ Scalable (can add more backend replicas)

**Reference:** See `docker-compose.yml` for local setup and `docker-compose.prod.yml` for production.

---

**Document Version:**
- v1.0 (2025-10-17): Initial Docker strategy
