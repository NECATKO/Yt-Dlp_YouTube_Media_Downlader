from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from .logging_utils import append_log, colorize_line, log_error


def run_capture(cmd: list[str]) -> tuple[int, str, str]:
    """
    Run a command and capture stdout/stderr. Always returns a tuple to keep
    callers predictable, even on errors.
    """
    try:
        p = subprocess.run(
            cmd,
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
    """
    Stream a command to stdout while also teeing to a log file. Returns the
    process return code or 130 when interrupted by the user.
    """
    print("\n=== RUNNING COMMAND ===")
    print(" ".join(cmd))
    print("======================\n")

    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with log_path.open("a", encoding="utf-8", errors="ignore") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write(
                f"[{datetime.now().isoformat(timespec='seconds')}] CMD: {' '.join(cmd)}\n"
            )
            f.write("=" * 80 + "\n")

            p = subprocess.Popen(
                cmd,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
                newline="",  # Preserve \r for single-line progress updates
            )

            assert p.stdout is not None
            for line in p.stdout:
                # Apply syntax highlighting for console, keep raw for log
                print(colorize_line(line), end="", flush=True)
                f.write(line)

            rc = p.wait()
            print(f"\n>>> Command finished. returncode = {rc}\n")
            f.write(f"\n>>> returncode = {rc}\n")
            return rc

    except KeyboardInterrupt:
        print("\n>>> Operation cancelled by user (Ctrl+C).")
        append_log(
            log_path,
            f"\n[INFO {datetime.now().isoformat(timespec='seconds')}] Interrupted by user (Ctrl+C)\n",
        )
        return 130
    except Exception as ex:
        print("Command failed unexpectedly. See log for details.")
        log_error(log_path, "Unexpected error while running command", ex)
        return 1
