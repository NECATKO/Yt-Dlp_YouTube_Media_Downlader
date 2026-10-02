"""Tests for ytdlp_app.playlist module."""

import json
from pathlib import Path
from typing import Any

import pytest

from ytdlp_app.exceptions import PlaylistError
from ytdlp_app.playlist import (
    channel_id_from_url,
    fetch_listing,
    fetch_playlist_entries,
    get_playlist_id,
    is_channel_url,
    is_playlist_url,
    read_archive_ids,
    video_id_from_url,
)


class TestIsPlaylistUrl:
    """Tests for is_playlist_url function."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/playlist?list=PLtest123",
            "https://www.youtube.com/watch?v=abc&list=PLtest123",
            "https://youtube.com/playlist?list=PLtest123",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=RDdQw4w9WgXcQ",
        ],
    )
    def test_returns_true_for_playlist_urls(self, url: str) -> None:
        """Test playlist URLs are detected correctly."""
        assert is_playlist_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/channel/UCtest123",
            "https://www.youtube.com/c/ChannelName",
            "https://www.youtube.com/user/username",
            "https://www.youtube.com/@ChannelHandle",
        ],
    )
    def test_returns_true_for_channel_urls(self, url: str) -> None:
        """Test channel URLs are treated as playlists."""
        assert is_playlist_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/abc123",
        ],
    )
    def test_returns_false_for_single_video_urls(self, url: str) -> None:
        """Test single video URLs are not detected as playlists."""
        assert is_playlist_url(url) is False


class TestGetPlaylistId:
    """Tests for get_playlist_id function."""

    def test_extracts_id_from_list_param(self) -> None:
        """Test extracting playlist ID from 'list' query param."""
        url = "https://www.youtube.com/playlist?list=PLtest123"
        assert get_playlist_id(url) == "PLtest123"

    def test_extracts_id_from_video_with_list(self) -> None:
        """Test extracting playlist ID from video URL with list param."""
        url = "https://www.youtube.com/watch?v=abc&list=PLtest456"
        assert get_playlist_id(url) == "PLtest456"

    def test_extracts_channel_id(self) -> None:
        """Test extracting channel ID from channel URL."""
        url = "https://www.youtube.com/channel/UCtest123"
        assert get_playlist_id(url) == "UCtest123"

    def test_extracts_handle_without_at(self) -> None:
        """Test extracting handle without @ prefix."""
        url = "https://www.youtube.com/@ChannelHandle"
        assert get_playlist_id(url) == "ChannelHandle"

    def test_returns_unknown_for_empty_path(self) -> None:
        """Test fallback for URLs without identifiable ID."""
        url = "https://www.youtube.com/"
        assert get_playlist_id(url) == "unknown_playlist"


class TestReadArchiveIds:
    """Tests for read_archive_ids function."""

    def test_returns_empty_set_for_missing_file(self, tmp_path: Path) -> None:
        """Test reading non-existent archive returns empty set."""
        archive_path = tmp_path / "nonexistent.txt"
        result = read_archive_ids(archive_path)
        assert result == set()

    def test_reads_video_ids_from_archive(self, tmp_path: Path) -> None:
        """Test reading video IDs from archive file."""
        archive_path = tmp_path / "archive.txt"
        archive_path.write_text(
            "youtube dQw4w9WgXcQ\nyoutube abc123def\nyoutube xyz789\n",
            encoding="utf-8",
        )

        result = read_archive_ids(archive_path)
        assert result == {"dQw4w9WgXcQ", "abc123def", "xyz789"}

    def test_ignores_empty_lines(self, tmp_path: Path) -> None:
        """Test empty lines are ignored."""
        archive_path = tmp_path / "archive.txt"
        archive_path.write_text(
            "youtube vid1\n\nyoutube vid2\n   \nyoutube vid3\n",
            encoding="utf-8",
        )

        result = read_archive_ids(archive_path)
        assert result == {"vid1", "vid2", "vid3"}

    def test_handles_different_formats(self, tmp_path: Path) -> None:
        """Test handling various archive line formats."""
        archive_path = tmp_path / "archive.txt"
        archive_path.write_text(
            "youtube vid1\nvimeo vid2\ndailymotion vid3\n",
            encoding="utf-8",
        )

        result = read_archive_ids(archive_path)
        # Should extract the last part (video ID) regardless of prefix
        assert result == {"vid1", "vid2", "vid3"}


class TestIsChannelUrl:
    """Archive mode treats these as a whole channel (nested tab playlists)."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/@ChannelHandle",
            "https://www.youtube.com/@ChannelHandle/",
            "https://www.youtube.com/@ChannelHandle/videos",
            "https://www.youtube.com/@ChannelHandle/shorts",
            "https://www.youtube.com/@ChannelHandle/streams",
            "https://youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw",
            "https://m.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw/videos",
            "https://www.youtube.com/c/ChannelName",
            "https://www.youtube.com/user/username",
        ],
    )
    def test_detects_channels_and_their_tabs(self, url: str) -> None:
        assert is_channel_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/abc123",
            "https://www.youtube.com/playlist?list=PLtest123",
            # Redirects to the current live stream: a single video.
            "https://www.youtube.com/@ChannelHandle/live",
            # Right path shape, wrong site.
            "https://example.com/@ChannelHandle",
        ],
    )
    def test_rejects_everything_else(self, url: str) -> None:
        assert is_channel_url(url) is False

    def test_every_channel_url_is_also_a_playlist_url(self) -> None:
        """The session relies on this to download with --yes-playlist."""
        assert is_playlist_url("https://www.youtube.com/@ChannelHandle/videos") is True


class TestChannelIdFromUrl:
    def test_reads_the_id_from_a_channel_url(self) -> None:
        url = "https://www.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw/videos"
        assert channel_id_from_url(url) == "UCuAXFkgsw1L7xaCfnd5JJOw"

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/@ChannelHandle",
            "https://www.youtube.com/channel/not-a-channel-id",
        ],
    )
    def test_returns_none_without_a_real_id(self, url: str) -> None:
        assert channel_id_from_url(url) is None


CHANNEL_ID = "UCuAXFkgsw1L7xaCfnd5JJOw"


def _nested_channel_json(top_level_id: bool = True) -> dict[str, Any]:
    """What yt-dlp --flat-playlist -J returns for a bare channel URL: the
    Videos/Shorts/Live tabs as nested playlist entries."""
    data: dict[str, Any] = {
        "_type": "playlist",
        "title": "Channel Name",
        "entries": [
            {
                "_type": "url",
                "ie_key": "YoutubeTab",
                "url": "https://www.youtube.com/@ChannelHandle/videos",
                "title": "Channel Name - Videos",
                "channel_id": CHANNEL_ID,
            },
            {
                "_type": "url",
                "ie_key": "YoutubeTab",
                "url": "https://www.youtube.com/@ChannelHandle/shorts",
                "title": "Channel Name - Shorts",
            },
        ],
    }
    if top_level_id:
        data["id"] = CHANNEL_ID
        data["channel_id"] = CHANNEL_ID
    return data


class FakeRunner:
    def __init__(self, rc: int = 0, out: str = "", err: str = "") -> None:
        self.rc, self.out, self.err = rc, out, err
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str]) -> tuple[int, str, str]:
        self.calls.append(cmd)
        return self.rc, self.out, self.err


def _video(vid: str, *, duration: Any = None, short: bool = False) -> dict[str, Any]:
    """One flat-listing video entry, as yt-dlp emits it."""
    path = f"shorts/{vid}" if short else f"watch?v={vid}"
    raw: dict[str, Any] = {
        "_type": "url",
        "ie_key": "Youtube",
        "id": vid,
        "url": f"https://www.youtube.com/{path}",
        "title": f"Title {vid}",
    }
    if duration is not None:
        raw["duration"] = duration
    return raw


def _filled_channel_json() -> dict[str, Any]:
    """What yt-dlp really returns for a bare channel URL: the tabs come back as
    nested playlists whose entries are already filled in (extractor/youtube/_tab.py
    runs _real_extract on each extra tab)."""
    return {
        "_type": "playlist",
        "id": CHANNEL_ID,
        "channel_id": CHANNEL_ID,
        "title": "Channel",
        "entries": [
            {
                "_type": "playlist",
                "id": "videos-tab",
                "title": "Channel - Videos",
                "entries": [_video("vid1", duration=600), _video("vid2", duration=300)],
            },
            {
                "_type": "playlist",
                "id": "shorts-tab",
                "title": "Channel - Shorts",
                "entries": [_video("sh1", short=True)],
            },
        ],
    }


class TestFlatListing:
    def test_channel_tabs_are_flattened_into_their_videos(self) -> None:
        runner = FakeRunner(out=json.dumps(_filled_channel_json()))

        entries = fetch_playlist_entries("https://www.youtube.com/@ChannelHandle", [], runner)

        assert [e.id for e in entries] == ["vid1", "vid2", "sh1"]
        assert [e.playlist_index for e in entries] == [1, 2, 3]


class TestFetchListing:
    URL = "https://www.youtube.com/@ChannelHandle"

    def test_unexpanded_tab_stubs_contribute_no_videos(self) -> None:
        runner = FakeRunner(out=json.dumps(_nested_channel_json()))
        assert fetch_listing(self.URL, [], runner).entries == []

    def test_expanded_and_stub_tabs_can_be_mixed(self) -> None:
        data = _filled_channel_json()
        data["entries"].append(
            {
                "_type": "url",
                "ie_key": "YoutubeTab",
                "url": "https://www.youtube.com/@ChannelHandle/streams",
                "title": "Channel - Live",
            }
        )
        entries = fetch_listing(self.URL, [], FakeRunner(out=json.dumps(data))).entries
        assert [e.id for e in entries] == ["vid1", "vid2", "sh1"]

    def test_duration_and_shorts_are_carried(self) -> None:
        entries = fetch_listing(
            self.URL, [], FakeRunner(out=json.dumps(_filled_channel_json()))
        ).entries
        vid1, _vid2, short = entries

        assert vid1.duration == 600.0
        assert vid1.is_short is False
        assert short.duration is None
        assert short.is_short is True
        # The watch URL stays a plain watch URL, which is what the skip probe wants.
        assert short.watch_url == "https://www.youtube.com/watch?v=sh1"

    @pytest.mark.parametrize("bad", ["abc", True, 0, -5])
    def test_unusable_durations_are_dropped(self, bad: Any) -> None:
        data = {"_type": "playlist", "entries": [{**_video("v1"), "duration": bad}]}
        (entry,) = fetch_listing(self.URL, [], FakeRunner(out=json.dumps(data))).entries
        assert entry.duration is None

    def test_channel_id_is_read_from_the_listing(self) -> None:
        listing = fetch_listing(self.URL, [], FakeRunner(out=json.dumps(_filled_channel_json())))
        assert listing.channel_id == CHANNEL_ID

    def test_channel_id_in_the_url_wins(self) -> None:
        data = {"_type": "playlist", "entries": [_video("v1")]}
        url = f"https://www.youtube.com/channel/{CHANNEL_ID}"
        listing = fetch_listing(url, [], FakeRunner(out=json.dumps(data)))
        assert listing.channel_id == CHANNEL_ID

    def test_plain_playlist_has_no_channel_id(self, sample_playlist_json: dict[str, Any]) -> None:
        listing = fetch_listing(
            "https://www.youtube.com/playlist?list=PLtest123",
            [],
            FakeRunner(out=json.dumps(sample_playlist_json)),
        )
        assert listing.channel_id is None

    def test_extra_args_follow_the_url_and_nothing_limits_the_listing(self) -> None:
        runner = FakeRunner(out=json.dumps(_filled_channel_json()))
        extra = ["--sleep-requests", "1.5", "--proxy", "http://p:1"]

        fetch_listing(self.URL, extra, runner)

        (cmd,) = runner.calls
        assert cmd == ["yt-dlp", "--flat-playlist", "-J", "--yes-playlist", self.URL, *extra]

    def test_interrupt_is_raised(self) -> None:
        with pytest.raises(KeyboardInterrupt):
            fetch_listing(self.URL, [], FakeRunner(rc=130))

    def test_failure_raises_with_stderr(self) -> None:
        with pytest.raises(PlaylistError, match="boom"):
            fetch_listing(self.URL, [], FakeRunner(rc=1, err="boom"))

    @pytest.mark.parametrize("out", ["not json", "[]", "   "])
    def test_unusable_output_raises(self, out: str) -> None:
        with pytest.raises(PlaylistError):
            fetch_listing(self.URL, [], FakeRunner(out=out))

    def test_channel_id_falls_back_to_the_nested_entries(self) -> None:
        data = _nested_channel_json(top_level_id=False)
        listing = fetch_listing(self.URL, [], FakeRunner(out=json.dumps(data)))
        assert listing.channel_id == CHANNEL_ID

    def test_fetch_playlist_entries_still_lists_a_plain_playlist(
        self, sample_playlist_json: dict[str, Any]
    ) -> None:
        entries = fetch_playlist_entries(
            "https://www.youtube.com/playlist?list=PLtest123",
            [],
            FakeRunner(out=json.dumps(sample_playlist_json)),
        )
        assert [e.id for e in entries] == ["vid1", "vid2", "vid3"]
        assert entries[0].watch_url == "https://www.youtube.com/watch?v=vid1"


class TestUrlClassification:
    """Redirect forms are single videos, look-alike paths are not channels, and only
    YouTube's own hosts are ever treated as playlists or channels."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/@ChannelHandle/live",
            "https://www.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw/live",
            "https://www.youtube.com/c/Name/live",
            "https://www.youtube.com/live/dQw4w9WgXcQ",
            "https://www.youtube.com/clip/UgkxSomeClipId",
            "https://www.youtube.com/channelsomething",
            "https://www.youtube.com/cats",
            "https://www.youtube.com/user",
            "https://www.youtube.com/embed/dQw4w9WgXcQ",
        ],
    )
    def test_single_video_redirects_and_lookalike_paths_are_not_playlists(self, url: str) -> None:
        assert is_playlist_url(url) is False

    @pytest.mark.parametrize(
        "url",
        [
            "https://vimeo.com/channels/staffpicks",
            "https://soundcloud.com/@someone",
            "https://example.com/watch?v=1&list=abc",
            "https://example.com/playlist?list=abc",
            "https://notyoutube.com/@handle",
            "https://youtube.com.evil.example/playlist?list=PL1",
        ],
    )
    def test_other_sites_are_never_playlists_or_channels(self, url: str) -> None:
        assert is_playlist_url(url) is False
        assert is_channel_url(url) is False

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/@ChannelHandle/videos",
            "https://www.youtube.com/@ChannelHandle/shorts",
            "https://www.youtube.com/@ChannelHandle/streams",
            "https://www.youtube.com/@ChannelHandle/playlists",
            "https://www.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw/videos",
            "https://www.youtube.com/c/Name/videos",
            "https://www.youtube.com/user/name/streams",
            "https://youtu.be/dQw4w9WgXcQ?list=PLtest123",
            "https://music.youtube.com/playlist?list=PLtest123",
            "https://m.youtube.com/playlist?list=PLtest123",
        ],
    )
    def test_youtube_playlists_channels_and_their_tabs_still_are(self, url: str) -> None:
        assert is_playlist_url(url) is True

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://www.youtube.com/@ChannelHandle/videos", "ChannelHandle"),
            ("https://www.youtube.com/@ChannelHandle/shorts", "ChannelHandle"),
            ("https://www.youtube.com/@ChannelHandle/", "ChannelHandle"),
            (
                "https://www.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw/videos",
                "UCuAXFkgsw1L7xaCfnd5JJOw",
            ),
            ("https://www.youtube.com/c/Name/videos", "Name"),
            ("https://www.youtube.com/user/somebody/streams", "somebody"),
        ],
    )
    def test_the_id_names_the_channel_never_the_tab(self, url: str, expected: str) -> None:
        """Two channels' /videos tabs used to share one archive called "videos"."""
        assert get_playlist_id(url) == expected

    def test_two_channels_never_share_an_id(self) -> None:
        first = get_playlist_id("https://www.youtube.com/@Alpha/videos")
        second = get_playlist_id("https://www.youtube.com/@Beta/videos")

        assert first != second

    @pytest.mark.parametrize(
        ("host", "expected"),
        [
            ("youtube.com", True),
            ("www.youtube.com", True),
            ("m.youtube.com", True),
            ("music.youtube.com", True),
            ("youtu.be", True),
            ("www.youtube-nocookie.com", True),
            ("notyoutube.com", False),
            ("youtube.com.evil.example", False),
            ("vimeo.com", False),
        ],
    )
    def test_youtube_hosts(self, host: str, expected: bool) -> None:
        from ytdlp_app.playlist import is_youtube_host  # noqa: PLC0415

        assert is_youtube_host(f"https://{host}/x") is expected


class TestForeignExtractorEntries:
    """An entry from another site must keep its own address, not become a watch URL."""

    def make(self, raw: dict[str, Any]) -> Any:
        listing = {"_type": "playlist", "id": "x", "entries": [raw]}
        return fetch_listing(
            "https://www.youtube.com/playlist?list=PL1",
            [],
            FakeRunner(out=__import__("json").dumps(listing)),
        ).entries[0]

    def test_a_foreign_entry_keeps_its_own_url(self) -> None:
        entry = self.make(
            {"_type": "url", "ie_key": "Vimeo", "id": "123456", "url": "https://vimeo.com/123456"}
        )

        assert entry.watch_url == "https://vimeo.com/123456"

    def test_a_foreign_entry_without_a_usable_url_gets_none(self) -> None:
        entry = self.make({"_type": "url", "ie_key": "Vimeo", "id": "123456"})

        assert entry.watch_url == ""

    def test_a_youtube_entry_with_only_an_id_still_gets_a_watch_url(self) -> None:
        entry = self.make({"_type": "url", "ie_key": "Youtube", "id": "abcDEF12345"})

        assert entry.watch_url == "https://www.youtube.com/watch?v=abcDEF12345"


class TestVideoIdFromUrl:
    @pytest.mark.parametrize(
        ("url", "ident"),
        [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL1", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ?t=3", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://m.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/@chan/live", None),
            ("https://www.youtube.com/playlist?list=PL1", None),
            ("https://www.youtube.com/watch?v=short", None),
            ("https://vimeo.com/12345678901", None),
        ],
    )
    def test_the_id_a_single_video_url_names(self, url: str, ident: str | None) -> None:
        assert video_id_from_url(url) == ident
