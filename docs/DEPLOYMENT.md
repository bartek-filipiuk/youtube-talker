# Deployment Guide - YoutubeTalker

This document explains the CI/CD setup for automatically testing and deploying YoutubeTalker to production.

## Overview

The deployment workflow consists of two GitHub Actions:

1. **Test Workflow** (`.github/workflows/test.yml`) - Runs on every PR to main
2. **Deploy Workflow** (`.github/workflows/deploy.yml`) - Runs on merge to main

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Developer  │────>│  Pull Request │────>│  GitHub Actions │
│   Creates   │     │   to main     │     │   Run Tests     │
│     PR      │     │               │     │                 │
└─────────────┘     └──────────────┘     └─────────────────┘
                                                    │
                                                    │ Tests Pass?
                                                    ▼
                                          ┌──────────────────┐
                                          │  Merge to main   │
                                          │                  │
                                          └──────────────────┘
                                                    │
                                                    │ Triggers
                                                    ▼
                                          ┌──────────────────┐
                                          │ Auto-Deploy to   │
                                          │ Production (DO)  │
                                          └──────────────────┘
```

## Test Workflow

**Trigger:** Pull requests to `main` branch

**Jobs:**
- **Backend Tests:**
  - Sets up PostgreSQL and Qdrant services
  - Installs Python dependencies
  - Runs database migrations
  - Executes pytest with coverage

- **Frontend Tests:**
  - Sets up Node.js
  - Runs linter (ESLint)
  - Runs formatter check (Prettier)
  - Builds production bundle

**Branch Protection:** Configure main branch to require this workflow to pass before merging.

## Deploy Workflow

**Trigger:** Push to `main` branch (after PR merge)

**Steps:**
1. Checkout code
2. Setup SSH connection to Digital Ocean droplet
3. SSH into server and:
   - Navigate to deployment directory
   - Pull latest code from `main` branch
   - Run deployment script (`scripts/deploy.sh`)
4. Run health checks on backend and frontend
5. Report deployment status

## Deployment Script (`scripts/deploy.sh`)

The deployment script runs on the production server and performs:

1. **Stop Services:**
   - Backend (systemd: `youtubetalker-backend`)
   - Frontend (systemd: `youtubetalker-frontend`)

2. **Update Backend:**
   - Install Python dependencies
   - Run database migrations (`alembic upgrade head`)

3. **Update Frontend:**
   - Install npm dependencies
   - Build production bundle

4. **Start Docker Services:**
   - PostgreSQL
   - Qdrant

5. **Start Application Services:**
   - Backend API server
   - Frontend server

6. **Health Checks:**
   - Verify backend API responds (HTTP 200)
   - Verify frontend responds (HTTP 200)

## Initial Production Setup

### 1. Run Production Setup Script

On your Digital Ocean droplet, run the one-time setup script:

```bash
sudo bash scripts/setup_production.sh
```

This script will:
- Install system dependencies (Python 3.12, Node.js 20, Docker)
- Create deployment user
- Clone repository
- Setup environment files
- Create systemd services
- Start Docker services
- Run initial deployment

### 2. Configure Environment Files

Edit the production environment files created by the setup script:

**Backend** (`/opt/youtubetalker/backend/.env`):
```bash
# Update these values:
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/youtubetalker_prod
OPENROUTER_API_KEY=your_actual_api_key
SESSION_SECRET_KEY=generate_a_strong_random_key
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

**Frontend** (`/opt/youtubetalker/frontend/.env`):
```bash
PUBLIC_API_URL=https://api.yourdomain.com
PUBLIC_WS_URL=wss://api.yourdomain.com
```

### 3. Setup GitHub Deploy Keys

Generate SSH key on the server:
```bash
sudo -u deploy ssh-keygen -t ed25519 -C "deploy@youtubetalker"
sudo -u deploy cat /home/deploy/.ssh/id_ed25519.pub
```

Add the public key to GitHub:
1. Go to: Repository → Settings → Deploy keys → Add deploy key
2. Paste the public key
3. Check "Allow write access" if needed for deployments

### 4. Setup GitHub Secrets

Add the following secrets to your GitHub repository:

Go to: Repository → Settings → Secrets and variables → Actions → New repository secret

**Required Secrets:**

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `SSH_PRIVATE_KEY` | SSH private key for deployment | Contents of deploy user's private key |
| `SERVER_HOST` | Digital Ocean droplet IP address | `123.45.67.89` |
| `SERVER_USER` | SSH user for deployment | `deploy` or `root` |
| `SERVER_DEPLOY_PATH` | Deployment directory on server | `/opt/youtubetalker` |

**Optional Secrets:**

| Secret Name | Description |
|-------------|-------------|
| `CODECOV_TOKEN` | Token for coverage reports (if using Codecov) |

### 5. Enable Branch Protection

1. Go to: Repository → Settings → Branches
2. Add branch protection rule for `main`:
   - ✅ Require a pull request before merging
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging
   - Select: `test-backend` and `test-frontend` as required checks
   - ✅ Do not allow bypassing the above settings

## Manual Deployment

If you need to deploy manually (without GitHub Actions):

```bash
# SSH into production server
ssh deploy@your-server-ip

# Navigate to deployment directory
cd /opt/youtubetalker

# Pull latest code
git pull origin main

# Run deployment script
bash scripts/deploy.sh
```

## Rollback Procedure

If a deployment fails or introduces issues:

### Quick Rollback

```bash
# SSH into server
ssh deploy@your-server-ip
cd /opt/youtubetalker

# Rollback to previous commit
git reset --hard HEAD~1

# Run deployment
bash scripts/deploy.sh
```

### Database Rollback

If you need to rollback database migrations:

```bash
cd /opt/youtubetalker/backend
source .venv/bin/activate

# Rollback one migration
alembic downgrade -1

# Or rollback to specific revision
alembic downgrade <revision_id>
```

## Monitoring & Logs

### View Service Logs

```bash
# Backend logs
sudo journalctl -u youtubetalker-backend -f

# Frontend logs
sudo journalctl -u youtubetalker-frontend -f

# Docker services
docker compose logs -f
```

### Check Service Status

```bash
# Service status
sudo systemctl status youtubetalker-backend
sudo systemctl status youtubetalker-frontend

# Docker services
docker compose ps
```

### Health Checks

```bash
# Backend health
curl http://localhost:8000/api/health

# Frontend
curl http://localhost:4321
```

## Troubleshooting

### Deployment Fails

1. **Check GitHub Actions logs:**
   - Go to Actions tab in GitHub repository
   - Click on failed workflow
   - Review logs for each step

2. **Check server logs:**
   ```bash
   sudo journalctl -u youtubetalker-backend -n 100
   sudo journalctl -u youtubetalker-frontend -n 100
   ```

3. **Verify services are running:**
   ```bash
   systemctl status youtubetalker-backend
   systemctl status youtubetalker-frontend
   docker compose ps
   ```

### Database Migration Fails

```bash
# Check migration status
cd /opt/youtubetalker/backend
source .venv/bin/activate
alembic current

# Check migration history
alembic history

# Try running migrations manually
alembic upgrade head
```

### Permission Issues

```bash
# Fix ownership
sudo chown -R deploy:deploy /opt/youtubetalker

# Fix execute permissions
chmod +x /opt/youtubetalker/scripts/*.sh
```

## Security Best Practices

1. **Never commit secrets** to the repository
2. **Use GitHub Secrets** for sensitive data
3. **Regularly rotate** SSH keys and API keys
4. **Monitor logs** for suspicious activity
5. **Keep dependencies updated** (npm audit, pip audit)
6. **Use HTTPS** for all production traffic
7. **Enable firewall** (UFW) on production server

## Performance Optimization

### Backend

- **Use production ASGI server:** Already using uvicorn
- **Database connection pooling:** Configure in production settings
- **Enable caching:** Redis for session storage
- **CDN:** Use for static assets

### Frontend

- **Enable compression:** Gzip/Brotli in nginx
- **Cache static assets:** Set proper cache headers
- **Optimize images:** Use WebP format
- **Code splitting:** Already handled by Astro build

## Maintenance

### Regular Tasks

- **Weekly:** Review logs for errors
- **Monthly:** Update dependencies
- **Quarterly:** Review and rotate secrets
- **Annually:** Review and update documentation

### Backup Strategy

```bash
# Database backup
pg_dump -U postgres youtubetalker_prod > backup_$(date +%Y%m%d).sql

# Qdrant backup
docker compose exec qdrant /bin/sh -c "cd /qdrant/storage && tar czf /backup/qdrant_$(date +%Y%m%d).tar.gz *"
```

## Support

For issues or questions:
- Check GitHub Issues
- Review application logs
- Contact development team

---

**Last Updated:** 2025-11-07
