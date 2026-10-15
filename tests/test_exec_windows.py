"""On Windows, nothing a command started may outlive the call, whichever way it ends (D02).

The processes are real: a child starts a grandchild (the way yt-dlp starts ffmpeg) and
writes both pids to a file, and Windows itself is asked whether they are still running.
"""

import ctypes
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

import ytdlp_app.exec as exec_module
from ytdlp_app import windows_process
from ytdlp_app.exec import BAN_RETURN_CODE, TIMEOUT_RETURN_CODE, run_capture, run_cmd_tee

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows processes")

_SYNCHRONIZE = 0x00100000
_WAIT_TIMEOUT = 258


def running(pid: int) -> bool:
    """Whether the process is still running, asked through a handle (not os.kill, which
    on Windows terminates)."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel32.OpenProcess(_SYNCHRONIZE, False, pid)
    if not handle:
        return False
    try:
        return bool(kernel32.WaitForSingleObject(handle, 0) == _WAIT_TIMEOUT)
    finally:
        kernel32.CloseHandle(handle)


def still_running(pids: list[int], seconds: float = 5.0) -> list[int]:
    """The pids still running after up to `seconds`."""
    deadline = time.monotonic() + seconds
    left = [pid for pid in pids if running(pid)]
    while left and time.monotonic() < deadline:
        time.sleep(0.05)
        left = [pid for pid in left if running(pid)]
    return left


@pytest.fixture
def leftovers():
    """Pids a test starts; whatever still runs at the end is killed so no test leaks."""
    pids: list[int] = []
    yield pids
    for pid in still_running(pids, seconds=0):
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)


def tree(
    marker: Path,
    *,
    leader_waits: float,
    grandchild: str = "time.sleep(60)",
    ignore_break: bool = False,
    inherit_output: bool = False,
    say: str = "",
    until: Path | None = None,
) -> list[str]:
    """A leader that starts a grandchild, waits for `until` to exist (when given), writes
    both pids to `marker`, optionally says `say`, and then waits `leader_waits` seconds
    before it exits."""
    ignore = (
        "import signal; signal.signal(signal.SIGBREAK, signal.SIG_IGN)\n" if ignore_break else ""
    )
    output = "" if inherit_output else ", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL"
    grand_code = ignore + "import time\n" + grandchild
    script = (
        "import os, subprocess, sys, time\n"
        + ignore
        + f"grand = subprocess.Popen([sys.executable, '-c', {grand_code!r}]{output})\n"
        + (f"while not os.path.exists({str(until)!r}): time.sleep(0.02)\n" if until else "")
        + f"open({str(marker)!r}, 'w').write(f'{{os.getpid()}} {{grand.pid}}')\n"
        + (f"print({say!r}, flush=True)\n" if say else "")
        + f"time.sleep({leader_waits})\n"
    )
    return [sys.executable, "-c", script]


def pids_of(marker: Path, leftovers: list[int]) -> list[int]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if marker.exists():
            text = marker.read_text(encoding="utf-8").split()
            if len(text) == 2:
                pids = [int(x) for x in text]
                leftovers.extend(pids)
                return pids
        time.sleep(0.02)
    raise AssertionError("the child never wrote its pids")


class TestTheLeaderLeavingFirst:
    def test_run_capture_closes_the_child_the_leader_left_behind(
        self, tmp_path: Path, leftovers: list[int]
    ) -> None:
        marker = tmp_path / "pids"

        rc, _out, _err = run_capture(tree(marker, leader_waits=0), timeout=30)

        assert rc == 0
        assert still_running(pids_of(marker, leftovers)) == []

    def test_run_cmd_tee_closes_the_child_the_leader_left_behind(
        self, tmp_path: Path, leftovers: list[int]
    ) -> None:
        marker = tmp_path / "pids"

        rc = run_cmd_tee(tree(marker, leader_waits=0), tmp_path / "run.log")

        assert rc == 0
        assert still_running(pids_of(marker, leftovers)) == []

    def test_a_grandchild_holding_the_output_pipe_does_not_hang_the_call(
        self, tmp_path: Path, leftovers: list[int]
    ) -> None:
        marker = tmp_path / "pids"
        started = time.monotonic()

        rc = run_cmd_tee(
            tree(marker, leader_waits=0, inherit_output=True, say="done"), tmp_path / "run.log"
        )

        assert rc == 0
        assert time.monotonic() - started < 20
        assert "done" in (tmp_path / "run.log").read_text(encoding="utf-8")
        assert still_running(pids_of(marker, leftovers)) == []

    def test_run_capture_with_a_pipe_held_open_returns_the_leaders_output(
        self, tmp_path: Path, leftovers: list[int]
    ) -> None:
        marker = tmp_path / "pids"
        started = time.monotonic()

        rc, out, _err = run_capture(
            tree(marker, leader_waits=0, inherit_output=True, say="done"), timeout=30
        )

        assert rc == 0
        assert out.strip() == "done"
        assert time.monotonic() - started < 20
        assert still_running(pids_of(marker, leftovers)) == []

    def test_a_file_the_grandchild_kept_open_is_released(
        self, tmp_path: Path, leftovers: list[int]
    ) -> None:
        marker = tmp_path / "pids"
        held = tmp_path / "part.mkv"
        holder = f"f = open({str(held)!r}, 'w')\ntime.sleep(60)"

        run_capture(tree(marker, leader_waits=0, grandchild=holder, until=held), timeout=30)

        pids_of(marker, leftovers)
        deadline = time.monotonic() + 5
        while True:
            try:
                held.unlink()
                break
            except PermissionError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.05)


class TestStopping:
    def test_a_time_out_closes_the_whole_tree(self, tmp_path: Path, leftovers: list[int]) -> None:
        marker = tmp_path / "pids"

        rc, _out, err = run_capture(tree(marker, leader_waits=60), timeout=2)

        assert rc == TIMEOUT_RETURN_CODE
        assert "Timed out" in err
        assert still_running(pids_of(marker, leftovers)) == []

    def test_a_ban_closes_the_whole_tree(self, tmp_path: Path, leftovers: list[int]) -> None:
        marker = tmp_path / "pids"
        cmd = tree(marker, leader_waits=60, say="ERROR: HTTP Error 429: Too Many Requests")

        rc = run_cmd_tee(cmd, tmp_path / "run.log", stop_on_ban=True)

        assert rc == BAN_RETURN_CODE
        assert still_running(pids_of(marker, leftovers)) == []

    @pytest.mark.parametrize("ignore_break", [False, True])
    def test_a_cancel_closes_a_quiet_tree(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        leftovers: list[int],
        ignore_break: bool,
    ) -> None:
        monkeypatch.setattr(exec_module, "_INTERRUPT_GRACE", 0.5)
        marker = tmp_path / "pids"
        cancel = threading.Event()

        def cancel_when_ready() -> None:
            deadline = time.monotonic() + 10
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            time.sleep(0.2)
            cancel.set()

        threading.Thread(target=cancel_when_ready, daemon=True).start()
        started = time.monotonic()

        rc = run_cmd_tee(
            tree(marker, leader_waits=60, ignore_break=ignore_break),
            tmp_path / "run.log",
            cancel=cancel,
        )

        assert rc == 130
        assert time.monotonic() - started < 15
        assert still_running(pids_of(marker, leftovers)) == []

    @pytest.mark.parametrize(
        ("exc", "code"),
        [(KeyboardInterrupt(), 130), (BrokenPipeError("console closed"), 1)],
    )
    def test_an_output_error_or_interrupt_closes_the_tree(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        leftovers: list[int],
        exc: BaseException,
        code: int,
    ) -> None:
        real = exec_module.colorize_line

        def colorize(line: str) -> str:
            if line.startswith("READY"):
                raise exc
            return real(line)

        monkeypatch.setattr(exec_module, "colorize_line", colorize)
        marker = tmp_path / "pids"

        rc = run_cmd_tee(tree(marker, leader_waits=60, say="READY"), tmp_path / "run.log")

        assert rc == code
        assert still_running(pids_of(marker, leftovers)) == []


class TestStartingUnderControl:
    def test_a_job_that_cannot_be_set_up_stops_the_child_and_says_why(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, leftovers: list[int]
    ) -> None:
        started: list[int] = []

        def failing(pid: int) -> "windows_process.ProcessJob":
            started.append(pid)
            raise OSError("AssignProcessToJobObject failed (injected)")

        monkeypatch.setattr(windows_process.ProcessJob, "adopt", staticmethod(failing))
        marker = tmp_path / "pids"

        rc, _out, err = run_capture(tree(marker, leader_waits=60), timeout=30)
        tee_rc = run_cmd_tee(tree(marker, leader_waits=60), tmp_path / "run.log")

        assert rc == 1 and "AssignProcessToJobObject" in err
        assert tee_rc == 1
        # The child never ran: it was started suspended and stopped before it could start
        # anything, so no pid file was written.
        assert not marker.exists()
        assert len(started) == 2
        leftovers.extend(started)
        assert still_running(started) == []

    def test_many_short_commands_leave_an_unrelated_process_alone(self, tmp_path: Path) -> None:
        bystander = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        try:
            for _ in range(20):
                assert run_capture([sys.executable, "-c", "pass"], timeout=30)[0] == 0
            assert running(bystander.pid)
        finally:
            bystander.kill()
            bystander.wait()
