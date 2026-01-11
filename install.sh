#!/bin/bash
# install.sh - Cross-platform installer for ytdlp-downloader
# Supports: Linux (apt, dnf, pacman), macOS (brew)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  ytdlp-downloader Installer${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# Detect OS and package manager
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ -f /etc/debian_version ]]; then
        echo "debian"
    elif [[ -f /etc/redhat-release ]]; then
        echo "redhat"
    elif [[ -f /etc/arch-release ]]; then
        echo "arch"
    else
        echo "unknown"
    fi
}

OS=$(detect_os)
echo -e "${YELLOW}Detected OS:${NC} $OS"

# Check for Python 3.10+
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
        
        if [[ $MAJOR -ge 3 && $MINOR -ge 10 ]]; then
            echo -e "${GREEN}Python $PYTHON_VERSION found${NC}"
            return 0
        fi
    fi
    return 1
}

# Install Python if needed
install_python() {
    echo -e "${YELLOW}Installing Python 3.10+...${NC}"
    
    case $OS in
        macos)
            if command -v brew &> /dev/null; then
                brew install python@3.12
            else
                echo -e "${RED}Homebrew not found. Please install Homebrew first:${NC}"
                echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                exit 1
            fi
            ;;
        debian)
            sudo apt update
            sudo apt install -y python3 python3-venv python3-pip
            ;;
        redhat)
            sudo dnf install -y python3 python3-pip
            ;;
        arch)
            sudo pacman -S --noconfirm python python-pip
            ;;
        *)
            echo -e "${RED}Unknown OS. Please install Python 3.10+ manually.${NC}"
            exit 1
            ;;
    esac
}

# Install ffmpeg
install_ffmpeg() {
    if command -v ffmpeg &> /dev/null; then
        echo -e "${GREEN}ffmpeg already installed${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}Installing ffmpeg...${NC}"
    
    case $OS in
        macos)
            brew install ffmpeg
            ;;
        debian)
            sudo apt install -y ffmpeg
            ;;
        redhat)
            sudo dnf install -y ffmpeg
            ;;
        arch)
            sudo pacman -S --noconfirm ffmpeg
            ;;
        *)
            echo -e "${RED}Please install ffmpeg manually.${NC}"
            ;;
    esac
}

# Install Deno (optional, for JS challenges)
install_deno() {
    if command -v deno &> /dev/null; then
        echo -e "${GREEN}Deno already installed${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}Installing Deno (optional, for JS challenges)...${NC}"
    curl -fsSL https://deno.land/install.sh | sh
    
    # Add to PATH for current session
    export DENO_INSTALL="$HOME/.deno"
    export PATH="$DENO_INSTALL/bin:$PATH"
    
    echo -e "${YELLOW}Note: Add the following to your shell profile (.bashrc, .zshrc, etc.):${NC}"
    echo '  export DENO_INSTALL="$HOME/.deno"'
    echo '  export PATH="$DENO_INSTALL/bin:$PATH"'
}

# Create virtual environment and install dependencies
setup_venv() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$SCRIPT_DIR"
    
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    
    if [[ -d ".venv" ]]; then
        echo -e "${YELLOW}Virtual environment already exists, updating...${NC}"
    else
        python3 -m venv .venv
    fi
    
    echo -e "${YELLOW}Installing dependencies...${NC}"
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -e .
    
    echo -e "${GREEN}Dependencies installed successfully!${NC}"
}

# Main installation flow
main() {
    # Check/install Python
    if ! check_python; then
        install_python
        if ! check_python; then
            echo -e "${RED}Failed to install Python 3.10+${NC}"
            exit 1
        fi
    fi
    
    # Install ffmpeg
    install_ffmpeg
    
    # Install Deno (optional)
    read -p "Install Deno for JS challenge support? (y/N): " install_deno_choice
    if [[ "$install_deno_choice" =~ ^[Yy]$ ]]; then
        install_deno
    fi
    
    # Setup virtual environment
    setup_venv
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Installation Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "Run the downloader with: ${CYAN}./run.sh${NC}"
    echo ""
}

main "$@"
