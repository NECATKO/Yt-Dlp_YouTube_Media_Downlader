"""The output sink and the cancel event of run_cmd_tee and run_capture.

A front end that is not the console (the TUI) runs the session in a worker thread:
it shows the output through a sink and cancels through an event, since no
KeyboardInterrupt ever reaches that thread. Without either, nothing may change.
"""

import sys
import threading
import time
from pathlib import Path

import pytest

from tests.test_exec_lifecycle import PARENT, alive, pids_from, posix_only, wait_gone
from ytdlp_app.exec import ConsoleSink, run_capture, run_cmd_tee
from ytdlp_app.i18n import set_language, t
from ytdlp_app.redact import display_command

#: The time a cancelled command has to be gone in, start to finish.
CANCEL_BUDGET = 5.0


@pytest.fixture(autouse=True)
def _english():
    set_language("en")
    yield
    set_language("en")


def quiet_child(marker: Path, seconds: int = 30) -> list[str]:
    """A child that starts a grandchild, writes both pids to a file and then prints
    nothing for `seconds`, the way archive mode waits between requests."""
    script = PARENT.replace(
        'print("READY", os.getpid(), grand.pid, flush=True)',
        f'open({str(marker)!r}, "w").write(f"READY {{os.getpid()}} {{grand.pid}}")',
    ).replace("time.sleep(60)\n", f"time.sleep({seconds})\n")
    return [sys.executable, "-c", script]


def cancel_when_ready(marker: Path, cancel: threading.Event) -> threading.Thread:
    """Set `cancel` from another thread once the child has announced itself."""

    def run() -> None:
        deadline = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        time.sleep(0.1)
        cancel.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


class RecordingSink:
    """An OutputSink that keeps everything it is given."""

    def __init__(self) -> None:
        self.written: list[tuple[str, str]] = []
        self.progressed: list[str] = []

    def write(self, text: str, *, end: str = "\n") -> None:
        self.written.append((text, end))

    def progress(self, line: str) -> None:
        self.progressed.append(line)

    def text(self) -> str:
        return "".join(text + end for text, end in self.written)


def _printing(*chunks: str) -> list[str]:
    body = "import sys\n" + "".join(
        f"sys.stdout.write({chunk!r}); sys.stdout.flush()\n" for chunk in chunks
    )
    return [sys.executable, "-c", body]


@posix_only
class TestCancelStopsAQuietCommand:
    def test_run_cmd_tee_stops_within_the_budget_and_leaves_no_orphans(
        self, tmp_path: Path
    ) -> None:
        marker = tmp_path / "pids"
        log = tmp_path / "run.log"
        cancel = threading.Event()
        sink = RecordingSink()
        cancel_when_ready(marker, cancel)

        started = time.monotonic()
        rc = run_cmd_tee(quiet_child(marker), log, sink=sink, cancel=cancel)
        elapsed = time.monotonic() - started

        assert rc == 130
        assert elapsed < CANCEL_BUDGET
        assert wait_gone(pids_from(marker), seconds=1.0) == []
        assert "Interrupted by user (Ctrl+C)" in log.read_text(encoding="utf-8")
        assert t("status_cancelled") in sink.text()
        assert t("command_success", code=0) not in sink.text()

    def test_run_capture_stops_within_the_budget_and_leaves_no_orphans(
        self, tmp_path: Path
    ) -> None:
        marker = tmp_path / "pids"
        cancel = threading.Event()
        cancel_when_ready(marker, cancel)

        started = time.monotonic()
        rc, out, err = run_capture(quiet_child(marker), timeout=60, cancel=cancel)
        elapsed = time.monotonic() - started

        assert (rc, out, err) == (130, "", "Interrupted by user")
        assert elapsed < CANCEL_BUDGET
        assert wait_gone(pids_from(marker), seconds=1.0) == []

    def test_a_cancel_given_before_the_start_stops_it_at_once(self, tmp_path: Path) -> None:
        marker = tmp_path / "pids"
        cancel = threading.Event()
        cancel.set()

        started = time.monotonic()
        rc = run_cmd_tee(quiet_child(marker), tmp_path / "run.log", cancel=cancel)

        assert rc == 130
        assert time.monotonic() - started < CANCEL_BUDGET
        if marker.exists():
            assert not any(alive(pid) for pid in pids_from(marker))


class TestCancelLeftAlone:
    def test_a_finished_command_does_not_set_the_callers_event(self, tmp_path: Path) -> None:
        cancel = threading.Event()

        rc = run_cmd_tee([sys.executable, "-c", "print('x')"], tmp_path / "run.log", cancel=cancel)

        assert rc == 0
        assert not cancel.is_set()

    def test_run_capture_returns_its_output_with_an_unset_event(self) -> None:
        cancel = threading.Event()

        rc, out, _err = run_capture([sys.executable, "-c", "print('out')"], cancel=cancel)

        assert (rc, out.strip()) == (0, "out")
        assert not cancel.is_set()

    def test_the_watcher_thread_is_gone_after_the_call(self, tmp_path: Path) -> None:
        cancel = threading.Event()

        run_cmd_tee([sys.executable, "-c", "pass"], tmp_path / "run.log", cancel=cancel)

        assert not [th for th in threading.enumerate() if th.name == "cancel-watch"]


class TestSink:
    def test_the_sink_gets_every_line_and_progress_goes_apart(self, tmp_path: Path) -> None:
        log = tmp_path / "run.log"
        progress = "[download]  45.3% of ~10.00MiB at 2.10MiB/s ETA 00:05\r"
        cmd = _printing("[youtube] one\n", progress, "[download] 100% of 10.00MiB\n", "two\n")
        sink = RecordingSink()

        rc = run_cmd_tee(cmd, log, sink=sink)

        assert rc == 0
        assert sink.progressed == [progress]
        shown = sink.text()
        for expected in ("one", "100% of", "two", t("command_running")):
            assert expected in shown
        assert t("command_success", code=0) in shown
        # The command echo quotes the script; the output lines must not hold the redraw.
        assert not [text for text, end in sink.written if end == "" and "45.3%" in text]
        # The log is the same whatever the sink: every line, progress included, as read.
        text = log.read_bytes().decode("utf-8")  # read_text would turn the "\r" into "\n"
        assert progress in text
        assert ">>> returncode = 0" in text

    def test_nothing_reaches_the_console_when_a_sink_is_given(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run_cmd_tee(_printing("a\n", "b\r"), tmp_path / "run.log", sink=RecordingSink())

        assert capsys.readouterr().out == ""

    def test_failure_text_goes_to_the_sink(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        sink = RecordingSink()

        def broken(*_args: object, **_kwargs: object) -> None:
            raise OSError("cannot start")

        monkeypatch.setattr("ytdlp_app.exec.subprocess.Popen", broken)

        assert run_cmd_tee(["x"], tmp_path / "run.log", sink=sink) == 1
        assert t("command_failed") in sink.text()


class TestConsoleUnchanged:
    """Without a sink, the console shows exactly what it showed before sinks existed."""

    def test_the_console_output_is_byte_for_byte_the_old_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cmd = _printing("one\n", "two\r", "three\n")
        header = t("command_running")
        expected = (
            f"\n=== {header} ===\n"
            f"{' '.join(display_command(cmd))}\n"
            f"{'=' * (len(header) + 8)}\n\n"
            "one\ntwo\rthree\n"
            f"\n>>> {t('command_success', code=0)}\n\n"
        )

        assert run_cmd_tee(cmd, tmp_path / "run.log") == 0

        assert capsys.readouterr().out == expected

    def test_an_explicit_console_sink_is_the_default(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cmd = _printing("one\n", "two\r", "three\n")
        run_cmd_tee(cmd, tmp_path / "a.log")
        default = capsys.readouterr().out

        run_cmd_tee(cmd, tmp_path / "b.log", sink=ConsoleSink())

        assert capsys.readouterr().out == default
