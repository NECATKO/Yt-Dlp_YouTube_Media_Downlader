"""Tests for ytdlp_app.preflight: the listing guard and the estimate/resolution/space flow."""

from pathlib import Path
from typing import Any

import pytest

from ytdlp_app.estimate import format_size
from ytdlp_app.exceptions import PlaylistError
from ytdlp_app.i18n import set_language
from ytdlp_app.models import DownloadMode, PlaylistEntry, ProfileChoice
from ytdlp_app.preflight import (
    ListingStatus,
    PreflightAction,
    PreflightRequest,
    free_bytes,
    guarded_listing,
    run_preflight,
)
from ytdlp_app.settings import AppSettings

BAN_TEXT = "ERROR: [youtube:tab] @Handle: Sign in to confirm you\u2019re not a bot."


@pytest.fixture(autouse=True)
def _english():
    set_language("en")
    yield
    set_language("en")


class ScriptedUI:
    def __init__(self, picks: list[int] | None = None) -> None:
        self.picks = list(picks or [])
        self.messages: list[str] = []
        self.prompts: list[tuple[str, list[str]]] = []

    def print(self, text: object = "") -> None:
        self.messages.append(str(text))

    def print_panel(self, text: str, title: str | None = None, color: str = "") -> None:
        self.messages.append(text)

    def pick(self, prompt: str, options: list[str]) -> int:
        self.prompts.append((prompt, options))
        if not self.picks:
            raise AssertionError(f"unexpected pick(): {prompt!r} with {options!r}")
        return self.picks.pop(0)

    def ask_text(self, prompt: str) -> str:
        raise AssertionError(f"unexpected ask_text(): {prompt!r}")

    def prompt_exit_on_failure(self) -> bool:
        return True

    def text(self) -> str:
        return "\n".join(self.messages)


def _entry(vid: str, duration: float | None = 600, *, short: bool = False) -> PlaylistEntry:
    return PlaylistEntry(1, vid, "t", f"https://www.youtube.com/watch?v={vid}", duration, short)


def _request(tmp_path: Path, **overrides: Any) -> PreflightRequest:
    values: dict[str, Any] = {
        "mode": DownloadMode.VIDEO,
        "is_playlist": True,
        "entries": [_entry("a"), _entry("b"), _entry("c")],
        "archived_ids": frozenset(),
        "mp4_profile": ProfileChoice.QUALITY,
        "base_dir": tmp_path,
        "log_path": tmp_path / "session.log",
    }
    values.update(overrides)
    return PreflightRequest(**values)


def _run(
    request: PreflightRequest,
    ui: ScriptedUI,
    settings: AppSettings | None = None,
    *,
    measured: float | None = 1_000_000.0,
    free: int | Exception = 10**15,
    persist: Any = None,
):
    def no_speed_test(_proxy: str | None) -> float | None:
        return measured

    def disk_free(_path: Path) -> int:
        if isinstance(free, Exception):
            raise free
        return free

    return run_preflight(
        request,
        ui=ui,
        settings=settings if settings is not None else AppSettings(),
        persist_default=persist if persist is not None else (lambda _h: None),
        measure=no_speed_test,
        disk_free=disk_free,
    )


class TestGuardedListing:
    def test_success_returns_the_value(self, tmp_path: Path) -> None:
        result = guarded_listing(lambda: [1, 2], tmp_path / "log")
        assert result.status is ListingStatus.OK
        assert result.value == [1, 2]

    def test_ctrl_c_is_reported_not_raised(self, tmp_path: Path) -> None:
        def interrupted() -> list[int]:
            raise KeyboardInterrupt

        assert guarded_listing(interrupted, tmp_path / "log").status is ListingStatus.INTERRUPTED

    def test_a_ban_signal_is_flagged_and_logged(self, tmp_path: Path) -> None:
        log = tmp_path / "log"

        def banned() -> list[int]:
            raise PlaylistError(f"returncode=1\nstderr:\n{BAN_TEXT}")

        result = guarded_listing(banned, log)

        assert result.status is ListingStatus.BAN
        assert "Sign in to confirm" in result.error
        text = log.read_text(encoding="utf-8")
        assert "[BAN-GUARD" in text
        assert "Not starting the download" in text

    def test_another_failure_is_reported_with_its_text(self, tmp_path: Path) -> None:
        log = tmp_path / "log"

        def failing() -> list[int]:
            raise PlaylistError("returncode=1\nstderr:\nERROR: Unable to download webpage")

        result = guarded_listing(failing, log)

        assert result.status is ListingStatus.FAILED
        assert "Unable to download webpage" in result.error
        assert log.exists()

    def test_an_unexpected_exception_is_a_failed_listing(self, tmp_path: Path) -> None:
        def broken() -> list[int]:
            raise ValueError("bad")

        result = guarded_listing(broken, tmp_path / "log")
        assert result.status is ListingStatus.FAILED
        assert "bad" in result.error

    def test_a_missing_log_path_is_fine(self) -> None:
        def failing() -> list[int]:
            raise PlaylistError("x")

        assert guarded_listing(failing, None).status is ListingStatus.FAILED


class TestEstimateTable:
    def test_video_table_has_three_rows_and_the_summary(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])
        _run(_request(tmp_path), ui)

        text = ui.text()
        assert "1080p" in text
        assert "1440p (at most)" in text
        assert "2160p (at most)" in text
        assert "3 videos to download, 0 already in the archive, 0 with an assumed duration" in text
        assert "Free space:" in text

    def test_sizes_and_times_follow_the_bit_rates(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])
        _run(_request(tmp_path), ui, measured=1_000_000.0)

        text = ui.text()
        # 3 videos x 600 s at (6000 + 160) kbit/s = 1.386 GB; 1386 s at 1 MB/s.
        assert format_size(1_386_000_000) in text
        assert "23 min" in text
        assert "1 h 53 min" in text  # 2160p: 6.786 GB

    def test_the_measured_speed_is_shown(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])
        _run(_request(tmp_path), ui, measured=1_000_000.0)
        assert "Measured speed: 8.0 Mbit/s" in ui.text()

    def test_an_unmeasurable_speed_leaves_the_time_column_empty(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])
        _run(_request(tmp_path), ui, measured=None)

        text = ui.text()
        assert "could not be measured" in text
        assert "n/a" in text

    def test_assumed_durations_are_reported(self, tmp_path: Path) -> None:
        entries = [_entry("a", 600), _entry("s", None, short=True)]
        ui = ScriptedUI([4])
        _run(_request(tmp_path, entries=entries), ui)
        assert "1 with an assumed duration" in ui.text()

    def test_audio_shows_one_row_for_the_configured_format(self, tmp_path: Path) -> None:
        request = _request(
            tmp_path,
            mode=DownloadMode.AUDIO,
            mp4_profile=None,
            entries=[_entry("a", 600)],
        )
        ui = ScriptedUI()

        result = _run(request, ui)

        text = ui.text()
        assert "mp3" in text
        assert "17.5 MiB" in text  # 600 s at 245 kbit/s
        assert "1080p" not in text
        assert result.action is PreflightAction.PROCEED
        assert result.max_height is None

    def test_the_compatibility_profile_shows_only_1080p(self, tmp_path: Path) -> None:
        request = _request(tmp_path, mp4_profile=ProfileChoice.COMPATIBILITY)
        ui = ScriptedUI()

        result = _run(request, ui)

        text = ui.text()
        assert "1440p" not in text
        assert "limited to 1080p" in text
        assert result.max_height == 1080
        assert ui.prompts == []  # no resolution question

    def test_archive_mode_warns_about_the_waits(self, tmp_path: Path) -> None:
        entries = [_entry(f"v{i}") for i in range(10)]
        request = _request(tmp_path, mode=DownloadMode.ARCHIVE, mp4_profile=None, entries=entries)
        ui = ScriptedUI([1])

        _run(request, ui)  # 10 videos x 30 s average = 5 min

        assert "at least 5 min" in ui.text()
        assert "10 videos" in ui.text()

    def test_other_modes_do_not_show_the_wait_line(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])
        _run(_request(tmp_path), ui)
        assert "Waiting between videos" not in ui.text()


class TestUnavailableEstimate:
    def test_a_failed_listing_says_so_and_still_asks_the_resolution(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])

        def must_not_measure(_proxy: str | None) -> float | None:
            raise AssertionError("no speed test without an estimate")

        result = run_preflight(
            _request(tmp_path, entries=None),
            ui=ui,
            settings=AppSettings(),
            persist_default=lambda _h: None,
            measure=must_not_measure,
            disk_free=lambda _p: 10**15,
        )

        assert "Size could not be calculated" in ui.text()
        assert result.action is PreflightAction.PROCEED
        assert len(ui.prompts) == 1

    def test_no_known_duration_cannot_be_estimated(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])
        _run(_request(tmp_path, entries=[_entry("a", None), _entry("b", None)]), ui)
        assert "Size could not be calculated" in ui.text()

    def test_an_empty_listing_cannot_be_estimated(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])
        _run(_request(tmp_path, entries=[]), ui)
        assert "Size could not be calculated" in ui.text()

    def test_everything_archived_means_nothing_to_ask(self, tmp_path: Path) -> None:
        ui = ScriptedUI()
        request = _request(tmp_path, archived_ids=frozenset({"a", "b", "c"}))

        result = _run(request, ui)

        assert "nothing new to download" in ui.text()
        assert ui.prompts == []
        assert result.action is PreflightAction.PROCEED
        assert result.max_height is None  # the video default

    def test_everything_archived_in_archive_mode_keeps_the_archive_default(
        self, tmp_path: Path
    ) -> None:
        request = _request(
            tmp_path,
            mode=DownloadMode.ARCHIVE,
            mp4_profile=None,
            archived_ids=frozenset({"a", "b", "c"}),
        )
        result = _run(request, ScriptedUI())
        assert result.max_height == 1080


class TestResolutionQuestion:
    def test_default_is_marked_and_choosing_it_asks_nothing_more(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])

        result = _run(_request(tmp_path), ui)

        ((_prompt, options),) = ui.prompts
        assert options == ["1080p", "1440p", "2160p", "Unlimited (default)"]
        assert result == result.__class__(PreflightAction.PROCEED, None)

    def test_archive_default_is_1080(self, tmp_path: Path) -> None:
        request = _request(tmp_path, mode=DownloadMode.ARCHIVE, mp4_profile=None)
        ui = ScriptedUI([1])

        result = _run(request, ui)

        assert ui.prompts[0][1][0] == "1080p (default)"
        assert result.max_height == 1080

    def test_a_different_choice_asks_whether_to_keep_it(self, tmp_path: Path) -> None:
        saved: list[int | None] = []
        ui = ScriptedUI([2, 1])  # 1440p, then "only for this download"

        result = _run(_request(tmp_path), ui, persist=saved.append)

        assert result.max_height == 1440
        assert saved == []
        assert len(ui.prompts) == 2

    def test_saving_as_default_calls_the_callback(self, tmp_path: Path) -> None:
        saved: list[int | None] = []
        ui = ScriptedUI([2, 2])  # 1440p, then "save as default"

        result = _run(_request(tmp_path), ui, persist=saved.append)

        assert result.max_height == 1440
        assert saved == [1440]

    def test_a_save_failure_warns_and_continues(self, tmp_path: Path) -> None:
        def failing(_height: int | None) -> None:
            raise OSError("disk full")

        ui = ScriptedUI([2, 2])

        result = _run(_request(tmp_path), ui, persist=failing)

        assert result.action is PreflightAction.PROCEED
        assert result.max_height == 1440
        assert "Could not save the default (disk full)" in ui.text()

    def test_a_single_video_asks_the_resolution_without_a_table(self, tmp_path: Path) -> None:
        request = _request(tmp_path, is_playlist=False, entries=None)
        ui = ScriptedUI([3, 1])  # 2160p, only this once

        result = _run(request, ui)

        assert result.max_height == 2160
        assert "Estimated size" not in ui.text()
        assert "Size could not be calculated" not in ui.text()

    def test_a_single_compatibility_video_is_capped_without_asking(self, tmp_path: Path) -> None:
        request = _request(
            tmp_path,
            is_playlist=False,
            entries=None,
            mp4_profile=ProfileChoice.COMPATIBILITY,
        )
        ui = ScriptedUI()

        result = _run(request, ui)

        assert result.max_height == 1080
        assert ui.prompts == []

    def test_a_single_audio_download_asks_nothing(self, tmp_path: Path) -> None:
        request = _request(
            tmp_path, is_playlist=False, entries=None, mode=DownloadMode.AUDIO, mp4_profile=None
        )
        ui = ScriptedUI()

        result = _run(request, ui)

        assert result.max_height is None
        assert ui.prompts == []
        assert ui.messages == []

    def test_the_saved_video_default_is_marked(self, tmp_path: Path) -> None:
        settings = AppSettings()
        settings.video.max_height = 1440
        ui = ScriptedUI([2])

        result = _run(_request(tmp_path), ui, settings)

        assert ui.prompts[0][1][1] == "1440p (default)"
        assert result.max_height == 1440


class TestDiskSpace:
    def test_enough_space_asks_nothing(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])
        _run(_request(tmp_path), ui, free=10**15)
        assert "Not enough free space" not in ui.text()
        assert len(ui.prompts) == 1

    def test_too_little_space_offers_to_continue_anyway(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4, 1])  # unlimited, continue anyway

        result = _run(_request(tmp_path), ui, free=1000)

        assert "Not enough free space" in ui.text()
        assert result.action is PreflightAction.PROCEED

    def test_cancelling_is_logged(self, tmp_path: Path) -> None:
        request = _request(tmp_path)
        ui = ScriptedUI([4, 2])  # unlimited, cancel

        result = _run(request, ui, free=1000)

        assert result.action is PreflightAction.CANCEL
        assert "Cancelled: not enough free disk space" in ui.text()
        assert "Cancelled" in (tmp_path / "session.log").read_text(encoding="utf-8")

    def test_the_check_uses_the_chosen_resolution(self, tmp_path: Path) -> None:
        # 1080p needs about 1.85 GB and fits; unlimited (the 2160p row, about 9 GB) does not.
        free = 5_000_000_000
        ui_small = ScriptedUI([1, 1])  # 1080p differs from the unlimited default: save question
        result = _run(_request(tmp_path), ui_small, free=free)
        assert result.action is PreflightAction.PROCEED
        assert "Not enough free space" not in ui_small.text()

        ui_big = ScriptedUI([4, 1])
        _run(_request(tmp_path), ui_big, free=free)
        assert "Not enough free space" in ui_big.text()

    def test_unmeasurable_free_space_skips_the_check(self, tmp_path: Path) -> None:
        ui = ScriptedUI([4])

        result = _run(_request(tmp_path), ui, free=OSError("gone"))

        assert "Free disk space could not be measured" in ui.text()
        assert result.action is PreflightAction.PROCEED
        assert len(ui.prompts) == 1

    def test_audio_checks_space_too(self, tmp_path: Path) -> None:
        request = _request(tmp_path, mode=DownloadMode.AUDIO, mp4_profile=None)
        ui = ScriptedUI([2])  # cancel

        result = _run(request, ui, free=1000)

        assert result.action is PreflightAction.CANCEL

    def test_free_bytes_reads_the_real_disk(self, tmp_path: Path) -> None:
        assert free_bytes(tmp_path) > 0
