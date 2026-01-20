#!/bin/bash
# ============================================
# Auto BitBrowser - Deploy from GitHub
# ============================================
# Run on VPS: chmod +x deploy.sh && ./deploy.sh
# ============================================

set -e

PROJECT_DIR="/opt/auto-gemini"
REPO_URL="https://github.com/jackerlidzs/auto-gemini.git"
BRANCH="main"

echo "========================================"
echo "Auto BitBrowser - Deploy from GitHub"
echo "========================================"

# Check if project exists
if [ -d "$PROJECT_DIR" ]; then
    echo "[1/3] Pulling latest changes..."
    cd $PROJECT_DIR
    git pull origin $BRANCH
else
    echo "[1/3] Cloning repository..."
    git clone $REPO_URL $PROJECT_DIR
    cd $PROJECT_DIR
fi

# Activate virtual environment
echo "[2/3] Setting up virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# Install/update dependencies
echo "[3/3] Installing dependencies..."
pip install -r requirements.txt --quiet

echo ""
echo "========================================"
echo "Deploy Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Create accounts.txt with your accounts"
echo "2. Create proxies.txt with your proxies (optional)"
echo "3. Run: source venv/bin/activate && python auto_batch.py"
echo ""
