from __future__ import annotations

import os
import sys
from pathlib import Path

from ._version import __version__
from .config import (
    ensure_dirs_interactive,
    ensure_language_interactive,
    load_config,
    load_settings,
)
from .i18n import set_language, t
from .logging_utils import Colors, log_error, now_stamp
from .models import AppPaths, UserConfig
from .session import InteractiveSession
from .ui import ConsoleUI

_APP_DIR_NAME = "ytdlp-downloader"


def _installed_data_dir() -> Path:
    """Return a writable per-user data directory for an installed package."""
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA")
        base = Path(root).expanduser() if root else Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        root = os.environ.get("XDG_DATA_HOME")
        base = Path(root).expanduser() if root else Path.home() / ".local" / "share"
    return base / _APP_DIR_NAME


def _resolve_app_dir() -> Path:
    """Keep portable state beside downloader.py; installed state stays per-user."""
    try:
        argv0 = Path(sys.argv[0]) if sys.argv else None
        if argv0 and argv0.name.lower() == "downloader.py":
            return argv0.resolve().parent
    except (OSError, RuntimeError):
        pass
    return _installed_data_dir()


def run() -> int:
    app_name = "yt-dlp-downloader"
    app_dir = _resolve_app_dir()
    paths = AppPaths(
        app_dir=app_dir,
        config_file=app_dir / "config.json",
        logs_dir=app_dir / "logs",
        archives_dir=app_dir / "archives",
    )
    app_dir.mkdir(parents=True, exist_ok=True)

    ui = ConsoleUI()

    try:
        # 0) config: load or create paths (once)
        cfg = load_config(paths.config_file)

        # Language must be resolved before anything else is printed, otherwise
        # every t() lookup falls through to the raw key.
        set_language(ensure_language_interactive(ui, cfg, config_file=paths.config_file))

        ui.print_panel(
            t("app_version", version=__version__),
            title=t("app_title"),
            color=Colors.CYAN,
        )

        videos_base, music_base, _cfg = ensure_dirs_interactive(
            ui, cfg, config_file=paths.config_file, app_name=app_name
        )
        user_config = UserConfig(
            app=str(_cfg.get("app") or app_name),
            videos_dir=videos_base,
            music_dir=music_base,
            saved_at=(_cfg.get("saved_at") or None),
        )

        session = InteractiveSession(ui, user_config, paths, load_settings(_cfg), _cfg)
        return session.run_loop()

    except (KeyboardInterrupt, EOFError):
        ui.print(f"\n>>> {t('status_cancelled')} (Ctrl+C).")
        return 0
    except Exception as ex:
        # If something crashes before session loop or outside of it there is no
        # session log yet, so open a dedicated crash log to keep the traceback.
        crash_log = paths.logs_dir / f"crash_{now_stamp()}.log"
        log_error(crash_log, t("error_unexpected"), ex)
        return 1
