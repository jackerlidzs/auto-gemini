#!/bin/bash
# ============================================
# Auto Gemini - Complete Setup for Debian 12
# ============================================
# OS: Debian GNU/Linux 12 (Bookworm)
# Arch: x86_64
# ============================================
# Run from project directory:
#   cd /opt/auto-gemini
#   sudo bash setup_debian.sh
# ============================================

set -e  # Exit on error

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "Auto Gemini - Debian 12 Setup"
echo "========================================"
echo "Project directory: $SCRIPT_DIR"
echo ""

# 1. Update system
echo "[1/7] Updating system packages..."
apt update && apt upgrade -y

# 2. Install Python 3.11+ (Debian 12 comes with Python 3.11)
echo "[2/7] Installing Python and dependencies..."
apt install -y python3 python3-pip python3-venv python3-dev

# Check Python version
echo "Python version:"
python3 --version

# 3. Install system dependencies for Playwright
echo "[3/7] Installing system dependencies for browser automation..."
apt install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    fonts-liberation \
    xvfb \
    wget \
    curl

# 4. Install dependencies for PyQt6 (headless)
echo "[4/7] Installing Qt dependencies..."
apt install -y \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    libegl1 \
    libgl1 \
    libxkbcommon-x11-0 \
    libdbus-1-3

# 5. Create virtual environment in project directory
echo "[5/7] Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# 6. Install Python packages
echo "[6/7] Installing Python packages..."
pip install --upgrade pip
pip install -r "$SCRIPT_DIR/requirements.txt"

# 7. Install Playwright browsers
echo "[7/7] Installing Playwright Chromium..."
playwright install chromium
playwright install-deps chromium

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Python version: $(python3 --version)"
echo "Pip version: $(pip --version)"
echo ""
echo "Next steps:"
echo "  1. cp accounts.example.txt accounts.txt"
echo "  2. nano accounts.txt  # Add your accounts"
echo "  3. cp proxies.example.txt proxies.txt (optional)"
echo ""
echo "To run the tool:"
echo "  cd $SCRIPT_DIR"
echo "  source venv/bin/activate"
echo "  python auto_batch.py"
echo ""
