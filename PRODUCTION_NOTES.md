# YouTube Talker - Production Deployment Guide

## 🚀 Server Information

- **Server IP**: 207.154.244.167
- **Domains**:
  - Frontend: `qivio.pl` (and `www.qivio.pl`)
  - Backend API: `api.qivio.pl`
- **OS**: Ubuntu 24.04 LTS
- **Web Server**: Caddy 2.x (automatic HTTPS)

## 📦 Application Structure

```
/var/www/qivio.pl/app/
├── backend/                 # FastAPI Python application
│   ├── .venv/              # Python virtual environment
│   ├── app/                # Application code
│   ├── alembic/            # Database migrations
│   └── .env                # Backend environment variables
├── frontend/               # Astro Node.js application
│   ├── dist/               # Built application
│   ├── src/                # Source code
│   └── .env                # Frontend environment variables
├── scripts/                # Deployment scripts
│   ├── restart-app.sh      # Full application restart
│   ├── deploy.sh           # Deployment script
│   └── setup_production.sh # Initial setup script
├── docker-compose.yml      # Docker services configuration
└── PRODUCTION_NOTES.md     # This file
```

## 🔧 System Services

### Systemd Services

1. **youtubetalker-backend** - FastAPI backend API
   - Port: 8000
   - User: www-admin
   - Python: 3.12 with uvicorn

2. **youtubetalker-frontend** - Astro Node.js frontend
   - Port: 4321
   - User: www-admin
   - Node standalone mode

3. **caddy** - Web server and reverse proxy
   - Ports: 80 (HTTP), 443 (HTTPS)
   - Auto HTTPS with Let's Encrypt

### Docker Containers

1. **youtube-talker-postgres** - PostgreSQL 15 database
   - Port: 5432
   - User: postgres
   - Password: *stored in backend/.env*
   - Database: youtube_talker

2. **youtube-talker-qdrant** - Qdrant vector database
   - HTTP Port: 6333
   - gRPC Port: 6334
   - Dashboard: http://localhost:6333/dashboard

## 🎯 Service Management

### Starting/Stopping Services

```bash
# Backend
sudo systemctl start youtubetalker-backend
sudo systemctl stop youtubetalker-backend
sudo systemctl restart youtubetalker-backend
sudo systemctl status youtubetalker-backend

# Frontend
sudo systemctl start youtubetalker-frontend
sudo systemctl stop youtubetalker-frontend
sudo systemctl restart youtubetalker-frontend
sudo systemctl status youtubetalker-frontend

# Web Server
sudo systemctl reload caddy        # Reload config without downtime
sudo systemctl restart caddy       # Full restart
sudo systemctl status caddy

# Docker Services
cd /var/www/qivio.pl/app
docker compose up -d               # Start all Docker services
docker compose down                # Stop all Docker services
docker compose restart postgres    # Restart PostgreSQL
docker compose restart qdrant      # Restart Qdrant
docker compose ps                  # Show status
```

### Full Application Restart

Use the custom restart script for a complete, ordered restart:

```bash
cd /var/www/qivio.pl/app
sudo ./scripts/restart-app.sh
```

This script will:
1. Stop backend and frontend services
2. Restart Docker containers
3. Wait for databases to be healthy
4. Start backend and frontend
5. Run health checks
6. Show status summary

## 📊 Monitoring & Logs

### View Logs

```bash
# Backend logs (real-time)
sudo journalctl -u youtubetalker-backend -f

# Backend logs (last 100 lines)
sudo journalctl -u youtubetalker-backend -n 100

# Frontend logs (real-time)
sudo journalctl -u youtubetalker-frontend -f

# Caddy logs
sudo journalctl -u caddy -f
# OR check specific domain logs:
tail -f /var/log/caddy/qivio.pl.log
tail -f /var/log/caddy/api.qivio.pl.log

# Docker logs
docker compose logs -f              # All containers
docker compose logs -f postgres     # PostgreSQL only
docker compose logs -f qdrant       # Qdrant only
```

### Health Checks

```bash
# Backend API health
curl http://localhost:8000/api/health
# Should return: {"status":"ok"}

# Frontend health
curl -I http://localhost:4321
# Should return: HTTP/1.1 200 OK

# PostgreSQL health
docker exec youtube-talker-postgres pg_isready -U postgres

# Qdrant health
curl http://localhost:6333/
# Should return: {"title":"qdrant - vector search engine",...}

# Check all container health
docker ps --filter "name=youtube-talker"
```

## 🔐 Environment Variables

### Backend Environment (.env location: `/var/www/qivio.pl/app/backend/.env`)

**⚠️ IMPORTANT**: These API keys need to be configured:

```bash
# OpenRouter API (for LLM completions)
OPENROUTER_API_KEY=YOUR_OPENROUTER_API_KEY_HERE

# OpenAI API (for embeddings)
OPENAI_API_KEY=YOUR_OPENAI_API_KEY_HERE

# SUPADATA API (YouTube transcription)
SUPADATA_API_KEY=YOUR_SUPADATA_API_KEY_HERE
```

**After adding API keys, restart the backend:**
```bash
sudo systemctl restart youtubetalker-backend
```

### Other Backend Configuration

```bash
DATABASE_URL=postgresql+asyncpg://postgres:<password>@localhost:5432/youtube_talker
QDRANT_URL=http://localhost:6333
ALLOWED_ORIGINS=https://qivio.pl,https://api.qivio.pl
ENV=production
DEBUG=false
```

### Frontend Environment (.env location: `/var/www/qivio.pl/app/frontend/.env`)

```bash
PUBLIC_API_BASE=https://api.qivio.pl/api
PUBLIC_WS_URL=wss://api.qivio.pl/api/ws/chat
```

## 🌐 DNS Configuration

**Current Status:**
- ✅ `qivio.pl` - Configured and working
- ⚠️ `api.qivio.pl` - **Needs DNS configuration**

**To add the API subdomain:**

1. Go to your DNS provider (e.g., Cloudflare, Route53, etc.)
2. Add an A record:
   ```
   Type: A
   Name: api
   Value: 207.154.244.167
   TTL: Auto or 3600
   ```
3. Wait 5-60 minutes for DNS propagation
4. Caddy will automatically provision SSL certificate

**Verify DNS is working:**
```bash
host api.qivio.pl
# Should return: api.qivio.pl has address 207.154.244.167
```

## 🔄 Deployment Workflow

### Deploying Code Updates

1. **Pull latest code:**
   ```bash
   cd /var/www/qivio.pl/app
   sudo -u www-admin git pull origin main
   ```

2. **Update backend:**
   ```bash
   cd /var/www/qivio.pl/app/backend
   sudo -u www-admin bash -c "source .venv/bin/activate && pip install -e ."
   sudo -u www-admin bash -c "source .venv/bin/activate && alembic upgrade head"
   sudo systemctl restart youtubetalker-backend
   ```

3. **Update frontend:**
   ```bash
   cd /var/www/qivio.pl/app/frontend
   sudo -u www-admin npm ci
   sudo -u www-admin npm run build
   sudo systemctl restart youtubetalker-frontend
   ```

4. **Verify:**
   ```bash
   curl http://localhost:8000/api/health
   curl -I http://localhost:4321
   ```

### Full Deployment Script

Or use the deployment script:
```bash
cd /var/www/qivio.pl/app
sudo -u www-admin bash scripts/deploy.sh
```

## 🐛 Troubleshooting

### Backend won't start

```bash
# Check logs
sudo journalctl -u youtubetalker-backend -n 50

# Common issues:
# 1. Database connection - check DATABASE_URL in .env
# 2. Missing API keys - add to .env
# 3. Port already in use - check: lsof -i :8000

# Test manually:
cd /var/www/qivio.pl/app/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend won't start

```bash
# Check logs
sudo journalctl -u youtubetalker-frontend -n 50

# Common issues:
# 1. Build not completed - run: npm run build
# 2. Port already in use - check: lsof -i :4321
# 3. Missing node_modules - run: npm ci

# Test manually:
cd /var/www/qivio.pl/app/frontend
node ./dist/server/entry.mjs
```

### Database connection issues

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Check if it's healthy
docker inspect --format='{{.State.Health.Status}}' youtube-talker-postgres

# Connect to database
docker exec -it youtube-talker-postgres psql -U postgres -d youtube_talker

# Check logs
docker logs youtube-talker-qdrant
docker logs youtube-talker-postgres
```

### Qdrant connection issues

```bash
# Check if Qdrant is running
docker ps | grep qdrant

# Test connection
curl http://localhost:6333/

# Check logs
docker logs youtube-talker-qdrant

# Restart if needed
docker compose restart qdrant
```

### Caddy issues

```bash
# Check configuration
sudo caddy validate --config /etc/caddy/Caddyfile

# Check logs
sudo journalctl -u caddy -n 100

# Reload config
sudo systemctl reload caddy

# Test configuration
sudo caddy fmt --overwrite /etc/caddy/Caddyfile
```

### SSL Certificate Issues

```bash
# Check certificate status
sudo caddy trust list

# Force certificate renewal
sudo systemctl stop caddy
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl start caddy

# Check Let's Encrypt rate limits
# View Caddy logs for ACME errors
sudo journalctl -u caddy | grep acme
```

## 📝 Important File Locations

### Configuration Files
```
/etc/caddy/Caddyfile                                  # Web server config
/etc/systemd/system/youtubetalker-backend.service    # Backend service
/etc/systemd/system/youtubetalker-frontend.service   # Frontend service
/var/www/qivio.pl/app/docker-compose.yml             # Docker config
```

### Application Files
```
/var/www/qivio.pl/app/backend/.env                   # Backend env vars
/var/www/qivio.pl/app/frontend/.env                  # Frontend env vars
/var/www/qivio.pl/app/scripts/restart-app.sh         # Restart script
```

### Log Files
```
/var/log/caddy/qivio.pl.log                          # Frontend access logs
/var/log/caddy/api.qivio.pl.log                      # Backend access logs
journalctl -u youtubetalker-backend                  # Backend app logs
journalctl -u youtubetalker-frontend                 # Frontend app logs
```

### Data Directories
```
/var/lib/docker/volumes/youtube-talker-postgres-data # PostgreSQL data
/var/lib/docker/volumes/youtube-talker-qdrant-data   # Qdrant data
```

## 🔒 Security Checklist

- [x] Services run as non-root user (www-admin)
- [x] Firewall configured (ufw if enabled)
- [x] HTTPS enforced by Caddy
- [x] Secrets stored in .env files (not in code)
- [x] Database password is strong and random
- [x] CORS configured in backend
- [x] Security headers set in Caddy
- [ ] **API keys need to be added** (see Environment Variables section)

## 📞 Quick Reference

### Service Status Check (one-liner)
```bash
echo "Backend:" && systemctl is-active youtubetalker-backend && \
echo "Frontend:" && systemctl is-active youtubetalker-frontend && \
echo "Caddy:" && systemctl is-active caddy && \
echo "Docker:" && docker ps --filter "name=youtube-talker" --format "table {{.Names}}\t{{.Status}}"
```

### Complete Health Check
```bash
echo "=== Backend ===" && curl -s http://localhost:8000/api/health && \
echo -e "\n=== Frontend ===" && curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:4321 && \
echo "=== Docker ===" && docker ps --filter "name=youtube-talker" --format "table {{.Names}}\t{{.Status}}"
```

### Emergency Stop All
```bash
sudo systemctl stop youtubetalker-backend youtubetalker-frontend && \
docker compose -f /var/www/qivio.pl/app/docker-compose.yml down
```

### Emergency Start All
```bash
docker compose -f /var/www/qivio.pl/app/docker-compose.yml up -d && \
sleep 10 && \
sudo systemctl start youtubetalker-backend youtubetalker-frontend
```

---

## 📚 Additional Resources

- **Astro Documentation**: https://docs.astro.build
- **FastAPI Documentation**: https://fastapi.tiangolo.com
- **Caddy Documentation**: https://caddyserver.com/docs
- **Docker Compose**: https://docs.docker.com/compose
- **Qdrant Documentation**: https://qdrant.tech/documentation

---

**Last Updated**: 2025-11-08
**Maintainer**: www-admin@qivio.pl

---

## 🚀 GitHub Actions Deployment

### Configuration

The application is configured for automated deployment via GitHub Actions when code is pushed to the `main` branch.

**Deployment User:** `www-admin`

**Required GitHub Secrets:**
- `SSH_PRIVATE_KEY` - Private SSH key for www-admin user (deploy-key-yt)
- `SERVER_HOST` - Server IP address (207.154.244.167)
- `SERVER_USER` - Deployment user (www-admin)
- `SERVER_DEPLOY_PATH` - Application path (/var/www/qivio.pl/app)

### Sudo Configuration

Passwordless sudo is configured for www-admin to manage application services:

**File:** `/etc/sudoers.d/www-admin-deploy`

**Allowed commands:**
- `systemctl start/stop/restart/enable/disable/status` for youtubetalker-backend and youtubetalker-frontend
- `systemctl is-active` for checking service status
- `journalctl -u` for viewing service logs

### Deployment Process

When code is pushed to main:

1. **GitHub Actions runner connects via SSH** as www-admin
2. **Pulls latest code** from main branch
3. **Runs deployment script** (`scripts/deploy.sh`)
   - Stops services
   - Installs/updates dependencies (backend + frontend)
   - Runs database migrations
   - Builds frontend
   - Restarts Docker services
   - Starts application services
4. **Runs health checks** on backend and frontend
5. **Reports status** (success/failure)

### Manual Deployment

You can also deploy manually:

```bash
ssh www-admin@207.154.244.167
cd /var/www/qivio.pl/app
git pull origin main
bash scripts/deploy.sh
```

### Troubleshooting Deployments

**If deployment fails:**

1. Check GitHub Actions logs in the repository
2. SSH to server and check service logs:
   ```bash
   sudo journalctl -u youtubetalker-backend -n 50
   sudo journalctl -u youtubetalker-frontend -n 50
   ```
3. Check if services are running:
   ```bash
   systemctl status youtubetalker-backend
   systemctl status youtubetalker-frontend
   ```
4. Manually run deployment script to see errors:
   ```bash
   cd /var/www/qivio.pl/app
   bash scripts/deploy.sh
   ```

### Security Notes

- www-admin user has limited sudo access (only for application services)
- SSH key authentication only (no password login)
- www-admin is in docker group for managing containers
- All sudo commands are logged for audit purposes

