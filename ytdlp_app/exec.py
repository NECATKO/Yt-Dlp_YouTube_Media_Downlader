"""Command execution utilities for ytdlp_app.

This module provides functions for running external commands (primarily yt-dlp)
with output capture and logging capabilities.
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import signal
import subprocess
import threading
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol

from .i18n import t
from .logging_utils import (
    Colors,
    append_log,
    colorize_command,
    colorize_line,
    console_print,
    log_error,
    paint,
)
from .redact import display_command, redact_secrets
from .system import ytdlp_command

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

#: Returned by run_cmd_tee when it stopped yt-dlp because YouTube started
#: blocking. 75 is EX_TEMPFAIL: the same command will work again later.
BAN_RETURN_CODE = 75

#: Returned by run_capture when the process outran its time limit and was stopped.
#: 124 is the code coreutils' timeout(1) uses for the same thing.
TIMEOUT_RETURN_CODE = 124

# How long each step of a stop waits for the process to leave before the next, harder
# step. SIGINT first: it is what Ctrl+C sends, and yt-dlp answers it by stopping ffmpeg and
# exiting cleanly, leaving its partial files for --continue to resume; SIGTERM kills it without
# that chance; SIGKILL cannot be ignored.
_INTERRUPT_GRACE = 5.0
_TERMINATE_TIMEOUT = 5.0
_KILL_WAIT = 5.0
_POSIX_ESCALATION: tuple[tuple[int, str], ...] = (
    (signal.SIGINT, "_INTERRUPT_GRACE"),
    (signal.SIGTERM, "_TERMINATE_TIMEOUT"),
    (getattr(signal, "SIGKILL", signal.SIGTERM), "_KILL_WAIT"),
)

# Windows: CTRL_BREAK_EVENT is the signal a new process group can be sent (the console's
# Ctrl+C event cannot be aimed at one), and this flag is what gives the child its own group.
_CTRL_BREAK = getattr(signal, "CTRL_BREAK_EVENT", 1)
_CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)

# How often the cancel watcher looks up from waiting on the cancel event to see whether the
# command finished on its own. It bounds how long a finished call waits for its watcher.
_CANCEL_POLL = 0.05


class OutputSink(Protocol):
    """Where run_cmd_tee shows the command it runs and everything the command prints.

    The log file is written separately and is the same whatever the sink.
    """

    def write(self, text: str, *, end: str = "\n") -> None:
        """Show text: a line of our own, or (with ``end=""``) a line of the command's
        output, colourised, with its own terminator."""
        ...

    def progress(self, line: str) -> None:
        """Show a progress redraw: a line of the command's output that ends in a bare
        carriage return, as read (secrets masked, no colour added)."""
        ...


class ConsoleSink:
    """The terminal: progress redraws are printed like any other line, so the bare
    carriage return makes the terminal overwrite them in place."""

    def write(self, text: str, *, end: str = "\n") -> None:
        console_print(text, end=end, flush=True)

    def progress(self, line: str) -> None:
        console_print(colorize_line(line), end="", flush=True)


class BanSignal(StrEnum):
    """Why YouTube is refusing us. The values are written to the log."""

    RATE_LIMITED = "HTTP 429 Too Many Requests"
    BOT_CHECK = "Sign in to confirm you're not a bot"


_RATE_LIMIT_RE = re.compile(r"HTTP Error 429|429:? Too Many Requests", re.IGNORECASE)
# YouTube writes the apostrophe as U+2019; accept the ASCII one as well, and
# U+FFFD, which is what U+2019 becomes if a child's output was mis-decoded.
_BOT_CHECK_RE = re.compile(r"Sign in to confirm you[\u2019'\ufffd]re not a bot", re.IGNORECASE)
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


def child_env() -> dict[str, str]:
    """Environment for the tools we launch: force their output to UTF-8.

    Output is decoded as UTF-8 here. A Python child (yt-dlp) otherwise writes
    to a pipe in the Windows ANSI code page, which turns non-ASCII titles, and
    the apostrophe in YouTube's bot-check message, into replacement characters.
    Run.bat already sets both variables; this covers every other launch path.
    """
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


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


def _popen_kwargs() -> dict[str, Any]:
    """Start the child in its own process group (POSIX: its own session).

    Everything it starts (yt-dlp starts ffmpeg) then shares that group, so it can be
    stopped as a unit, and a terminal's Ctrl+C no longer reaches it behind our back:
    stopping it is our job, done explicitly and on every exit path.
    """
    if os.name == "nt":
        return {"creationflags": _CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _killpg(pgid: int, sig: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pgid, sig)


def _stop_posix(p: subprocess.Popen[Any]) -> None:
    """SIGINT, then SIGTERM, then SIGKILL to the whole group, waiting between them."""
    pgid = p.pid  # start_new_session made the child its own group leader
    for sig, grace_name in _POSIX_ESCALATION:
        if p.poll() is not None:
            break
        _killpg(pgid, sig)
        with contextlib.suppress(subprocess.TimeoutExpired):
            p.wait(timeout=globals()[grace_name])
    if p.poll() is None:
        p.wait()
    # The leader may be gone while something it started (an ffmpeg that got no signal
    # in time) is not: sweep the group. Nothing is left to signal on the usual path.
    _killpg(pgid, getattr(signal, "SIGKILL", signal.SIGTERM))


def _stop_windows(
    p: subprocess.Popen[Any],
    grace: float | None = None,
    run: Callable[..., Any] = subprocess.run,
) -> None:
    """CTRL_BREAK to the group, then ``taskkill /T /F`` on the whole tree.

    The tree is always swept, also when the leader left on its own, because ffmpeg can
    outlive the yt-dlp that started it. ``/T`` follows the parent links, so it finds
    the descendants without a job object.
    """
    grace = _INTERRUPT_GRACE if grace is None else grace
    if p.poll() is None:
        with contextlib.suppress(OSError, ValueError):
            p.send_signal(_CTRL_BREAK)
        with contextlib.suppress(subprocess.TimeoutExpired):
            p.wait(timeout=grace)
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        run(
            ["taskkill", "/PID", str(p.pid), "/T", "/F"],
            capture_output=True,
            check=False,
            timeout=_KILL_WAIT,
        )
    if p.poll() is None:
        p.wait()


def _close_pipes(p: subprocess.Popen[Any]) -> None:
    for stream in (p.stdin, p.stdout, p.stderr):
        if stream is not None:
            with contextlib.suppress(OSError, ValueError):
                stream.close()


def stop_process_tree(p: subprocess.Popen[Any], *, close_pipes: bool = True) -> None:
    """Stop a process and everything it started, reap it and close its pipes.

    Safe on a process that already finished (it then only sweeps stragglers and closes
    the pipes) and on a process that ignores SIGINT and SIGTERM (it is killed). A second
    Ctrl+C during the stop skips the waiting and kills at once.
    """
    try:
        if os.name == "nt":
            _stop_windows(p)
        else:
            _stop_posix(p)
    except KeyboardInterrupt:
        # Impatience while we are cleaning up: kill outright, then keep cleaning.
        with contextlib.suppress(Exception):
            if os.name == "nt":
                p.kill()
            else:
                _killpg(p.pid, getattr(signal, "SIGKILL", signal.SIGTERM))
            p.wait(timeout=_KILL_WAIT)
    finally:
        if close_pipes:
            _close_pipes(p)


@contextlib.contextmanager
def _stopped_on_cancel(p: subprocess.Popen[Any], cancel: threading.Event | None) -> Iterator[None]:
    """While the body runs, stop the process tree as soon as ``cancel`` is set.

    A check between output lines would not do: archive mode can print nothing for most
    of a minute. A watcher thread waits on the event instead. It is released through a
    private event when the body ends, never by setting ``cancel``, which is the caller's,
    and is joined before this returns. Stopping the tree closes the child's end of the
    pipes, so a read blocked in the body returns.
    """
    if cancel is None:
        yield
        return
    done = threading.Event()

    def watch() -> None:
        while not done.is_set():
            if cancel.wait(_CANCEL_POLL):
                if p.poll() is None:
                    stop_process_tree(p, close_pipes=False)
                return

    watcher = threading.Thread(target=watch, name="cancel-watch", daemon=True)
    watcher.start()
    try:
        yield
    finally:
        done.set()
        watcher.join()


def _interrupt_note() -> str:
    """The log line for a run the user stopped. The log stays English: it is a
    diagnostic artifact, not UI."""
    return f"\n[INFO {datetime.now().isoformat(timespec='seconds')}] Interrupted by user (Ctrl+C)\n"


def run_capture(
    cmd: list[str], timeout: float | None = None, *, cancel: threading.Event | None = None
) -> tuple[int, str, str]:
    """Run a command and capture its output.

    Executes a command synchronously and captures both stdout and stderr.
    Always returns a tuple to keep callers predictable, even on errors. The command
    runs in its own process group and is stopped, with everything it started, on
    every way out of this function.

    Args:
        cmd: The command and arguments to execute.
        timeout: Seconds the whole command may take, or None for no limit. It is for
            calls that return a document (a listing, a probe); a download never uses it.
        cancel: When set (from another thread), the command is stopped and the call
            returns as for Ctrl+C. None leaves Ctrl+C as the only way to cancel.

    Returns:
        A tuple of (return_code, stdout, stderr).
        On keyboard interrupt or cancel, returns (130, "", "Interrupted by user").
        On a time-out, returns (TIMEOUT_RETURN_CODE, whatever was printed, "Timed out ...").
        On other exceptions, returns (1, "", error_message).
    """
    p: subprocess.Popen[str] | None = None
    try:
        p = subprocess.Popen(
            resolve_program(cmd),
            env=child_env(),
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **_popen_kwargs(),
        )
        with _stopped_on_cancel(p, cancel):
            stdout, stderr = p.communicate(timeout=timeout)
        if cancel is not None and cancel.is_set():
            return 130, "", "Interrupted by user"
        return p.returncode, stdout, stderr
    except subprocess.TimeoutExpired as ex:
        assert p is not None
        partial = ex.stdout if isinstance(ex.stdout, str) else ""
        stop_process_tree(p, close_pipes=False)
        with contextlib.suppress(Exception):
            rest_out, rest_err = p.communicate(timeout=_KILL_WAIT)
            partial = rest_out or partial
            return (
                TIMEOUT_RETURN_CODE,
                partial,
                f"Timed out after {timeout:g} s\n{rest_err or ''}".rstrip(),
            )
        return TIMEOUT_RETURN_CODE, partial, f"Timed out after {timeout:g} s"
    except KeyboardInterrupt:
        return 130, "", "Interrupted by user"
    except Exception as ex:
        return 1, "", f"{type(ex).__name__}: {ex}"
    finally:
        if p is not None:
            stop_process_tree(p)


def run_cmd_tee(
    cmd: list[str],
    log_path: Path,
    *,
    stop_on_ban: bool = False,
    sink: OutputSink | None = None,
    cancel: threading.Event | None = None,
) -> int:
    """Run a command with live output streaming and logging.

    Streams command output to the sink (the console by default) in real-time with
    syntax highlighting, while also logging the raw output to a file. Whatever ends the
    call (the command finishing, a ban, Ctrl+C, a cancel, a failed log write, an output
    error), the command and everything it started are stopped, reaped and their pipes
    closed before it returns.

    Args:
        cmd: The command and arguments to execute.
        log_path: Path to the log file for capturing output.
        stop_on_ban: Stop the command as soon as its output shows YouTube
            rate limiting (HTTP 429) or demanding a bot check. Continuing to
            send requests at that point only extends the block.
        sink: Where the output is shown; None is the console.
        cancel: When set (from another thread), the command is stopped and the call
            returns as for Ctrl+C. None leaves Ctrl+C as the only way to cancel.

    Returns:
        The process return code.
        Returns BAN_RETURN_CODE when stop_on_ban stopped the command.
        Returns 130 on keyboard interrupt or cancel.
        Returns 1 on unexpected errors.
    """
    out: OutputSink = sink if sink is not None else ConsoleSink()
    header = t("command_running")
    shown = display_command(cmd)
    out.write(f"\n{Colors.BOLD}=== {header} ==={Colors.RESET}")
    out.write(colorize_command(shown))
    out.write(f"{Colors.BOLD}{'=' * (len(header) + 8)}{Colors.RESET}\n")

    p: subprocess.Popen[bytes] | None = None
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", errors="ignore") as f:
            f.write("\n" + "=" * 80 + "\n")
            # The log records what really ran, launcher included, for debugging;
            # the console above shows the shorter logical command. Credentials are
            # masked in both: only the arguments actually executed keep them.
            real_cmd = resolve_program(cmd)
            f.write(
                f"[{datetime.now().isoformat(timespec='seconds')}] "
                f"CMD: {' '.join(display_command(real_cmd))}\n"
            )
            f.write("=" * 80 + "\n")

            p = subprocess.Popen(
                real_cmd,
                env=child_env(),
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                # Use binary mode to manually handle carriage returns
                text=False,
                **_popen_kwargs(),
            )

            assert p.stdout is not None
            # Wrap stdout to handle \r without translating to \n
            # newline="" ensures \r is preserved as-is
            reader = io.TextIOWrapper(p.stdout, encoding="utf-8", newline="", errors="replace")

            with _stopped_on_cancel(p, cancel):
                for raw in reader:
                    line = redact_secrets(raw)
                    # Apply syntax highlighting for display, keep raw for log. A line
                    # ending in a bare "\r" is a progress redraw.
                    if line.endswith("\r"):
                        out.progress(line)
                    else:
                        out.write(colorize_line(line), end="")
                    f.write(line)

                    signal_seen = detect_ban_signal(line) if stop_on_ban else None
                    if signal_seen is not None:
                        # Stop before reading further: a merge left running by yt-dlp
                        # could otherwise hold the pipe open.
                        stop_process_tree(p)
                        f.write(
                            f"\n[BAN-GUARD {datetime.now().isoformat(timespec='seconds')}] "
                            f"Stopped yt-dlp: {signal_seen.value} detected in: {line.strip()}\n"
                            f">>> returncode = {BAN_RETURN_CODE}\n"
                        )
                        return BAN_RETURN_CODE

                rc = p.wait()

            if cancel is not None and cancel.is_set():
                # The watcher stopped the tree, which is what ended the output.
                f.write(_interrupt_note())
                with contextlib.suppress(Exception):
                    out.write(f"\n>>> {t('status_cancelled')} (Ctrl+C).")
                return 130

            if rc == 0:
                message = f">>> {t('command_success', code=rc)}"
                out.write("\n" + paint(message, Colors.GREEN, Colors.BOLD) + "\n")
            # A non-zero code is reported by the caller, which has the context
            # to know whether it is fatal (see the two-stage compatibility flow).

            f.write(f"\n>>> returncode = {rc}\n")
            return rc

    except KeyboardInterrupt:
        # Stop the tree before anything else: printing may itself fail.
        if p is not None:
            stop_process_tree(p)
        with contextlib.suppress(Exception):
            out.write(f"\n>>> {t('status_cancelled')} (Ctrl+C).")
        append_log(log_path, _interrupt_note())
        return 130
    except Exception as ex:
        if p is not None:
            stop_process_tree(p)
        with contextlib.suppress(Exception):
            out.write(t("command_failed"))
        log_error(log_path, "Unexpected error while running command", ex)
        return 1
    finally:
        if p is not None:
            stop_process_tree(p)
