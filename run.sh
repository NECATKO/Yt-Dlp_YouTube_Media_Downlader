#!/bin/bash
# run.sh - launcher for ytdlp-downloader (Linux and macOS)
#
# Start it with:  bash run.sh   (or ./run.sh when the file is executable; a ZIP download
# does not keep that bit, so "bash run.sh" always works).
#
# Linux runs from the portable runtime in ./runtime, which install.sh downloads
# on first launch. macOS uses the .venv created by install.sh.

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Ignore packages from the user's own Python profile.
export PYTHONNOUSERSITE=1

# The console output is natural Turkish/English text: make Python use UTF-8 whatever the
# terminal's locale says (the Windows launcher does the same).
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

# There is no update check here: on Linux/macOS the app is updated on request with
# "bash update.sh" (Run.bat, on Windows, still checks at launch).

if [[ "$(uname -s)" == "Linux" ]]; then
    PYTHON="runtime/python/bin/python3"
    if [[ ! -x "$PYTHON" ]]; then
        echo -e "${YELLOW}First-time setup: downloading the portable runtime into this folder...${NC}"
        echo -e "${YELLOW}(Python, yt-dlp, ffmpeg, Deno - nothing is installed on the system)${NC}"
        bash install.sh || { echo -e "${RED}Setup failed.${NC}"; exit 1; }
    elif ! bash install.sh --quiet; then
        # Already set up once: an offline launch must still work.
        echo -e "${YELLOW}WARNING: The runtime check did not finish; continuing with what is installed.${NC}"
    fi
else
    PYTHON=".venv/bin/python"
    if [[ ! -x "$PYTHON" ]]; then
        echo -e "${YELLOW}Virtual environment not found. Running installer...${NC}"
        bash install.sh
    fi
fi

# Run the downloader
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  ytdlp-downloader${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

exec "$PYTHON" -s downloader.py "$@"
