"""Tests for the ban guard in ytdlp_app.exec."""

import sys
import time
from pathlib import Path

import pytest

from ytdlp_app.exec import (
    BAN_RETURN_CODE,
    BanSignal,
    detect_ban_signal,
    find_ban_signal,
    run_cmd_tee,
)


class TestDetectBanSignal:
    """Real yt-dlp output lines, and look-alikes that must not trip the guard."""

    @pytest.mark.parametrize(
        "line",
        [
            "ERROR: [youtube] dQw4w9WgXcQ: Unable to download API page: "
            "HTTP Error 429: Too Many Requests",
            "WARNING: [youtube] Unable to download webpage: HTTP Error 429: Too Many Requests\n",
            "WARNING: Unable to download video subtitles for 'tr': HTTP Error 429: "
            "Too Many Requests",
            "[download] Got error: HTTP Error 429: Too Many Requests. "
            "Retrying fragment 3 (1/10)...\r",
        ],
    )
    def test_rate_limit(self, line: str) -> None:
        assert detect_ban_signal(line) is BanSignal.RATE_LIMITED

    @pytest.mark.parametrize(
        "line",
        [
            # YouTube's own wording uses a typographic apostrophe.
            "ERROR: [youtube] dQw4w9WgXcQ: Sign in to confirm you\u2019re not a bot. "
            "Use --cookies-from-browser or --cookies for the authentication.",
            "ERROR: [youtube] dQw4w9WgXcQ: Sign in to confirm you're not a bot.",
        ],
    )
    def test_bot_check(self, line: str) -> None:
        assert detect_ban_signal(line) is BanSignal.BOT_CHECK

    @pytest.mark.parametrize(
        "line",
        [
            # Progress and sizes are full of numbers.
            "[download]  42.9% of  429.00MiB at    1.20MiB/s ETA 03:12\r",
            "[download] Downloading item 429 of 1000\n",
            # A title quoting the phrases is not a diagnostic.
            "[download] Destination: HTTP Error 429 explained.mkv\n",
            "[info] Writing video description to: Sign in to confirm you're not a bot.description",
            # Other sign-in errors are handled by the normal error path.
            "ERROR: [youtube] abc: Sign in to confirm your age.",
            "ERROR: [youtube] abc: HTTP Error 403: Forbidden",
            "",
        ],
    )
    def test_ignores_everything_else(self, line: str) -> None:
        assert detect_ban_signal(line) is None

    def test_find_scans_every_line(self) -> None:
        stderr = (
            "WARNING: something harmless\n"
            "ERROR: [youtube:tab] x: HTTP Error 429: Too Many Requests\n"
        )
        assert find_ban_signal(stderr) is BanSignal.RATE_LIMITED
        assert find_ban_signal("WARNING: nothing to see\n") is None


def _script(*lines: str, then_sleep: float = 0.0) -> list[str]:
    """A command that prints lines like yt-dlp would, then optionally keeps running."""
    body = "import sys, time\n"
    for line in lines:
        body += f"print({line!r}, flush=True)\n"
    body += f"time.sleep({then_sleep})\n"
    return [sys.executable, "-c", body]


class TestRunCmdTeeBanGuard:
    """The guard must actually stop the process and leave a trace in the log."""

    def test_stops_the_process_on_429(self, tmp_path: Path) -> None:
        log = tmp_path / "run.log"
        cmd = _script(
            "[youtube] Extracting URL: https://www.youtube.com/watch?v=x",
            "ERROR: [youtube] x: HTTP Error 429: Too Many Requests",
            then_sleep=60,
        )

        started = time.monotonic()
        rc = run_cmd_tee(cmd, log, stop_on_ban=True)

        assert rc == BAN_RETURN_CODE
        # Well under the 60 s the child would otherwise keep running for.
        assert time.monotonic() - started < 15
        text = log.read_text(encoding="utf-8")
        assert "[BAN-GUARD" in text
        assert BanSignal.RATE_LIMITED.value in text

    def test_stops_the_process_on_bot_check(self, tmp_path: Path) -> None:
        log = tmp_path / "run.log"
        cmd = _script(
            "ERROR: [youtube] x: Sign in to confirm you\u2019re not a bot.",
            then_sleep=60,
        )

        assert run_cmd_tee(cmd, log, stop_on_ban=True) == BAN_RETURN_CODE
        assert BanSignal.BOT_CHECK.value in log.read_text(encoding="utf-8")

    def test_guard_is_off_by_default(self, tmp_path: Path) -> None:
        """MP4/MP3 keep their behavior: the process runs to its own exit code."""
        log = tmp_path / "run.log"
        cmd = _script("ERROR: [youtube] x: HTTP Error 429: Too Many Requests")

        assert run_cmd_tee(cmd, log) == 0
        assert "[BAN-GUARD" not in log.read_text(encoding="utf-8")

    def test_clean_run_is_unaffected(self, tmp_path: Path) -> None:
        log = tmp_path / "run.log"
        cmd = _script("[download] 100% of 1.00MiB", "[download] Downloading item 429 of 500")

        assert run_cmd_tee(cmd, log, stop_on_ban=True) == 0
