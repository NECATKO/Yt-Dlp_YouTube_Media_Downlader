"""Command execution utilities for ytdlp_app.

This module provides functions for running external commands (primarily yt-dlp)
with output capture and logging capabilities.
"""

from __future__ import annotations

import io
import re
import subprocess
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from .i18n import t
from .logging_utils import (
    Colors,
    append_log,
    colorize_command,
    colorize_line,
    log_error,
    paint,
)
from .system import ytdlp_command

if TYPE_CHECKING:
    from pathlib import Path

#: Returned by run_cmd_tee when it stopped yt-dlp because YouTube started
#: blocking. 75 is EX_TEMPFAIL: the same command will work again later.
BAN_RETURN_CODE = 75

#: How long a stopped yt-dlp gets to exit before it is killed outright.
_TERMINATE_TIMEOUT = 10


class BanSignal(StrEnum):
    """Why YouTube is refusing us. The values are written to the log."""

    RATE_LIMITED = "HTTP 429 Too Many Requests"
    BOT_CHECK = "Sign in to confirm you're not a bot"


_RATE_LIMIT_RE = re.compile(r"HTTP Error 429|429:? Too Many Requests", re.IGNORECASE)
# YouTube writes the apostrophe as U+2019; accept the ASCII one as well.
_BOT_CHECK_RE = re.compile(r"Sign in to confirm you[\u2019']re not a bot", re.IGNORECASE)
# Only yt-dlp's own diagnostics count. A download line can quote a video title,
# and a title may well mention either phrase. "Got error:" is how the fragment
# downloader reports a failed attempt before retrying it.
_DIAGNOSTIC_MARKERS = ("ERROR:", "WARNING:", "Got error:")


def detect_ban_signal(line: str) -> BanSignal | None:
    """Recognize the output yt-dlp prints once YouTube starts blocking requests.

    Args:
        line: One line of yt-dlp output.

    Returns:
        The kind of block, or None for any other line.
    """
    if not any(marker in line for marker in _DIAGNOSTIC_MARKERS):
        return None
    if _BOT_CHECK_RE.search(line):
        return BanSignal.BOT_CHECK
    if _RATE_LIMIT_RE.search(line):
        return BanSignal.RATE_LIMITED
    return None


def resolve_program(cmd: list[str]) -> list[str]:
    """Replace the logical program name "yt-dlp" with how to actually run it.

    Command builders keep writing "yt-dlp" so commands stay readable in the UI
    and in tests; the real launcher (usually "<python> -m yt_dlp") is only
    substituted here, right before execution. If yt-dlp cannot be found the
    command is left as is and fails with a clear "not found" error.
    """
    if cmd and cmd[0] == "yt-dlp":
        launcher = ytdlp_command()
        if launcher:
            return [*launcher, *cmd[1:]]
    return cmd


def find_ban_signal(text: str) -> BanSignal | None:
    """Scan multi-line output (such as a captured stderr) for a ban signal."""
    for line in text.splitlines():
        signal = detect_ban_signal(line)
        if signal is not None:
            return signal
    return None


def _stop_process(p: subprocess.Popen[bytes]) -> None:
    """Stop yt-dlp, escalating to kill if it does not exit in time."""
    p.terminate()
    try:
        p.wait(timeout=_TERMINATE_TIMEOUT)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait()


def run_capture(cmd: list[str]) -> tuple[int, str, str]:
    """Run a command and capture its output.

    Executes a command synchronously and captures both stdout and stderr.
    Always returns a tuple to keep callers predictable, even on errors.

    Args:
        cmd: The command and arguments to execute.

    Returns:
        A tuple of (return_code, stdout, stderr).
        On keyboard interrupt, returns (130, "", "Interrupted by user").
        On other exceptions, returns (1, "", error_message).
    """
    try:
        p = subprocess.run(
            resolve_program(cmd),
            check=False,
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return p.returncode, p.stdout, p.stderr
    except KeyboardInterrupt:
        return 130, "", "Interrupted by user"
    except Exception as ex:
        return 1, "", f"{type(ex).__name__}: {ex}"


def run_cmd_tee(cmd: list[str], log_path: Path, *, stop_on_ban: bool = False) -> int:
    """Run a command with live output streaming and logging.

    Streams command output to stdout in real-time with syntax highlighting,
    while also logging the raw output to a file.

    Args:
        cmd: The command and arguments to execute.
        log_path: Path to the log file for capturing output.
        stop_on_ban: Stop the command as soon as its output shows YouTube
            rate limiting (HTTP 429) or demanding a bot check. Continuing to
            send requests at that point only extends the block.

    Returns:
        The process return code.
        Returns BAN_RETURN_CODE when stop_on_ban stopped the command.
        Returns 130 on keyboard interrupt.
        Returns 1 on unexpected errors.
    """
    header = t("command_running")
    print(f"\n{Colors.BOLD}=== {header} ==={Colors.RESET}")
    print(colorize_command(cmd))
    print(f"{Colors.BOLD}{'=' * (len(header) + 8)}{Colors.RESET}\n")

    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with log_path.open("a", encoding="utf-8", errors="ignore") as f:
            f.write("\n" + "=" * 80 + "\n")
            # The log records what really ran, launcher included, for debugging;
            # the console above shows the shorter logical command.
            real_cmd = resolve_program(cmd)
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] CMD: {' '.join(real_cmd)}\n")
            f.write("=" * 80 + "\n")

            p = subprocess.Popen(
                real_cmd,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                # Use binary mode to manually handle carriage returns
                text=False,
            )

            assert p.stdout is not None
            # Wrap stdout to handle \r without translating to \n
            # newline="" ensures \r is preserved as-is
            reader = io.TextIOWrapper(p.stdout, encoding="utf-8", newline="", errors="replace")

            for line in reader:
                # Apply syntax highlighting for console, keep raw for log
                print(colorize_line(line), end="", flush=True)
                f.write(line)

                signal = detect_ban_signal(line) if stop_on_ban else None
                if signal is not None:
                    # Stop reading before stopping the process: a merge left
                    # running by yt-dlp could otherwise hold the pipe open.
                    _stop_process(p)
                    reader.close()
                    f.write(
                        f"\n[BAN-GUARD {datetime.now().isoformat(timespec='seconds')}] "
                        f"Stopped yt-dlp: {signal.value} detected in: {line.strip()}\n"
                        f">>> returncode = {BAN_RETURN_CODE}\n"
                    )
                    return BAN_RETURN_CODE

            rc = p.wait()
            if rc == 0:
                message = f">>> {t('command_success', code=rc)}"
                print("\n" + paint(message, Colors.GREEN, Colors.BOLD) + "\n")
            # A non-zero code is reported by the caller, which has the context
            # to know whether it is fatal (see the two-stage compatibility flow).

            f.write(f"\n>>> returncode = {rc}\n")
            return rc

    except KeyboardInterrupt:
        print(f"\n>>> {t('status_cancelled')} (Ctrl+C).")
        # The log stays English: it is a diagnostic artifact, not UI.
        append_log(
            log_path,
            f"\n[INFO {datetime.now().isoformat(timespec='seconds')}] "
            "Interrupted by user (Ctrl+C)\n",
        )
        return 130
    except Exception as ex:
        print(t("command_failed"))
        log_error(log_path, "Unexpected error while running command", ex)
        return 1
