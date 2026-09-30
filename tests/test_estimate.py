"""Tests for ytdlp_app.estimate: the pure size, space and time arithmetic."""

import pytest

from ytdlp_app.estimate import (
    RESOLUTIONS,
    UNLIMITED_HEIGHT,
    VideoSet,
    archive_wait,
    audio_output_kbps,
    download_seconds,
    effective_speed,
    estimate_audio,
    estimate_video,
    format_duration,
    format_size,
    parse_rate_limit,
    plan_videos,
    size_bytes,
)
from ytdlp_app.i18n import set_language
from ytdlp_app.models import PlaylistEntry


@pytest.fixture(autouse=True)
def _english():
    set_language("en")
    yield
    set_language("en")


def _entry(vid: str, duration: float | None = None, *, short: bool = False) -> PlaylistEntry:
    return PlaylistEntry(
        playlist_index=1,
        id=vid,
        title="t",
        watch_url=f"https://www.youtube.com/watch?v={vid}",
        duration=duration,
        is_short=short,
    )


class TestBitRates:
    def test_size_is_seconds_times_kilobits_over_eight(self) -> None:
        assert size_bytes(3600, 8) == 3_600_000

    @pytest.mark.parametrize(
        ("fmt", "quality", "expected"),
        [
            ("mp3", 0, 245),
            ("mp3", 5, 130),
            ("mp3", 9, 65),
            ("mp3", 99, 65),
            ("mp3", -1, 245),
            ("flac", 0, 1100),
            ("wav", 0, 1536),
            ("m4a", 0, 160),
            ("opus", 0, 160),
            ("best", 0, 160),
            ("aac", 0, 160),
        ],
    )
    def test_audio_output_bit_rate(self, fmt: str, quality: int, expected: int) -> None:
        assert audio_output_kbps(fmt, quality) == expected

    def test_offered_resolutions(self) -> None:
        assert RESOLUTIONS == (1080, 1440, 2160)


class TestPlanVideos:
    def test_duplicates_by_id_are_counted_once(self) -> None:
        videos = plan_videos([_entry("a", 100), _entry("a", 100), _entry("b", 200)], set())
        assert videos is not None
        assert videos.seconds == (100.0, 200.0)

    def test_archived_videos_are_left_out_and_counted(self) -> None:
        videos = plan_videos([_entry("a", 100), _entry("b", 200)], {"a"})
        assert videos is not None
        assert videos.seconds == (200.0,)
        assert videos.archived == 1

    def test_entries_without_an_id_are_kept_each(self) -> None:
        videos = plan_videos([_entry("", 100), _entry("", 100)], {""})
        assert videos is not None
        assert videos.count == 2

    def test_shorts_without_a_duration_get_180_seconds(self) -> None:
        videos = plan_videos([_entry("a", 600), _entry("s", None, short=True)], set())
        assert videos is not None
        assert videos.seconds == (600.0, 180.0)
        assert videos.assumed == 1

    def test_other_missing_durations_get_the_median(self) -> None:
        entries = [_entry("a", 100), _entry("b", 300), _entry("c", 500), _entry("d")]
        videos = plan_videos(entries, set())
        assert videos is not None
        assert videos.seconds == (100.0, 300.0, 500.0, 300.0)
        assert videos.assumed == 1

    def test_the_median_also_counts_archived_videos(self) -> None:
        videos = plan_videos([_entry("x", 1000), _entry("y")], {"x"})
        assert videos is not None
        assert videos.seconds == (1000.0,)

    def test_an_archived_video_without_a_duration_is_not_an_assumption(self) -> None:
        videos = plan_videos([_entry("a", 100), _entry("z")], {"z"})
        assert videos is not None
        assert videos.assumed == 0

    def test_no_known_duration_and_no_shorts_cannot_be_estimated(self) -> None:
        assert plan_videos([_entry("a"), _entry("b")], set()) is None

    def test_only_shorts_can_still_be_estimated(self) -> None:
        videos = plan_videos([_entry("s1", None, short=True)], set())
        assert videos is not None
        assert videos.seconds == (180.0,)

    def test_no_entries_cannot_be_estimated(self) -> None:
        assert plan_videos([], set()) is None

    def test_everything_archived_leaves_nothing_to_download(self) -> None:
        videos = plan_videos([_entry("a", 100)], {"a"})
        assert videos is not None
        assert videos.count == 0
        assert videos.archived == 1

    def test_video_set_totals(self) -> None:
        videos = VideoSet(seconds=(60.0, 120.0), assumed=0, archived=0)
        assert videos.count == 2
        assert videos.total_seconds == 180.0
        assert videos.longest_seconds == 120.0
        assert VideoSet((), 0, 0).longest_seconds == 0.0


class TestEstimates:
    VIDEOS = VideoSet(seconds=(600.0, 1200.0), assumed=0, archived=0)

    def test_video_1080p(self) -> None:
        estimate = estimate_video(self.VIDEOS, 1080)
        # (6000 + 160) kbit/s: 462 MB for 600 s, 924 MB for 1200 s.
        assert estimate.height == 1080
        assert estimate.total_bytes == 1_386_000_000
        # Space needed = everything + the largest single video (source and output coexist).
        assert estimate.required_bytes == 1_386_000_000 + 924_000_000
        assert estimate.download_bytes == estimate.total_bytes

    def test_the_audio_estimate_never_undercounts_a_small_output(self) -> None:
        """A 65 kbit/s MP3 is smaller than its ~160 kbit/s source: the source is the peak."""
        videos = VideoSet(seconds=(600.0, 600.0), assumed=0, archived=0)
        estimate = estimate_audio(videos, 65)

        source = 12_000_000
        assert estimate.required_bytes >= estimate.total_bytes + source

    def test_a_large_output_is_covered_too(self) -> None:
        """wav is far bigger than its source; the peak is every output plus one source."""
        videos = VideoSet(seconds=(600.0, 300.0), assumed=0, archived=0)
        estimate = estimate_audio(videos, 1536)

        assert estimate.required_bytes == estimate.total_bytes + 12_000_000

    def test_higher_resolutions_need_more(self) -> None:
        sizes = [estimate_video(self.VIDEOS, h).total_bytes for h in RESOLUTIONS]
        assert sizes == sorted(sizes)
        assert len(set(sizes)) == 3

    def test_audio_counts_output_for_space_and_the_source_for_the_download(self) -> None:
        videos = VideoSet(seconds=(600.0,), assumed=0, archived=0)
        estimate = estimate_audio(videos, 245)

        assert estimate.height is None
        assert estimate.total_bytes == 18_375_000
        # While the last file converts, all finished outputs plus that file's *source*
        # (the ~160 kbit/s stream, 12 MB) are on disk, and the output is already in the
        # total. Counting the largest output instead under-estimated small outputs.
        assert estimate.required_bytes == 18_375_000 + 12_000_000
        # The network carries the ~160 kbit/s source stream, not the MP3.
        assert estimate.download_bytes == 12_000_000


class TestSpeed:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("1M", 1024.0**2),
            ("500K", 512_000.0),
            ("4.2M", 4.2 * 1024**2),
            ("2g", 2 * 1024.0**3),
            ("50", 50.0),
        ],
    )
    def test_rate_limit_is_parsed(self, text: str, expected: float) -> None:
        assert parse_rate_limit(text) == pytest.approx(expected)

    @pytest.mark.parametrize("text", ["fast", "", None, "0", "M", "1 M"])
    def test_unusable_rate_limits_are_ignored(self, text: str | None) -> None:
        assert parse_rate_limit(text) is None

    def test_effective_speed_is_capped_by_the_limit(self) -> None:
        assert effective_speed(2_000_000, "1M") == 1024.0**2
        assert effective_speed(500_000, "1M") == 500_000

    def test_effective_speed_without_a_measurement_is_unknown(self) -> None:
        assert effective_speed(None, "1M") is None
        assert effective_speed(0, None) is None

    def test_an_unusable_limit_does_not_change_the_speed(self) -> None:
        assert effective_speed(1_000_000, "bogus") == 1_000_000

    def test_download_seconds(self) -> None:
        assert download_seconds(1000, 100.0) == 10.0
        assert download_seconds(1000, None) is None
        assert download_seconds(1000, 0.0) is None


class TestArchiveWait:
    def test_minimum_and_expected_are_different_numbers(self) -> None:
        wait = archive_wait(10, 15, 45)

        # The shortest possible waits are all 15 s; on average they are 30 s.
        assert wait.minimum == 150.0
        assert wait.expected == 300.0

    def test_a_single_video_shows_the_same_gap(self) -> None:
        wait = archive_wait(1, 15, 45)

        assert (wait.minimum, wait.expected) == (15.0, 30.0)

    def test_a_max_below_the_min_is_treated_as_the_min(self) -> None:
        wait = archive_wait(10, 20, 5)

        assert wait.minimum == wait.expected == 200.0

    def test_no_videos_no_wait(self) -> None:
        wait = archive_wait(0, 15, 45)

        assert (wait.minimum, wait.expected) == (0.0, 0.0)


class TestUnlimitedResolution:
    """ "No limit" is not 2160p: YouTube serves 4320p (8K) too."""

    VIDEOS = VideoSet(seconds=(600.0,), assumed=0, archived=0)

    def test_the_unlimited_estimate_exceeds_the_2160p_one(self) -> None:
        capped = estimate_video(self.VIDEOS, 2160)
        unlimited = estimate_video(self.VIDEOS, None)

        assert unlimited.total_bytes > capped.total_bytes
        assert unlimited.required_bytes > capped.required_bytes

    def test_the_unlimited_row_says_it_is_the_unlimited_one(self) -> None:
        assert estimate_video(self.VIDEOS, None).height == UNLIMITED_HEIGHT

    def test_no_capped_row_is_treated_as_the_upper_bound(self) -> None:
        assert max(RESOLUTIONS) < UNLIMITED_HEIGHT


class TestFormatting:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (0, "0 B"),
            (1023, "1023 B"),
            (1024, "1.0 KiB"),
            (1536, "1.5 KiB"),
            (1024**2, "1.0 MiB"),
            (43 * 1024**3, "43.0 GiB"),
            (5 * 1024**4, "5.0 TiB"),
            (2000 * 1024**4, "2000.0 TiB"),
            (-5, "0 B"),
        ],
    )
    def test_sizes_are_1024_based(self, value: float, expected: str) -> None:
        assert format_size(value) == expected

    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            (0, "0 s"),
            (45, "45 s"),
            (90, "1 min"),
            (3600, "1 h 0 min"),
            (3720, "1 h 2 min"),
            (90000, "1 d 1 h"),
        ],
    )
    def test_durations(self, seconds: float, expected: str) -> None:
        assert format_duration(seconds) == expected

    def test_durations_follow_the_language(self) -> None:
        set_language("tr")
        assert format_duration(3720) == "1 sa 2 dk"
