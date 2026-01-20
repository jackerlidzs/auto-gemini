@echo off
REM ============================================
REM Auto BitBrowser - Setup Script (Windows)
REM ============================================
REM Run: setup.bat
REM ============================================

echo ========================================
echo Auto BitBrowser - Setup
echo ========================================

REM Check Python version
echo [1/4] Checking Python version...
python --version

REM Create virtual environment
echo [2/4] Creating virtual environment...
python -m venv venv
call venv\Scripts\activate

REM Install dependencies
echo [3/4] Installing Python packages...
pip install -r requirements.txt

REM Install Playwright browsers
echo [4/4] Installing Playwright Chromium...
playwright install chromium

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo To run the tool:
echo   venv\Scripts\activate
echo   python auto_batch.py
echo.
pause
