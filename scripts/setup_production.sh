#!/bin/bash

# One-time Production Server Setup Script for YoutubeTalker
# Run this script ONCE on a fresh Digital Ocean droplet to set up the production environment

set -e

echo "========================================="
echo "🔧 YoutubeTalker Production Setup"
echo "========================================="

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if running as root or with sudo
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root or with sudo${NC}"
   exit 1
fi

# =======================
# 1. System updates
# =======================
echo ""
echo -e "${YELLOW}📦 Updating system packages...${NC}"
apt-get update
apt-get upgrade -y

# =======================
# 2. Install dependencies
# =======================
echo ""
echo -e "${YELLOW}🔧 Installing dependencies...${NC}"

# Install essential packages
apt-get install -y \
    git \
    curl \
    wget \
    build-essential \
    software-properties-common \
    ca-certificates \
    gnupg \
    lsb-release

# Install Python 3.12
echo "Installing Python 3.12..."
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update
apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip

# Install Node.js 20
echo "Installing Node.js 20..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# Install Docker
echo "Installing Docker..."
curl -fsSL https://get.docker.com | sh
systemctl start docker
systemctl enable docker

# Install Docker Compose
echo "Installing Docker Compose..."
apt-get install -y docker-compose-plugin

echo -e "${GREEN}✅ Dependencies installed${NC}"

# =======================
# 3. Create deployment user
# =======================
echo ""
echo -e "${YELLOW}👤 Setting up deployment user...${NC}"

# Create deploy user if it doesn't exist
if ! id "deploy" &>/dev/null; then
    useradd -m -s /bin/bash deploy
    usermod -aG docker deploy
    echo -e "${GREEN}✅ Deploy user created${NC}"
else
    echo "ℹ️  Deploy user already exists"
fi

# =======================
# 4. Setup deployment directory
# =======================
echo ""
echo -e "${YELLOW}📂 Setting up deployment directory...${NC}"

DEPLOY_PATH="/opt/youtubetalker"

# Create deployment directory
mkdir -p "$DEPLOY_PATH"
chown -R deploy:deploy "$DEPLOY_PATH"

# Clone repository (user will need to provide the repo URL)
read -p "Enter your GitHub repository URL (e.g., git@github.com:user/repo.git): " REPO_URL

if [ -d "$DEPLOY_PATH/.git" ]; then
    echo "ℹ️  Repository already exists, pulling latest..."
    cd "$DEPLOY_PATH"
    sudo -u deploy git pull
else
    echo "Cloning repository..."
    sudo -u deploy git clone "$REPO_URL" "$DEPLOY_PATH"
fi

echo -e "${GREEN}✅ Deployment directory setup complete${NC}"

# =======================
# 5. Setup environment files
# =======================
echo ""
echo -e "${YELLOW}📝 Setting up environment files...${NC}"

# Create backend .env
if [ ! -f "$DEPLOY_PATH/backend/.env" ]; then
    cat > "$DEPLOY_PATH/backend/.env" << 'EOF'
# Database
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/youtubetalker_prod

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_NAME=youtube_transcripts

# OpenRouter API
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Session
SESSION_SECRET_KEY=your_secret_key_here_change_this

# Environment
ENVIRONMENT=production

# CORS
ALLOWED_ORIGINS=http://your-domain.com,https://your-domain.com

# RAG Configuration
RAG_CHUNK_SIZE=700
RAG_CHUNK_OVERLAP=20
RAG_MAX_CONTEXT_MESSAGES=10
RAG_RETRIEVAL_TOP_K=12

# Embedding Model
EMBEDDING_MODEL=openai/text-embedding-3-small
EMBEDDING_BATCH_SIZE=100

# LLM Models
OPENROUTER_CHITCHAT_MODEL=anthropic/claude-3.5-sonnet
OPENROUTER_ROUTER_MODEL=anthropic/claude-3.5-sonnet
OPENROUTER_GRADER_MODEL=anthropic/claude-3.5-sonnet
OPENROUTER_GENERATOR_MODEL=anthropic/claude-3.5-sonnet
EOF

    chown deploy:deploy "$DEPLOY_PATH/backend/.env"
    echo -e "${YELLOW}⚠️  Please edit $DEPLOY_PATH/backend/.env with your actual values${NC}"
else
    echo "ℹ️  Backend .env already exists"
fi

# Create frontend .env
if [ ! -f "$DEPLOY_PATH/frontend/.env" ]; then
    cat > "$DEPLOY_PATH/frontend/.env" << 'EOF'
PUBLIC_API_URL=http://localhost:8000
PUBLIC_WS_URL=ws://localhost:8000
EOF

    chown deploy:deploy "$DEPLOY_PATH/frontend/.env"
    echo -e "${YELLOW}⚠️  Please edit $DEPLOY_PATH/frontend/.env with your actual values${NC}"
else
    echo "ℹ️  Frontend .env already exists"
fi

# =======================
# 6. Create systemd services
# =======================
echo ""
echo -e "${YELLOW}⚙️  Creating systemd services...${NC}"

# Backend service
cat > /etc/systemd/system/youtubetalker-backend.service << EOF
[Unit]
Description=YoutubeTalker Backend API
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=deploy
WorkingDirectory=$DEPLOY_PATH/backend
Environment="PATH=$DEPLOY_PATH/backend/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$DEPLOY_PATH/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Frontend service
cat > /etc/systemd/system/youtubetalker-frontend.service << EOF
[Unit]
Description=YoutubeTalker Frontend
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=$DEPLOY_PATH/frontend
Environment="PATH=/usr/bin:/bin:/usr/local/bin"
ExecStart=/usr/bin/npm run preview -- --host 0.0.0.0 --port 4321
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

echo -e "${GREEN}✅ Systemd services created${NC}"

# =======================
# 7. Setup Docker services
# =======================
echo ""
echo -e "${YELLOW}🐳 Starting Docker services...${NC}"

cd "$DEPLOY_PATH"

# Start PostgreSQL and Qdrant
docker compose up -d postgres qdrant

echo -e "${GREEN}✅ Docker services started${NC}"

# =======================
# 8. Initial deployment
# =======================
echo ""
echo -e "${YELLOW}🚀 Running initial deployment...${NC}"

cd "$DEPLOY_PATH"

# Make deploy script executable
chmod +x scripts/deploy.sh

# Run deployment as deploy user
sudo -u deploy bash scripts/deploy.sh

# =======================
# 9. Setup firewall (optional)
# =======================
echo ""
echo -e "${YELLOW}🔥 Setting up firewall...${NC}"

# Install ufw if not present
apt-get install -y ufw

# Allow SSH
ufw allow OpenSSH

# Allow HTTP and HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Allow backend API (optional, can be closed if using reverse proxy)
ufw allow 8000/tcp

# Allow frontend (optional, can be closed if using reverse proxy)
ufw allow 4321/tcp

echo "Firewall rules configured. To enable: sudo ufw enable"
echo -e "${YELLOW}⚠️  WARNING: Only enable UFW if you're sure SSH is allowed!${NC}"

# =======================
# 10. Summary
# =======================
echo ""
echo "========================================="
echo -e "${GREEN}🎉 Production setup complete!${NC}"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Edit environment files:"
echo "   - $DEPLOY_PATH/backend/.env"
echo "   - $DEPLOY_PATH/frontend/.env"
echo ""
echo "2. Add deploy user's SSH public key for GitHub:"
echo "   sudo -u deploy ssh-keygen -t ed25519"
echo "   sudo -u deploy cat /home/deploy/.ssh/id_ed25519.pub"
echo "   (Add this to GitHub deploy keys)"
echo ""
echo "3. Services are managed with systemd:"
echo "   sudo systemctl status youtubetalker-backend"
echo "   sudo systemctl status youtubetalker-frontend"
echo ""
echo "4. View logs:"
echo "   sudo journalctl -u youtubetalker-backend -f"
echo "   sudo journalctl -u youtubetalker-frontend -f"
echo ""
echo "5. Optional: Set up Nginx reverse proxy for production domains"
echo ""
