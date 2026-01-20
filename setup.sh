#!/bin/bash
# ============================================
# Auto BitBrowser - Setup Script (Linux/Mac)
# ============================================
# Run: chmod +x setup.sh && ./setup.sh
# ============================================

echo "========================================"
echo "Auto BitBrowser - Setup"
echo "========================================"

# Check Python version
echo "[1/4] Checking Python version..."
python3 --version

# Create virtual environment (optional but recommended)
echo "[2/4] Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "[3/4] Installing Python packages..."
pip install -r requirements.txt

# Install Playwright browsers
echo "[4/4] Installing Playwright Chromium..."
playwright install chromium

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "To run the tool:"
echo "  source venv/bin/activate"
echo "  python auto_batch.py"
echo ""
