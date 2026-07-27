"""Configuration management for ytdlp_app.

This module handles loading, saving, and validating user configuration,
as well as interactive setup for first-run configuration.
"""

from __future__ import annotations

import contextlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .i18n import get_available_languages, get_language_name, t
from .logging_utils import Colors, paint
from .settings import AppSettings

if TYPE_CHECKING:
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
        data = json.loads(config_file.read_text(encoding="utf-8"))
    except Exception:
        # Runs before the language is known -- the config being unreadable is
        # exactly what would have told us which language to use -- so this
        # falls back to English.
        print(paint(t("config_read_warning"), Colors.YELLOW))
        return {}
    # A JSON file whose top level is a list or scalar is as unusable as a
    # corrupt one; callers rely on getting a mapping back.
    return data if isinstance(data, dict) else {}


def save_config(config_file: Path, cfg: dict[str, Any]) -> None:
    """Save configuration to a JSON file.

    Args:
        config_file: Path to the configuration file.
        cfg: The configuration dictionary to save.
    """
    config_file.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def load_settings(cfg: dict[str, Any]) -> AppSettings:
    """Read the advanced settings out of a loaded configuration dict.

    Configs written before settings existed simply have no "settings" key, so
    they resolve to the defaults and need no migration.

    Args:
        cfg: The configuration dictionary from load_config().

    Returns:
        The parsed settings, or all-defaults when the key is absent or unusable.
    """
    raw = cfg.get("settings")
    if not isinstance(raw, dict):
        return AppSettings()
    return AppSettings.from_dict(raw)


def save_settings(config_file: Path, cfg: dict[str, Any], settings: AppSettings) -> None:
    """Write the advanced settings back into config.json.

    Mutates ``cfg`` so the caller keeps holding the current state.

    Args:
        config_file: Path to the configuration file.
        cfg: The configuration dictionary to update and persist.
        settings: The settings to store.
    """
    cfg["settings"] = settings.to_dict()
    cfg["saved_at"] = datetime.now().isoformat(timespec="seconds")
    save_config(config_file, cfg)


def delete_config(config_file: Path) -> None:
    """Delete the configuration file if it exists.

    Args:
        config_file: Path to the configuration file.
    """
    if config_file.exists():
        config_file.unlink()


def ensure_language_interactive(ui: UI, existing_cfg: dict, *, config_file: Path) -> str:
    """Resolve the interface language, asking once on first run.

    The choice is persisted to config.json so later runs are silent. It can be
    changed afterwards from the in-app settings menu (see settings_menu.py).

    Args:
        ui: The UI interface.
        existing_cfg: The loaded configuration dict (mutated in place).
        config_file: Path to the configuration file.

    Returns:
        The resolved language code.
    """
    available = get_available_languages()
    saved = str(existing_cfg.get("language") or "").strip().lower()

    if saved in available:
        return saved
    if len(available) < 2:
        return available[0] if available else "en"

    # Nothing recorded yet. Translations are not loaded at this point, so the
    # prompt has to carry its own text in every language it offers.
    choice = ui.pick(
        "Select language / Dil secin",
        [get_language_name(code) for code in available],
    )
    language = available[choice - 1]

    existing_cfg["language"] = language
    # A read-only config location must not stop the app from starting.
    with contextlib.suppress(Exception):
        save_config(config_file, existing_cfg)

    return language


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
        ui.print(paint(t("config_using"), Colors.CYAN))
        ui.print(paint(t("config_videos", path=v_dir), Colors.YELLOW))
        ui.print(paint(t("config_music", path=m_dir), Colors.YELLOW))
        ui.print(paint(t("config_edit_hint", path=config_file), Colors.YELLOW) + "\n")

    # If config already has both values, use them without asking again.
    if videos_dir and music_dir:
        videos_dir.mkdir(parents=True, exist_ok=True)
        music_dir.mkdir(parents=True, exist_ok=True)
        announce_paths(videos_dir, music_dir)
        return videos_dir, music_dir, existing_cfg

    ui.print(paint(t("config_setup_title"), Colors.YELLOW, Colors.BOLD))

    def ask_path(prompt: str, default: Path) -> Path:
        ui.print("\n" + paint(prompt, Colors.CYAN))
        ui.print(paint(t("config_default", path=default), Colors.YELLOW))
        s = ui.ask_text(paint(t("config_path_prompt"), Colors.GREEN))
        if not s:
            return default
        return normalize_user_path(s)

    videos_dir = ask_path(t("config_videos_prompt"), videos_dir or def_videos)
    music_dir = ask_path(t("config_music_prompt"), music_dir or def_music)

    videos_dir.mkdir(parents=True, exist_ok=True)
    music_dir.mkdir(parents=True, exist_ok=True)

    # Start from the existing config so keys we do not own here (notably the
    # language chosen by ensure_language_interactive) survive the rewrite.
    new_cfg = dict(existing_cfg)
    new_cfg.update(
        {
            "app": app_name,
            "videos_dir": str(videos_dir),
            "music_dir": str(music_dir),
            "saved_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    save_config(config_file, new_cfg)

    ui.print("\n" + paint(t("config_saved"), Colors.GREEN, Colors.BOLD))
    ui.print("  " + paint(t("config_videos", path=videos_dir), Colors.YELLOW))
    ui.print("  " + paint(t("config_music", path=music_dir), Colors.YELLOW))
    ui.print("  " + paint(t("config_file_at", path=config_file), Colors.YELLOW) + "\n")
    announce_paths(videos_dir, music_dir)

    return videos_dir, music_dir, new_cfg
