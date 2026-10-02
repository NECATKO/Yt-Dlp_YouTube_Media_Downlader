#!/bin/bash
# install.sh - sets up ytdlp-downloader
#
# Linux: a portable runtime in ./runtime, with no sudo and no system packages.
#   runtime/python   relocatable Python (python-build-standalone), with yt-dlp
#   runtime/ffmpeg   ffmpeg + ffprobe
#   runtime/deno     Deno, for YouTube's JavaScript challenges
# Every download is checked against the sha256 pinned in runtime.lock. Safe to
# run repeatedly: it only fetches what is missing or re-pinned.
#
# macOS: the system installation (Homebrew Python/ffmpeg + a .venv), as before.
#
# Usage: bash install.sh [--quiet]   (or ./install.sh once it is executable)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

QUIET=0
if [[ "${1:-}" == "--quiet" ]]; then
    QUIET=1
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

say() {
    if [[ $QUIET -eq 0 ]]; then
        echo -e "$@"
    fi
}

die() {
    echo -e "${RED}ERROR: $*${NC}" >&2
    exit 1
}

# ==============================================================================
# Linux: portable runtime
# ==============================================================================

RUNTIME_DIR="$SCRIPT_DIR/runtime"
PYTHON_DIR="$RUNTIME_DIR/python"
PYTHON_EXE="$PYTHON_DIR/bin/python3"
# Records which runtime.lock pin the unpacked Python came from.
PYTHON_MARKER="$PYTHON_DIR/.lock-sha256"

linux_platform_key() {
    local arch
    arch="$(uname -m)"
    case "$arch" in
        x86_64|amd64) arch="x86_64" ;;
        aarch64|arm64) arch="aarch64" ;;
        *) die "The portable runtime supports x86_64 and aarch64 Linux, not $arch." ;;
    esac
    # The pinned builds link against glibc; musl systems (Alpine) cannot run them.
    if ldd --version 2>&1 | grep -qi musl; then
        die "musl-based systems (such as Alpine) are not supported by the portable runtime."
    fi
    echo "linux-$arch"
}

# Prints "<sha256> <url>" for a component on a platform.
lock_entry() {
    local component="$1" platform="$2" found
    found="$(awk -v c="$component" -v p="$platform" \
        '$1 !~ /^#/ && NF == 4 && $1 == c && $2 == p { print $3, $4; exit }' runtime.lock)"
    [[ -n "$found" ]] || die "runtime.lock has no $component build for $platform"
    echo "$found"
}

fetch() {
    local url="$1" out="$2"
    if command -v curl &> /dev/null; then
        curl -fL --retry 3 --progress-bar -o "$out" "$url"
    elif command -v wget &> /dev/null; then
        wget -q --show-progress -O "$out" "$url"
    else
        die "curl or wget is required to download the runtime."
    fi
}

install_python() {
    local sha="$1" url="$2" downloads archive partial actual staging
    downloads="$RUNTIME_DIR/downloads"
    mkdir -p "$downloads"
    archive="$downloads/${url##*/}"
    partial="$archive.part"

    echo -e "${CYAN}Downloading Python (${url##*/})...${NC}"
    if ! fetch "$url" "$partial"; then
        rm -f "$partial"
        die "Python download failed."
    fi

    actual="$(sha256sum "$partial" | awk '{ print $1 }')"
    if [[ "$actual" != "$sha" ]]; then
        rm -f "$partial"
        die "Checksum mismatch for Python: expected $sha, got $actual. The file was discarded."
    fi
    mv -f "$partial" "$archive"

    # Unpack beside the old copy and swap at the end, so an interrupted run
    # never leaves a half-unpacked Python behind.
    staging="$RUNTIME_DIR/python-staging"
    rm -rf "$staging"
    mkdir -p "$staging"
    tar -xzf "$archive" -C "$staging"
    [[ -x "$staging/python/bin/python3" ]] || die "Unexpected archive layout: $archive"

    # Swap without a gap: the old Python is renamed aside, not deleted, until the new one
    # is in place; if the rename in fails the old one goes back.
    local old="$RUNTIME_DIR/python.old"
    rm -rf "$old"
    if [[ -d "$PYTHON_DIR" ]]; then
        mv "$PYTHON_DIR" "$old" || die "Could not move the old Python aside."
    fi
    if ! mv "$staging/python" "$PYTHON_DIR"; then
        if [[ -d "$old" ]]; then
            mv "$old" "$PYTHON_DIR"
        fi
        die "Could not put the new Python in place; the previous one was kept."
    fi
    printf '%s' "$sha" > "$PYTHON_MARKER"
    rm -rf "$old" "$staging" "$archive"
    echo -e "${GREEN}Python installed: $PYTHON_EXE${NC}"
}

# A run killed between "old Python aside" and "new Python in place" leaves only python.old:
# put it back, or drop it when the real one is there.
recover_python() {
    local old="$RUNTIME_DIR/python.old"
    [[ -d "$old" ]] || return 0
    if [[ -x "$PYTHON_EXE" ]]; then
        rm -rf "$old"
    else
        rm -rf "$PYTHON_DIR"
        mv "$old" "$PYTHON_DIR"
    fi
}

portable_install() {
    [[ -f downloader.py ]] || die "install.sh must be run from the program folder."

    local platform entry sha url current=""
    recover_python
    platform="$(linux_platform_key)"
    entry="$(lock_entry python "$platform")"
    sha="${entry%% *}"
    url="${entry#* }"

    if [[ -f "$PYTHON_MARKER" ]]; then
        current="$(cat "$PYTHON_MARKER")"
    fi
    if [[ -x "$PYTHON_EXE" && "$current" == "$sha" ]]; then
        say "Python is up to date."
    else
        install_python "$sha" "$url"
    fi

    # yt-dlp, ffmpeg and Deno (and the weekly yt-dlp update).
    PYTHONNOUSERSITE=1 "$PYTHON_EXE" -s -m ytdlp_app.portable ensure \
        || die "Setting up the portable runtime failed."

    say "${GREEN}Portable runtime ready.${NC} Run the downloader with: ${CYAN}./run.sh${NC}"
}

# ==============================================================================
# macOS: system installation (unchanged behavior)
# ==============================================================================

# The interpreter the .venv is made with, once found.
PYTHON_BIN=""

# Whether $1 runs and is Python 3.11 or newer (compared by Python itself, so 4.0 passes).
python_ok() {
    "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' &> /dev/null
}

# The first Python 3.11+ on the PATH, versioned names first: Homebrew links python3.12 and
# friends onto the PATH, while "python3" may still be an older system or python.org one.
find_python() {
    local candidate path
    for candidate in python3.14 python3.13 python3.12 python3.11 python3; do
        path="$(command -v "$candidate" 2> /dev/null)" || continue
        if python_ok "$path"; then
            PYTHON_BIN="$path"
            return 0
        fi
    done
    return 1
}

require_brew() {
    if ! command -v brew &> /dev/null; then
        echo -e "${RED}Homebrew not found. Please install Homebrew first:${NC}"
        echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
}

macos_install() {
    if ! find_python; then
        echo -e "${YELLOW}Installing Python 3.11+...${NC}"
        require_brew
        brew install python@3.12
        # Use the interpreter brew just installed, by its own path: installing it does not
        # change which "python3" comes first on the PATH.
        PYTHON_BIN="$(brew --prefix python@3.12)/bin/python3.12"
        python_ok "$PYTHON_BIN" || die "Failed to install Python 3.11+"
    fi
    echo -e "${GREEN}Using Python: $PYTHON_BIN${NC}"

    if command -v ffmpeg &> /dev/null; then
        echo -e "${GREEN}ffmpeg already installed${NC}"
    else
        echo -e "${YELLOW}Installing ffmpeg...${NC}"
        require_brew
        brew install ffmpeg
    fi

    if ! command -v deno &> /dev/null; then
        read -r -p "Install Deno for JS challenge support? (y/N): " install_deno_choice
        if [[ "$install_deno_choice" =~ ^[Yy]$ ]]; then
            require_brew
            brew install deno
        fi
    fi

    echo -e "${YELLOW}Creating virtual environment...${NC}"
    if [[ ! -d ".venv" ]]; then
        "$PYTHON_BIN" -m venv .venv
    fi
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -e .

    echo -e "${GREEN}Installation complete!${NC} Run the downloader with: ${CYAN}./run.sh${NC}"
}

# ==============================================================================

case "$(uname -s)" in
    Linux)  portable_install ;;
    Darwin) macos_install ;;
    *)      die "Unsupported operating system: $(uname -s). On Windows, use Run.bat." ;;
esac
