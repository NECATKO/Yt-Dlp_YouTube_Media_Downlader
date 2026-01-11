#!/bin/bash
# update.sh - Cross-platform updater for ytdlp-downloader

set -e

# Configuration
GITHUB_OWNER="NECATKO"
GITHUB_REPO="Yt-Dlp_YouTube_Media_Downlader"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Get current version from git tag or pyproject.toml
get_current_version() {
    if command -v git &> /dev/null && git describe --tags 2>/dev/null; then
        git describe --tags 2>/dev/null | head -1
    elif [[ -f "pyproject.toml" ]]; then
        grep 'version = ' pyproject.toml | head -1 | cut -d'"' -f2
    else
        echo "unknown"
    fi
}

# Get latest release version from GitHub
get_latest_version() {
    if command -v curl &> /dev/null; then
        curl -s "https://api.github.com/repos/$GITHUB_OWNER/$GITHUB_REPO/releases/latest" | \
            grep '"tag_name"' | cut -d'"' -f4
    elif command -v wget &> /dev/null; then
        wget -qO- "https://api.github.com/repos/$GITHUB_OWNER/$GITHUB_REPO/releases/latest" | \
            grep '"tag_name"' | cut -d'"' -f4
    else
        echo ""
    fi
}

# Update yt-dlp
update_ytdlp() {
    echo -e "${YELLOW}Updating yt-dlp...${NC}"
    
    if [[ -f ".venv/bin/pip" ]]; then
        .venv/bin/pip install --upgrade yt-dlp
    elif [[ -f ".venv/Scripts/pip.exe" ]]; then
        .venv/Scripts/pip.exe install --upgrade yt-dlp
    else
        echo -e "${RED}Virtual environment not found.${NC}"
        return 1
    fi
    
    echo -e "${GREEN}yt-dlp updated successfully!${NC}"
}

# Check only mode
if [[ "$1" == "--check-only" ]]; then
    CURRENT=$(get_current_version)
    LATEST=$(get_latest_version)
    
    if [[ -n "$LATEST" && "$CURRENT" != "$LATEST" ]]; then
        echo -e "${YELLOW}Update available: $CURRENT -> $LATEST${NC}"
        exit 0
    else
        exit 0
    fi
fi

# Main update flow
main() {
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  ytdlp-downloader Updater${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
    
    CURRENT=$(get_current_version)
    echo -e "${YELLOW}Current version:${NC} $CURRENT"
    
    LATEST=$(get_latest_version)
    if [[ -n "$LATEST" ]]; then
        echo -e "${YELLOW}Latest version:${NC} $LATEST"
        
        if [[ "$CURRENT" == "$LATEST" ]]; then
            echo -e "${GREEN}You are running the latest version.${NC}"
        else
            echo -e "${YELLOW}A new version is available!${NC}"
            echo ""
            read -p "Download and install update? (y/N): " update_choice
            
            if [[ "$update_choice" =~ ^[Yy]$ ]]; then
                echo -e "${YELLOW}Downloading update...${NC}"
                
                # Download the latest release
                DOWNLOAD_URL="https://github.com/$GITHUB_OWNER/$GITHUB_REPO/archive/refs/tags/$LATEST.zip"
                TMP_DIR=$(mktemp -d)
                
                if command -v curl &> /dev/null; then
                    curl -L -o "$TMP_DIR/update.zip" "$DOWNLOAD_URL"
                else
                    wget -O "$TMP_DIR/update.zip" "$DOWNLOAD_URL"
                fi
                
                echo -e "${YELLOW}Extracting update...${NC}"
                unzip -q "$TMP_DIR/update.zip" -d "$TMP_DIR"
                
                # Copy new files (preserving config)
                EXTRACT_DIR="$TMP_DIR/$GITHUB_REPO-${LATEST#v}"
                
                # Backup config
                [[ -f config.json ]] && cp config.json "$TMP_DIR/config.json.bak"
                [[ -f settings.json ]] && cp settings.json "$TMP_DIR/settings.json.bak"
                
                # Copy new files
                cp -r "$EXTRACT_DIR/ytdlp_app" .
                cp "$EXTRACT_DIR/downloader.py" .
                cp "$EXTRACT_DIR/pyproject.toml" .
                
                # Restore config
                [[ -f "$TMP_DIR/config.json.bak" ]] && cp "$TMP_DIR/config.json.bak" config.json
                [[ -f "$TMP_DIR/settings.json.bak" ]] && cp "$TMP_DIR/settings.json.bak" settings.json
                
                # Cleanup
                rm -rf "$TMP_DIR"
                
                echo -e "${GREEN}Update installed successfully!${NC}"
            fi
        fi
    else
        echo -e "${YELLOW}Could not check for updates.${NC}"
    fi
    
    echo ""
    
    # Always offer to update yt-dlp
    read -p "Update yt-dlp to latest version? (y/N): " ytdlp_choice
    if [[ "$ytdlp_choice" =~ ^[Yy]$ ]]; then
        update_ytdlp
    fi
    
    echo ""
    echo -e "${GREEN}Done!${NC}"
}

main "$@"
