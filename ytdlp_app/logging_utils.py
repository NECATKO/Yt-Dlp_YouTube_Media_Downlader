from __future__ import annotations

import os
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


def colorize_line(line: str) -> str:
    """
    Apply syntax highlighting to yt-dlp output lines based on their prefix.
    Returns the colorized line for console display.
    """
    stripped = line.lstrip()
    
    # Download progress - green
    if stripped.startswith("[download]"):
        return f"{Colors.GREEN}{line}{Colors.RESET}"
    
    # Errors - red
    if stripped.startswith(("[error]", "ERROR:", "[ERROR")):
        return f"{Colors.RED}{Colors.BOLD}{line}{Colors.RESET}"
    
    # Warnings - yellow
    if stripped.startswith(("[warning]", "WARNING:", "[WARNING")):
        return f"{Colors.YELLOW}{line}{Colors.RESET}"
    
    # Info messages - cyan
    if stripped.startswith(("[info]", "[INFO")):
        return f"{Colors.CYAN}{line}{Colors.RESET}"
    
    # Extraction/processing - blue
    if stripped.startswith(("[youtube]", "[generic]", "[ExtractAudio]", "[Merger]", "[ffmpeg]")):
        return f"{Colors.BLUE}{line}{Colors.RESET}"
    
    # Metadata - magenta
    if stripped.startswith(("[Metadata]", "[ThumbnailsConvertor]", "[EmbedThumbnail]")):
        return f"{Colors.MAGENTA}{line}{Colors.RESET}"
    
    return line


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
