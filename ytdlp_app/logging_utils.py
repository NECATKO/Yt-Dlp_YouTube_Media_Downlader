from __future__ import annotations

import os
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path

# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"


def _enable_windows_ansi() -> None:
    """Enable ANSI escape codes on Windows terminals."""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # Enable VIRTUAL_TERMINAL_PROCESSING
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


_enable_windows_ansi()


def colorize_command(cmd: list[str]) -> str:
    """
    Apply syntax highlighting to command arguments.
    Highlights command name, flags, and values differently.
    """
    if not cmd:
        return ""
    
    result = []
    for i, arg in enumerate(cmd):
        if i == 0:
            # Command name - bold cyan
            result.append(f"{Colors.CYAN}{Colors.BOLD}{arg}{Colors.RESET}")
        elif arg.startswith('-'):
            # Flags/options - yellow
            result.append(f"{Colors.YELLOW}{arg}{Colors.RESET}")
        elif arg.startswith('http'):
            # URLs - bold magenta
            result.append(f"{Colors.MAGENTA}{Colors.BOLD}{arg}{Colors.RESET}")
        elif '\\' in arg or '/' in arg:
            # File paths - white
            result.append(f"{Colors.WHITE}{arg}{Colors.RESET}")
        else:
            # Values - green
            result.append(f"{Colors.GREEN}{arg}{Colors.RESET}")
    
    return " ".join(result)


def colorize_line(line: str) -> str:
    """
    Apply granular syntax highlighting to yt-dlp output.
    Highlights specific keywords, values, and patterns within lines.
    """
    # Don't process empty lines
    if not line.strip():
        return line
    
    result = line
    
    # Highlight prefixes/tags first
    result = re.sub(
        r'(\[download\])',
        rf'{Colors.GREEN}\1{Colors.RESET}',
        result
    )
    result = re.sub(
        r'(\[error\]|\[ERROR\]|ERROR:)',
        rf'{Colors.RED}{Colors.BOLD}\1{Colors.RESET}',
        result,
        flags=re.IGNORECASE
    )
    result = re.sub(
        r'(\[warning\]|\[WARNING\]|WARNING:)',
        rf'{Colors.YELLOW}\1{Colors.RESET}',
        result,
        flags=re.IGNORECASE
    )
    result = re.sub(
        r'(\[info\]|\[INFO\])',
        rf'{Colors.CYAN}\1{Colors.RESET}',
        result,
        flags=re.IGNORECASE
    )
    result = re.sub(
        r'(\[youtube\]|\[generic\]|\[ExtractAudio\]|\[Merger\]|\[ffmpeg\])',
        rf'{Colors.BLUE}\1{Colors.RESET}',
        result
    )
    result = re.sub(
        r'(\[Metadata\]|\[ThumbnailsConvertor\]|\[EmbedThumbnail\])',
        rf'{Colors.MAGENTA}\1{Colors.RESET}',
        result
    )
    
    # Highlight percentages (download progress)
    result = re.sub(
        r'\b(\d+\.?\d*%)\b',
        rf'{Colors.GREEN}{Colors.BOLD}\1{Colors.RESET}',
        result
    )
    
    # Highlight file sizes (e.g., 1.5MiB, 500KiB, 1.2GiB)
    result = re.sub(
        r'\b(\d+\.?\d*\s?(?:B|KiB|MiB|GiB|TiB|KB|MB|GB|TB))\b',
        rf'{Colors.CYAN}\1{Colors.RESET}',
        result
    )
    
    # Highlight speeds (e.g., 1.5MiB/s)
    result = re.sub(
        r'\b(\d+\.?\d*\s?(?:B|KiB|MiB|GiB)/s)\b',
        rf'{Colors.MAGENTA}\1{Colors.RESET}',
        result
    )
    
    # Highlight time values (e.g., 00:05:30, ETA 00:30)
    result = re.sub(
        r'\b(\d{1,2}:\d{2}(?::\d{2})?)\b',
        rf'{Colors.BLUE}\1{Colors.RESET}',
        result
    )
    result = re.sub(
        r'\b(ETA)\s+',
        rf'{Colors.YELLOW}\1{Colors.RESET} ',
        result
    )
    
    # Highlight video IDs and URLs
    result = re.sub(
        r'(https?://[^\s]+)',
        rf'{Colors.CYAN}{Colors.BOLD}\1{Colors.RESET}',
        result
    )
    
    # Highlight common status words
    result = re.sub(
        r'\b(Downloading|Extracting|Converting|Merging|Processing|Finished|Complete)\b',
        rf'{Colors.GREEN}\1{Colors.RESET}',
        result,
        flags=re.IGNORECASE
    )
    result = re.sub(
        r'\b(Failed|Error|Skipping)\b',
        rf'{Colors.RED}\1{Colors.RESET}',
        result,
        flags=re.IGNORECASE
    )
    
    # Highlight file paths (basic detection)
    result = re.sub(
        r'([A-Z]:\\[^\s:]+|/[^\s:]+)',
        rf'{Colors.WHITE}\1{Colors.RESET}',
        result
    )
    
    return result


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def append_log(log_path: Path | None, text: str) -> None:
    """
    Best-effort logging. Never raises.
    """
    try:
        if not log_path:
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", errors="ignore") as f:
            f.write(text)
    except Exception:
        # logging must never crash the app
        pass


def _append_log(log_path: Path | None, text: str) -> None:
    append_log(log_path, text)


def log_error(
    log_path: Path | None, title: str, ex: BaseException | None = None
) -> None:
    """
    Prints a readable error and writes full details (including traceback) to log file.
    """
    stamp = datetime.now().isoformat(timespec="seconds")
    header = f"\n[ERROR {stamp}] {title}\n"
    print(header.strip())
    if log_path:
        print(f"(details written to {log_path})")

    details = header
    if ex is not None:
        details += f"Exception: {type(ex).__name__}: {ex}\n"
        details += "Traceback:\n"
        details += "".join(traceback.format_exception(type(ex), ex, ex.__traceback__))
    details += "\n"

    append_log(log_path, details)


def log_info(log_path: Path | None, message: str) -> None:
    """
    Lightweight info-level log entry with timestamp.
    """
    stamp = datetime.now().isoformat(timespec="seconds")
    append_log(log_path, f"[INFO {stamp}] {message}\n")
