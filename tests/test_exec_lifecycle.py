"""No child or grandchild may outlive the call that started it, whichever way it ends.

The children here are real processes: each one starts a grandchild (the way yt-dlp
starts ffmpeg) and reports both pids, and the tests ask the operating system, not a
mock, whether they are gone.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

import ytdlp_app.exec as exec_module
from ytdlp_app.exec import (
    TIMEOUT_RETURN_CODE,
    run_capture,
    run_cmd_tee,
    stop_process_tree,
)

posix_only = pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX-only")

# A child that starts a grandchild, announces "READY <child> <grandchild>" and then
# stays busy. IGNORE_SIGNALS makes both refuse SIGINT and SIGTERM, as a wedged ffmpeg might.
PARENT = """
import os, signal, subprocess, sys, time
if os.environ.get("IGNORE_SIGNALS"):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
grand = subprocess.Popen([sys.executable, "-c", (
    "import os, signal, time\\n"
    "if os.environ.get('IGNORE_SIGNALS'):\\n"
    "    signal.signal(signal.SIGINT, signal.SIG_IGN)\\n"
    "    signal.signal(signal.SIGTERM, signal.SIG_IGN)\\n"
    "time.sleep(60)")])
if os.environ.get("MARKER"):
    with open(os.environ["MARKER"], "w") as marker:
        marker.write(f"READY {os.getpid()} {grand.pid}")
print("READY", os.getpid(), grand.pid, flush=True)
time.sleep(60)
"""


def busy_command() -> list[str]:
    return [sys.executable, "-c", PARENT]


def alive(pid: int) -> bool:
    """Whether a process still exists (a zombie counts as gone once it is reaped)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # Exists, but may be a zombie awaiting its parent: /proc says so.
    try:
        status = Path(f"/proc/{pid}/status").read_text()
    except OSError:
        return True
    return "State:\tZ" not in status


def wait_gone(pids: list[int], seconds: float = 5.0) -> list[int]:
    """The pids still alive after up to `seconds` (processes vanish asynchronously)."""
    deadline = time.monotonic() + seconds
    left = [pid for pid in pids if alive(pid)]
    while left and time.monotonic() < deadline:
        time.sleep(0.05)
        left = [pid for pid in left if alive(pid)]
    return left


def pids_from(log: Path) -> list[int]:
    for line in log.read_text(encoding="utf-8").splitlines():
        if line.startswith("READY"):
            return [int(x) for x in line.split()[1:]]
    raise AssertionError("child never announced itself:\n" + log.read_text(encoding="utf-8"))


@pytest.fixture
def quick_escalation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shorten the grace periods so a child that ignores signals is killed in a moment."""
    monkeypatch.setattr(exec_module, "_INTERRUPT_GRACE", 0.4)
    monkeypatch.setattr(exec_module, "_TERMINATE_TIMEOUT", 0.4)


def interrupting_on_ready(monkeypatch: pytest.MonkeyPatch, exc: BaseException) -> None:
    """Make the console output of the READY line raise, as Ctrl+C or a broken pipe would."""
    real = exec_module.colorize_line

    def colorize(line: str) -> str:
        if line.startswith("READY"):
            raise exc
        return real(line)

    monkeypatch.setattr(exec_module, "colorize_line", colorize)


@posix_only
class TestRunCmdTeeLeavesNothingBehind:
    @pytest.mark.parametrize(
        ("exc", "code"),
        [
            (KeyboardInterrupt(), 130),
            (BrokenPipeError("console closed"), 1),
            (UnicodeEncodeError("ascii", "x", 0, 1, "cannot encode"), 1),
            (RuntimeError("unexpected"), 1),
        ],
    )
    def test_output_errors_and_interrupts_stop_child_and_grandchild(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, exc: BaseException, code: int
    ) -> None:
        interrupting_on_ready(monkeypatch, exc)
        marker = tmp_path / "pids"
        monkeypatch.setenv("MARKER", str(marker))

        rc = run_cmd_tee(busy_command(), tmp_path / "run.log")

        assert rc == code
        assert wait_gone(pids_from(marker)) == []

    def test_a_log_write_failure_stops_the_child_too(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        log = tmp_path / "run.log"
        marker = tmp_path / "pids"
        script = PARENT.replace(
            'print("READY", os.getpid(), grand.pid, flush=True)',
            f'open({str(marker)!r}, "w").write(f"READY {{os.getpid()}} {{grand.pid}}")\n'
            'print("GO", flush=True)',
        )
        real_open = Path.open

        class FullDisk:
            """A log file whose disk fills up as soon as the child says something."""

            def __init__(self, handle: Any) -> None:
                self.handle = handle

            def write(self, text: str) -> int:
                if text.startswith("GO"):
                    raise OSError(28, "No space left on device")
                return self.handle.write(text)

            def __enter__(self) -> "FullDisk":
                return self

            def __exit__(self, *_exc: object) -> None:
                self.handle.close()

        def fake_open(self: Path, *args: Any, **kwargs: Any) -> Any:
            handle = real_open(self, *args, **kwargs)
            return FullDisk(handle) if self == log else handle

        monkeypatch.setattr(Path, "open", fake_open)

        rc = run_cmd_tee([sys.executable, "-c", script], log)

        assert rc == 1
        assert wait_gone(pids_from(marker)) == []

    def test_a_ban_stops_the_grandchild_as_well(self, tmp_path: Path) -> None:
        log = tmp_path / "run.log"
        script = PARENT.replace(
            'print("READY", os.getpid(), grand.pid, flush=True)',
            'print("READY", os.getpid(), grand.pid, flush=True)\n'
            'print("ERROR: HTTP Error 429: Too Many Requests", flush=True)',
        )

        rc = run_cmd_tee([sys.executable, "-c", script], log, stop_on_ban=True)

        assert rc == exec_module.BAN_RETURN_CODE
        assert wait_gone(pids_from(log)) == []

    @pytest.mark.usefixtures("quick_escalation")
    def test_a_child_that_ignores_sigint_and_sigterm_is_killed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("IGNORE_SIGNALS", "1")
        marker = tmp_path / "pids"
        monkeypatch.setenv("MARKER", str(marker))
        interrupting_on_ready(monkeypatch, KeyboardInterrupt())

        started = time.monotonic()
        rc = run_cmd_tee(busy_command(), tmp_path / "run.log")

        assert rc == 130
        assert time.monotonic() - started < 10
        assert wait_gone(pids_from(marker)) == []

    def test_the_pipe_is_closed_and_the_child_reaped(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        interrupting_on_ready(monkeypatch, KeyboardInterrupt())
        started: list[subprocess.Popen[bytes]] = []
        real_popen = subprocess.Popen

        def spy(*args: Any, **kwargs: Any) -> subprocess.Popen[bytes]:
            proc = real_popen(*args, **kwargs)
            started.append(proc)
            return proc

        monkeypatch.setattr(exec_module.subprocess, "Popen", spy)

        run_cmd_tee(busy_command(), tmp_path / "run.log")

        assert started[0].returncode is not None
        assert started[0].stdout is not None and started[0].stdout.closed

    def test_a_normal_run_is_unaffected(self, tmp_path: Path) -> None:
        log = tmp_path / "run.log"

        rc = run_cmd_tee([sys.executable, "-c", "print('hello'); raise SystemExit(3)"], log)

        assert rc == 3
        assert "hello" in log.read_text(encoding="utf-8")

    def test_the_child_does_not_share_our_process_group(self, tmp_path: Path) -> None:
        """Otherwise a terminal's Ctrl+C would reach it only by luck of the terminal."""
        log = tmp_path / "run.log"
        code = "import os; print('GROUP', os.getpgrp() == os.getpid())"

        run_cmd_tee([sys.executable, "-c", code], log)

        assert "GROUP True" in log.read_text(encoding="utf-8")


@posix_only
class TestRunCaptureLeavesNothingBehind:
    def test_a_time_out_stops_child_and_grandchild(self, tmp_path: Path) -> None:
        marker = tmp_path / "pids"
        script = PARENT.replace(
            'print("READY", os.getpid(), grand.pid, flush=True)',
            f'open({str(marker)!r}, "w").write(f"READY {{os.getpid()}} {{grand.pid}}")',
        )

        rc, _out, err = run_capture([sys.executable, "-c", script], timeout=1.5)

        assert rc == TIMEOUT_RETURN_CODE
        assert "Timed out" in err
        assert wait_gone(pids_from(marker)) == []

    def test_an_interrupt_stops_the_tree(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        marker = tmp_path / "pids"
        script = PARENT.replace(
            'print("READY", os.getpid(), grand.pid, flush=True)',
            f'open({str(marker)!r}, "w").write(f"READY {{os.getpid()}} {{grand.pid}}")',
        )
        real_communicate = subprocess.Popen.communicate

        def interrupted(self: Any, *args: Any, **kwargs: Any) -> Any:
            deadline = time.monotonic() + 5
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            time.sleep(0.1)
            raise KeyboardInterrupt

        monkeypatch.setattr(subprocess.Popen, "communicate", interrupted)

        rc, _out, err = run_capture([sys.executable, "-c", script])

        monkeypatch.setattr(subprocess.Popen, "communicate", real_communicate)
        assert rc == 130
        assert "Interrupted" in err
        assert wait_gone(pids_from(marker)) == []

    def test_a_normal_run_returns_its_output(self) -> None:
        rc, out, err = run_capture(
            [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr)"]
        )

        assert (rc, out.strip(), err.strip()) == (0, "out", "err")

    def test_no_time_out_means_a_long_run_is_left_alone(self) -> None:
        rc, out, _ = run_capture([sys.executable, "-c", "import time; time.sleep(1.2); print('x')"])

        assert (rc, out.strip()) == (0, "x")

    def test_a_missing_program_is_reported_not_raised(self) -> None:
        rc, _out, err = run_capture(["definitely-not-a-program-xyz"])

        assert rc == 1
        assert "FileNotFoundError" in err


@posix_only
def test_stop_process_tree_is_safe_on_a_finished_process() -> None:
    proc = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    proc.wait()

    stop_process_tree(proc)

    assert proc.returncode == 0


class FakeProcess:
    """Enough of Popen to check which Windows calls a stop makes."""

    def __init__(self, exits_after_break: bool) -> None:
        self.pid = 4321
        self.stdout = None
        self.stderr = None
        self.stdin = None
        self.sent: list[int] = []
        self.returncode: int | None = None
        self._exits_after_break = exits_after_break

    def poll(self) -> int | None:
        return self.returncode

    def send_signal(self, sig: int) -> None:
        self.sent.append(sig)
        if self._exits_after_break:
            self.returncode = 1

    def wait(self, timeout: float | None = None) -> int:
        if self.returncode is None:
            if timeout is not None:
                raise subprocess.TimeoutExpired("fake", timeout)
            self.returncode = 1
        return self.returncode


class TestWindowsTreeStop:
    """The Windows branch cannot run here; its decisions are checked with a stand-in."""

    def test_asks_politely_first_and_only_kills_the_tree_if_ignored(self) -> None:
        proc = FakeProcess(exits_after_break=False)
        calls: list[list[str]] = []

        exec_module._stop_windows(proc, grace=0.01, run=lambda cmd, **_: calls.append(cmd))  # type: ignore[arg-type]

        assert proc.sent == [exec_module._CTRL_BREAK]
        assert calls == [["taskkill", "/PID", "4321", "/T", "/F"]]
        assert proc.returncode is not None

    def test_a_process_that_leaves_on_its_own_still_has_its_tree_swept(self) -> None:
        proc = FakeProcess(exits_after_break=True)
        calls: list[list[str]] = []

        exec_module._stop_windows(proc, grace=0.01, run=lambda cmd, **_: calls.append(cmd))  # type: ignore[arg-type]

        # ffmpeg may outlive yt-dlp, so the tree is always swept.
        assert calls == [["taskkill", "/PID", "4321", "/T", "/F"]]

    def test_spawn_options_differ_per_platform(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(exec_module.os, "name", "nt")
        assert exec_module._popen_kwargs() == {
            "creationflags": exec_module._CREATE_NEW_PROCESS_GROUP
        }
        monkeypatch.setattr(exec_module.os, "name", "posix")
        assert exec_module._popen_kwargs() == {"start_new_session": True}


def test_sigint_is_offered_before_sigterm() -> None:
    """The order matters: SIGINT lets yt-dlp and ffmpeg finish cleanly; SIGTERM does not."""
    assert [s for s, _ in exec_module._POSIX_ESCALATION] == [
        signal.SIGINT,
        signal.SIGTERM,
        signal.SIGKILL if hasattr(signal, "SIGKILL") else signal.SIGTERM,
    ]
