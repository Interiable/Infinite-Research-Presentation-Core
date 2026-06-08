#!/bin/bash
# ============================================================
# LangAIAgent — One-shot Setup Script
# Ubuntu 24.04 / Python 3.11+
# Usage: bash setup.sh
# ============================================================

set -e
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
# 2. .env setup (BEFORE pip install so LOCAL_LLM_MODEL is readable)
# ------------------------------------------------------------
if [ ! -f backend/.env ]; then
  info "Creating backend/.env from template..."
  cp backend/.env.example backend/.env
  echo ""
  warn "▶ ACTION REQUIRED: Edit backend/.env and fill in your API keys before continuing."
  warn "  nano backend/.env"
  echo ""
  read -p "Press Enter after editing .env to continue setup..." -r
else
  success "backend/.env already exists — skipping"
fi

# Read model names from .env
if [ -f backend/.env ]; then
  ENV_LOCAL_MODEL=$(grep -E "^LOCAL_LLM_MODEL=" backend/.env | cut -d'=' -f2 | tr -d ' "#\'\r')
  ENV_SCIENCE_MODEL=$(grep -E "^LOCAL_SCIENCE_MODEL=" backend/.env | cut -d'=' -f2 | tr -d ' "#\'\r')
fi
LOCAL_MODEL="${ENV_LOCAL_MODEL:-"qwen3.6:27b"}"
SCIENCE_MODEL="${ENV_SCIENCE_MODEL:-"gemma4:31b"}"

# ------------------------------------------------------------
# 3. Python virtual environment
# ------------------------------------------------------------
info "Creating Python virtual environment in backend/venv ..."
cd backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip --quiet
success "Virtual environment ready"

# ------------------------------------------------------------
# 4. Python dependencies
# ------------------------------------------------------------
info "Installing Python packages (this may take a few minutes)..."
pip install -r requirements.txt --quiet
success "Python packages installed"

# ------------------------------------------------------------
# 5. Playwright — Chromium browser for PDF generation
#    Use venv python to avoid system path conflicts
# ------------------------------------------------------------
info "Installing Playwright Chromium (required for PDF generation)..."
python3 -m playwright install chromium
success "Playwright Chromium installed"

cd ..

# ------------------------------------------------------------
# 6. Frontend (Node / npm)
# ------------------------------------------------------------
info "Installing frontend dependencies..."
cd frontend
npm install --silent
success "Frontend dependencies installed"
cd ..

# ------------------------------------------------------------
# 7. Ollama (local LLM server)
# ------------------------------------------------------------
if command -v ollama &>/dev/null; then
  success "Ollama already installed: $(ollama --version 2>/dev/null | head -1)"
else
  info "Installing Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh
  success "Ollama installed"
fi

# ------------------------------------------------------------
# 8. Pull local LLM models (reads from .env)
# ------------------------------------------------------------
echo ""
warn "Models to pull:"
warn "  General LLM : ${LOCAL_MODEL}   (~17GB)"
warn "  Science LLM : ${SCIENCE_MODEL} (~22GB)"
warn "Total disk ~39GB required."
echo ""
read -p "Pull both models now? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
  info "Pulling ${LOCAL_MODEL} (General LLM)..."
  ollama pull "${LOCAL_MODEL}"
  success "${LOCAL_MODEL} ready"

  info "Pulling ${SCIENCE_MODEL} (Science LLM)..."
  ollama pull "${SCIENCE_MODEL}"
  success "${SCIENCE_MODEL} ready"
else
  warn "Skipped. Run manually:"
  warn "  ollama pull ${LOCAL_MODEL}"
  warn "  ollama pull ${SCIENCE_MODEL}"
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
echo "  1. Verify API keys:   nano backend/.env"
echo "  2. Start the system:  python3 run_system.py"
echo "  3. Open browser:      http://localhost:5174"
echo ""
