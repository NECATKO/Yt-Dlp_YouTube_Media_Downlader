from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path


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

    details = header
    if ex is not None:
        details += f"Exception: {type(ex).__name__}: {ex}\n"
        details += "Traceback:\n"
        details += "".join(traceback.format_exception(type(ex), ex, ex.__traceback__))
    details += "\n"

    append_log(log_path, details)
