"""Configuration management for ytdlp_app.

This module handles loading, saving, and validating user configuration,
as well as interactive setup for first-run configuration.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .logging_utils import Colors
from .ui import UI


def normalize_user_path(s: str) -> Path:
    """Normalize and expand a user-provided path string.

    Expands environment variables (e.g., %USERPROFILE% on Windows)
    and user home directory references (e.g., ~).

    Args:
        s: The path string to normalize.

    Returns:
        A Path object with all variables and references expanded.

    Example:
        >>> normalize_user_path("~/Downloads")
        PosixPath('/home/user/Downloads')
        >>> normalize_user_path("%USERPROFILE%\\Videos")
        WindowsPath('C:/Users/User/Videos')
    """
    expanded = os.path.expandvars(s)
    return Path(expanded).expanduser()


def default_dirs() -> tuple[Path, Path]:
    """Get the default download directories.

    Returns:
        A tuple of (videos_dir, music_dir) using standard user directories.
    """
    return Path.home() / "Videos", Path.home() / "Music"


def load_config(config_file: Path) -> dict[str, Any]:
    """Load configuration from a JSON file.

    Args:
        config_file: Path to the configuration file.

    Returns:
        The configuration dictionary, or empty dict if file doesn't exist
        or cannot be parsed.
    """
    if not config_file.exists():
        return {}
    try:
        return json.loads(config_file.read_text(encoding="utf-8"))
    except Exception:
        print("WARNING: config.json could not be read; it will be recreated.")
        return {}


def save_config(config_file: Path, cfg: dict[str, Any]) -> None:
    """Save configuration to a JSON file.

    Args:
        config_file: Path to the configuration file.
        cfg: The configuration dictionary to save.
    """
    config_file.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_config(config_file: Path) -> None:
    """Delete the configuration file if it exists.

    Args:
        config_file: Path to the configuration file.
    """
    if config_file.exists():
        config_file.unlink()


def ensure_dirs_interactive(
    ui: UI, existing_cfg: dict, *, config_file: Path, app_name: str
) -> tuple[Path, Path, dict]:
    """
    Ask for download folders on first run. On later runs, reuse config.json and
    remind the user it can be edited manually to change locations.
    """
    def_videos, def_music = default_dirs()

    v_raw = (existing_cfg.get("videos_dir") or "").strip()
    m_raw = (existing_cfg.get("music_dir") or "").strip()

    videos_dir = normalize_user_path(v_raw) if v_raw else None
    music_dir = normalize_user_path(m_raw) if m_raw else None

    def announce_paths(v_dir: Path, m_dir: Path) -> None:
        ui.print(
            f"{Colors.CYAN}Using download folders ({Colors.YELLOW}Videos:{Colors.RESET} {Colors.WHITE}{v_dir}{Colors.RESET} {Colors.CYAN}|{Colors.RESET} {Colors.YELLOW}Music:{Colors.RESET} {Colors.WHITE}{m_dir}{Colors.RESET}{Colors.CYAN}).{Colors.RESET}"
        )
        ui.print(
            f"{Colors.YELLOW}To change these later, edit config.json at:{Colors.RESET} {Colors.WHITE}{config_file}{Colors.RESET}\n"
        )

    # If config already has both values, use them without asking again.
    if videos_dir and music_dir:
        videos_dir.mkdir(parents=True, exist_ok=True)
        music_dir.mkdir(parents=True, exist_ok=True)
        announce_paths(videos_dir, music_dir)
        return videos_dir, music_dir, existing_cfg

    ui.print(
        f"{Colors.YELLOW}{Colors.BOLD}Download folders not set yet. Configure them now (this is only asked once).{Colors.RESET}"
    )

    def ask_path(label: str, default: Path) -> Path:
        ui.print(
            f"\n{Colors.CYAN}Enter folder path for {Colors.BOLD}{label}{Colors.RESET}{Colors.CYAN} (blank = default):{Colors.RESET}"
        )
        ui.print(f"{Colors.YELLOW}Default:{Colors.RESET} {Colors.WHITE}{default}{Colors.RESET}")
        s = ui.ask_text(f"{Colors.GREEN}Path: {Colors.RESET}")
        if not s:
            return default
        return normalize_user_path(s)

    videos_dir = ask_path("VIDEOS", videos_dir or def_videos)
    music_dir = ask_path("MUSIC", music_dir or def_music)

    videos_dir.mkdir(parents=True, exist_ok=True)
    music_dir.mkdir(parents=True, exist_ok=True)

    new_cfg = {
        "app": app_name,
        "videos_dir": str(videos_dir),
        "music_dir": str(music_dir),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_config(config_file, new_cfg)

    ui.print(f"\n{Colors.GREEN}{Colors.BOLD}Settings saved:{Colors.RESET}")
    ui.print(f"  {Colors.YELLOW}Videos:{Colors.RESET} {Colors.WHITE}{videos_dir}{Colors.RESET}")
    ui.print(f"  {Colors.YELLOW}Music :{Colors.RESET} {Colors.WHITE}{music_dir}{Colors.RESET}")
    ui.print(f"  {Colors.YELLOW}Config:{Colors.RESET} {Colors.WHITE}{config_file}{Colors.RESET}\n")
    announce_paths(videos_dir, music_dir)

    return videos_dir, music_dir, new_cfg
