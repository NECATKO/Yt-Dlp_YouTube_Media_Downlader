"""Tests for ytdlp_app.skip_probe.

The skip report is user-facing, so these mainly guard that every branch goes
through t() -- returning a raw English literal is the regression to catch.
"""

import json

import pytest

from ytdlp_app.i18n import load_locale, set_language
from ytdlp_app.skip_probe import probe_skip_reason


def _runner(rc: int, out: str = "", err: str = ""):
    """Build a CaptureRunner that always answers with the given result."""

    def run(cmd: list[str]) -> tuple[int, str, str]:
        return rc, out, err

    return run


def _formats(*vcodecs: str | None) -> str:
    return json.dumps({"formats": [{"vcodec": v} for v in vcodecs]})


@pytest.fixture(autouse=True)
def _english():
    """Each test starts from a known catalogue."""
    set_language("en")


@pytest.mark.parametrize(
    ("stderr", "expected_key"),
    [
        ("ERROR: Private video. Sign in if you've been granted access", "skip_reason_private"),
        ("ERROR: Join this channel to get access", "skip_reason_members_only"),
        ("ERROR: Sign in to confirm your age", "skip_reason_age_restricted"),
        ("ERROR: not available in your country", "skip_reason_region_blocked"),
        ("ERROR: Video unavailable", "skip_reason_unavailable"),
        ("ERROR: blocked on copyright grounds", "skip_reason_copyright"),
        ("ERROR: Requested format is not available", "skip_reason_format"),
        ("ERROR: Unable to extract nsig", "skip_reason_js_challenge"),
        ("ERROR: The read operation timed out", "skip_reason_timeout"),
        ("ERROR: HTTP Error 429: Too Many Requests", "skip_reason_rate_limited"),
    ],
)
def test_stderr_is_classified(stderr: str, expected_key: str) -> None:
    reason = probe_skip_reason("https://x.test/v", [], _runner(1, err=stderr))
    assert reason == load_locale("en")[expected_key]


def test_interrupt_is_reported() -> None:
    reason = probe_skip_reason("https://x.test/v", [], _runner(130))
    assert reason == load_locale("en")["skip_reason_interrupted"]


def test_unknown_error_quotes_the_stderr() -> None:
    reason = probe_skip_reason("https://x.test/v", [], _runner(1, err="ERROR: brand new failure"))
    assert "brand new failure" in reason
    assert "{detail}" not in reason


def test_unknown_error_truncates_a_long_stderr() -> None:
    reason = probe_skip_reason("https://x.test/v", [], _runner(1, err="x" * 5000))
    assert len(reason) < 400


def test_audio_only_entry() -> None:
    reason = probe_skip_reason("https://x.test/v", [], _runner(0, out=_formats("none")))
    assert reason == load_locale("en")["skip_reason_no_video_track"]


def test_video_present_means_postprocessing_failed() -> None:
    reason = probe_skip_reason("https://x.test/v", [], _runner(0, out=_formats("avc1.64001f")))
    assert reason == load_locale("en")["skip_reason_postprocess"]


def test_unparseable_json() -> None:
    reason = probe_skip_reason("https://x.test/v", [], _runner(0, out="not json at all"))
    assert reason == load_locale("en")["skip_reason_json_parse"]


@pytest.mark.parametrize(
    "runner",
    [
        _runner(130),
        _runner(1, err="ERROR: Private video"),
        _runner(1, err="ERROR: nothing recognizable"),
        _runner(0, out=_formats("none")),
        _runner(0, out=_formats("avc1")),
        _runner(0, out="not json"),
    ],
)
def test_every_branch_is_translated(runner) -> None:
    """A hardcoded English literal would come back identical in Turkish."""
    set_language("en")
    english = probe_skip_reason("https://x.test/v", [], runner)
    set_language("tr")
    turkish = probe_skip_reason("https://x.test/v", [], runner)
    set_language("en")

    assert english != turkish, f"untranslated skip reason: {english!r}"


class TestProbeStatus:
    """Cancellation and a ban are signals to stop, not just explanatory text."""

    def test_ctrl_c_is_a_cancellation(self) -> None:
        from ytdlp_app.skip_probe import ProbeStatus, probe_item  # noqa: PLC0415

        result = probe_item("https://x.test/v", [], _runner(130, err="Interrupted by user"))

        assert result.status is ProbeStatus.CANCELLED

    @pytest.mark.parametrize(
        "stderr",
        [
            "ERROR: [youtube] abc: HTTP Error 429: Too Many Requests",
            "ERROR: [youtube] abc: Sign in to confirm you\u2019re not a bot. Use --cookies",
        ],
    )
    def test_a_block_is_a_ban(self, stderr: str) -> None:
        from ytdlp_app.skip_probe import ProbeStatus, probe_item  # noqa: PLC0415

        result = probe_item("https://x.test/v", [], _runner(1, err=stderr))

        assert result.status is ProbeStatus.BANNED

    def test_the_bot_check_is_not_mistaken_for_an_age_restriction(self) -> None:
        """Both say "Sign in"; only one means the whole run should stop."""
        from ytdlp_app.skip_probe import ProbeStatus, probe_item  # noqa: PLC0415

        age = probe_item("u", [], _runner(1, err="ERROR: Sign in to confirm your age"))

        assert age.status is ProbeStatus.REASON

    def test_an_ordinary_failure_is_only_a_reason(self) -> None:
        from ytdlp_app.skip_probe import ProbeStatus, probe_item  # noqa: PLC0415

        result = probe_item("u", [], _runner(1, err="ERROR: Video unavailable"))

        assert result.status is ProbeStatus.REASON
        assert result.text == probe_skip_reason("u", [], _runner(1, err="ERROR: Video unavailable"))

    def test_a_timeout_is_reported_as_a_reason(self) -> None:
        from ytdlp_app.exec import TIMEOUT_RETURN_CODE  # noqa: PLC0415
        from ytdlp_app.skip_probe import ProbeStatus, probe_item  # noqa: PLC0415

        result = probe_item("u", [], _runner(TIMEOUT_RETURN_CODE, err="Timed out after 180 s"))

        assert result.status is ProbeStatus.REASON
        assert result.text == load_locale("en")["skip_reason_timeout"]

    def test_the_probe_command_can_carry_the_shared_network_arguments(self) -> None:
        from ytdlp_app.skip_probe import probe_item  # noqa: PLC0415

        seen: list[list[str]] = []

        def run(cmd: list[str]) -> tuple[int, str, str]:
            seen.append(cmd)
            return 1, "", "ERROR: Video unavailable"

        probe_item("https://x.test/v", ["--proxy", "http://p:1"], run)

        assert "--proxy" in seen[0]
        assert seen[0][-2:] == ["--proxy", "http://p:1"]
