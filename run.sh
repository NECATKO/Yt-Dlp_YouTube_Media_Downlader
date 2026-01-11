#!/bin/bash
# run.sh - Cross-platform launcher for ytdlp-downloader

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [[ ! -d ".venv" ]]; then
    echo -e "${YELLOW}Virtual environment not found. Running installer...${NC}"
    
    if [[ -f "install.sh" ]]; then
        bash install.sh
    else
        echo -e "${RED}install.sh not found. Please run installation manually.${NC}"
        exit 1
    fi
fi

# Determine Python executable
if [[ -f ".venv/bin/python" ]]; then
    PYTHON=".venv/bin/python"
elif [[ -f ".venv/Scripts/python.exe" ]]; then
    # Windows Git Bash or similar
    PYTHON=".venv/Scripts/python.exe"
else
    echo -e "${RED}Python not found in virtual environment.${NC}"
    echo -e "${YELLOW}Please run: ./install.sh${NC}"
    exit 1
fi

# Check for updates (optional)
check_updates() {
    if [[ -f "update.sh" ]]; then
        echo -e "${CYAN}Checking for updates...${NC}"
        bash update.sh --check-only 2>/dev/null || true
    fi
}

# Run the downloader
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  ytdlp-downloader${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# Optional: check for updates
# check_updates

# Run the application
exec "$PYTHON" downloader.py "$@"
