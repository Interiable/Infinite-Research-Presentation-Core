#!/bin/bash
# ============================================================
# LangAIAgent — One-shot Setup Script
# Ubuntu 24.04 / Python 3.11+
# Usage: bash setup.sh
# ============================================================

set -e  # Exit on any error
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC}   $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║       LangAIAgent — Setup (Ubuntu 24.04)      ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ------------------------------------------------------------
# 1. System dependencies
# ------------------------------------------------------------
info "Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
  python3 python3-pip python3-venv \
  nodejs npm \
  curl wget git \
  build-essential libssl-dev \
  fonts-noto-cjk fonts-noto-color-emoji \
  libnss3 libatk-bridge2.0-0 libdrm2 libxcomposite1 \
  libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 \
  libasound2t64 libxkbcommon0
success "System packages installed"

# ------------------------------------------------------------
# 2. Python virtual environment
# ------------------------------------------------------------
info "Creating Python virtual environment in backend/venv ..."
cd backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip --quiet
success "Virtual environment ready"

# ------------------------------------------------------------
# 3. Python dependencies
# ------------------------------------------------------------
info "Installing Python packages (this may take a few minutes)..."
pip install -r requirements.txt --quiet
success "Python packages installed"

# ------------------------------------------------------------
# 4. Playwright — Chromium browser for PDF generation
# ------------------------------------------------------------
info "Installing Playwright Chromium (required for PDF generation)..."
playwright install chromium
success "Playwright Chromium installed"

cd ..

# ------------------------------------------------------------
# 5. Frontend (Node / npm)
# ------------------------------------------------------------
info "Installing frontend dependencies..."
cd frontend
npm install --silent
success "Frontend dependencies installed"
cd ..

# ------------------------------------------------------------
# 6. Ollama (local LLM server)
# ------------------------------------------------------------
if command -v ollama &>/dev/null; then
  success "Ollama already installed: $(ollama --version 2>/dev/null | head -1)"
else
  info "Installing Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh
  success "Ollama installed"
fi

# ------------------------------------------------------------
# 7. Pull local LLM model
# ------------------------------------------------------------
LOCAL_MODEL=${LOCAL_LLM_MODEL:-"qwen3:32b"}
echo ""
warn "Local model to pull: ${LOCAL_MODEL}"
warn "This requires ~20GB VRAM / disk space. Skip with Ctrl+C if not needed."
echo ""
read -p "Pull local model '${LOCAL_MODEL}' now? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
  info "Pulling ${LOCAL_MODEL} via Ollama..."
  ollama pull "${LOCAL_MODEL}"
  success "Model ${LOCAL_MODEL} ready"
else
  warn "Skipped model pull. Run manually: ollama pull ${LOCAL_MODEL}"
fi

# ------------------------------------------------------------
# 8. .env setup
# ------------------------------------------------------------
if [ ! -f backend/.env ]; then
  info "Creating backend/.env from template..."
  cp backend/.env.example backend/.env
  echo ""
  warn "▶ ACTION REQUIRED: Edit backend/.env and fill in your API keys"
  warn "  nano backend/.env"
  echo ""
else
  success "backend/.env already exists — skipping"
fi

# ------------------------------------------------------------
# 9. Required directories
# ------------------------------------------------------------
info "Creating required directories..."
mkdir -p backend/artifacts backend/results backend/dialogue_history backend/data
success "Directories ready"

# ------------------------------------------------------------
# Done
# ------------------------------------------------------------
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║               Setup Complete! 🚀              ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  Next steps:"
echo "  1. Fill in API keys:  nano backend/.env"
echo "  2. Start the system:  python3 run_system.py"
echo "  3. Open browser:      http://localhost:5174"
echo ""
