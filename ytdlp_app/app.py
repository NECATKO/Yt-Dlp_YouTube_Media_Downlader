from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

from ._version import __version__
from .archive_audit import cli_entry as audit_command
from .config import (
    default_dirs,
    ensure_dirs_interactive,
    ensure_language_interactive,
    load_config,
    load_settings,
    migrate_config,
    normalize_user_path,
)
from .i18n import set_language, t
from .logging_utils import Colors, log_error, now_stamp, paint
from .models import AppPaths, UserConfig
from .redact import register_proxy
from .session import InteractiveSession
from .ui import ConsoleUI

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .settings import SettingsIssue
    from .ui import UI

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


def _portable_app_dir() -> Path | None:
    """Return the app folder when launched as the portable app (downloader.py)."""
    try:
        argv0 = Path(sys.argv[0]) if sys.argv else None
        if argv0 and argv0.name.lower() == "downloader.py":
            return argv0.resolve().parent
    except (OSError, RuntimeError):
        pass
    return None


def _resolve_app_dir() -> Path:
    """Keep portable state beside downloader.py; installed state stays per-user."""
    return _portable_app_dir() or _installed_data_dir()


def make_streams_forgiving(*streams: TextIO | Any) -> None:
    """Make console output replace what the terminal cannot encode instead of raising.

    The messages use natural Turkish, and a terminal in a legacy code page (a Windows
    console outside the launcher's UTF-8 mode, ``LANG=C``) cannot show every letter. A
    stray "?" is a better failure than an UnicodeEncodeError in the middle of a download.
    """
    for stream in streams:
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            with contextlib.suppress(OSError, ValueError):
                reconfigure(errors="replace")


def _print_settings_issues(ui: UI, issues: Sequence[SettingsIssue]) -> None:
    """Tell the user which settings could not be used, by name."""
    for issue in issues:
        if issue.fallback is None:
            text = t("settings_issue_warning", field=issue.field, problem=issue.problem)
        else:
            text = t(
                "settings_issue_invalid",
                field=issue.field,
                problem=issue.problem,
                fallback=issue.fallback,
            )
        ui.print(paint(text, Colors.YELLOW))


def _folders_for_audit(
    cfg: dict[str, Any], app_dir: Path, portable_dir: Path | None
) -> tuple[Path, Path]:
    """The download folders as configured, or the defaults, without asking anything."""
    default_videos, default_music = default_dirs(portable_dir)

    def pick(key: str, fallback: Path) -> Path:
        value = cfg.get(key)
        if isinstance(value, str) and value.strip() and "\x00" not in value:
            return normalize_user_path(value.strip(), app_dir)
        return fallback

    return pick("videos_dir", default_videos), pick("music_dir", default_music)


def run(argv: Sequence[str] | None = None) -> int:
    make_streams_forgiving(sys.stdout, sys.stderr)
    args = list(sys.argv[1:] if argv is None else argv)
    app_name = "yt-dlp-downloader"
    portable_dir = _portable_app_dir()
    app_dir = _resolve_app_dir()
    if portable_dir is not None:
        # Imported here, not at module level: the package __init__ imports this
        # module, and "python -m ytdlp_app.portable" would otherwise find the
        # module it is about to run already imported (runpy warns about that).
        from .portable import configure_environment  # noqa: PLC0415

        # Before anything looks for ffmpeg/Deno or launches yt-dlp: the bundled
        # tools and the in-folder caches must be what every child process sees.
        configure_environment(portable_dir)
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
        migration_notes = migrate_config(cfg)

        # Language must be resolved before anything else is printed, otherwise
        # every t() lookup falls through to the raw key.
        set_language(ensure_language_interactive(ui, cfg, config_file=paths.config_file))

        if args and args[0] == "audit":
            # The archive check: no prompts, nothing changed without --apply.
            videos, music = _folders_for_audit(cfg, app_dir, portable_dir)
            return audit_command(args[1:], paths, UserConfig(app_name, videos, music))

        if migration_notes:
            ui.print(paint(t("config_migrated", count=len(migration_notes)), Colors.CYAN))

        ui.print_panel(
            t("app_version", version=__version__),
            title=t("app_title"),
            color=Colors.CYAN,
        )

        videos_base, music_base, _cfg = ensure_dirs_interactive(
            ui,
            cfg,
            config_file=paths.config_file,
            app_name=app_name,
            portable=portable_dir is not None,
        )
        user_config = UserConfig(
            app=str(_cfg.get("app") or app_name),
            videos_dir=videos_base,
            music_dir=music_base,
            saved_at=(_cfg.get("saved_at") or None),
        )

        issues: list[SettingsIssue] = []
        settings = load_settings(_cfg, issues)
        _print_settings_issues(ui, issues)
        register_proxy(settings.download.proxy)

        session = InteractiveSession(ui, user_config, paths, settings, _cfg)
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
