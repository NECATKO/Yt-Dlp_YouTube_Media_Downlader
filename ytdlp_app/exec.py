"""Command execution utilities for ytdlp_app.

This module provides functions for running external commands (primarily yt-dlp)
with output capture and logging capabilities.
"""

from __future__ import annotations

import io
import subprocess
from datetime import datetime
from typing import TYPE_CHECKING

from .logging_utils import (
    Colors,
    append_log,
    colorize_command,
    colorize_line,
    log_error,
    paint,
)

if TYPE_CHECKING:
    from pathlib import Path


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
            cmd,
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


def run_cmd_tee(cmd: list[str], log_path: Path) -> int:
    """Run a command with live output streaming and logging.

    Streams command output to stdout in real-time with syntax highlighting,
    while also logging the raw output to a file.

    Args:
        cmd: The command and arguments to execute.
        log_path: Path to the log file for capturing output.

    Returns:
        The process return code.
        Returns 130 on keyboard interrupt.
        Returns 1 on unexpected errors.
    """
    print(f"\n{Colors.BOLD}=== RUNNING COMMAND ==={Colors.RESET}")
    print(colorize_command(cmd))
    print(f"{Colors.BOLD}======================={Colors.RESET}\n")

    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with log_path.open("a", encoding="utf-8", errors="ignore") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] CMD: {' '.join(cmd)}\n")
            f.write("=" * 80 + "\n")

            p = subprocess.Popen(
                cmd,
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

            rc = p.wait()
            if rc == 0:
                print(
                    "\n"
                    + paint(">>> Command finished successfully.", Colors.GREEN, Colors.BOLD)
                    + "\n"
                )
            # A non-zero code is reported by the caller, which has the context
            # to know whether it is fatal (see the two-stage compatibility flow).

            f.write(f"\n>>> returncode = {rc}\n")
            return rc

    except KeyboardInterrupt:
        print("\n>>> Operation cancelled by user (Ctrl+C).")
        append_log(
            log_path,
            f"\n[INFO {datetime.now().isoformat(timespec='seconds')}] "
            "Interrupted by user (Ctrl+C)\n",
        )
        return 130
    except Exception as ex:
        print("Command failed unexpectedly. See log for details.")
        log_error(log_path, "Unexpected error while running command", ex)
        return 1
