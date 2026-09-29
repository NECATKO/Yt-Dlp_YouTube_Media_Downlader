"""Advanced configuration settings for ytdlp_app.

This module provides extended configuration options that allow users
to customize download behavior, performance settings, and output formats.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final


@dataclass
class DownloadSettings:
    """Settings for download behavior and performance.

    These settings control how yt-dlp handles downloads, including
    retry behavior, rate limiting, and parallel downloads.

    Attributes:
        concurrent_fragments: Number of fragments to download in parallel.
        sleep_interval: Minimum seconds to sleep between downloads.
        max_sleep_interval: Maximum seconds to sleep between downloads.
        retries: Number of retries for failed downloads ('infinite' or int).
        fragment_retries: Number of retries for failed fragments.
        rate_limit: Download speed limit (e.g., '1M', '500K'), or None.
        proxy: HTTP/SOCKS proxy URL, or None.
    """

    concurrent_fragments: int = 4
    sleep_interval: int = 1
    max_sleep_interval: int = 3
    retries: str = "infinite"
    fragment_retries: str = "infinite"
    rate_limit: str | None = None
    proxy: str | None = None

    def to_args(self) -> list[str]:
        """Convert settings to yt-dlp command-line arguments.

        Returns:
            List of command-line arguments.
        """
        args = [
            "--continue",
            "--ignore-errors",
            "--retries",
            self.retries,
            "--fragment-retries",
            self.fragment_retries,
            "--concurrent-fragments",
            str(self.concurrent_fragments),
            "--sleep-interval",
            str(self.sleep_interval),
            "--max-sleep-interval",
            str(self.max_sleep_interval),
        ]
        args.extend(self.network_args())
        return args

    def network_args(self) -> list[str]:
        """Return only the rate limit and proxy arguments.

        Archive mode has its own retry and pacing policy but must still honor
        these two, so they are exposed separately.
        """
        args: list[str] = []

        if self.rate_limit:
            args.extend(["--limit-rate", self.rate_limit])

        if self.proxy:
            args.extend(["--proxy", self.proxy])

        return args


@dataclass
class AudioSettings:
    """Settings for audio extraction and conversion.

    Attributes:
        audio_quality: Audio quality (0=best, 9=worst).
        audio_format: Target audio format (mp3, m4a, opus, etc.).
        embed_thumbnail: Whether to embed thumbnail in audio files.
        embed_metadata: Whether to embed metadata in audio files.
        convert_thumbnails: Format to convert thumbnails to (jpg, png, etc.).
    """

    audio_quality: int = 0
    audio_format: str = "mp3"
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    convert_thumbnails: str = "jpg"

    def to_args(self) -> list[str]:
        """Convert settings to yt-dlp command-line arguments.

        Returns:
            List of command-line arguments for audio extraction.
        """
        args = [
            "--extract-audio",
            "--audio-format",
            self.audio_format,
            "--audio-quality",
            str(self.audio_quality),
        ]

        if self.embed_metadata:
            args.extend(["--embed-metadata", "--add-metadata"])

        if self.embed_thumbnail:
            args.append("--embed-thumbnail")
            if self.convert_thumbnails:
                args.extend(["--convert-thumbnails", self.convert_thumbnails])

        return args


@dataclass
class VideoSettings:
    """Settings for video downloads.

    Attributes:
        embed_thumbnail: Whether to embed thumbnail in video files.
        embed_metadata: Whether to embed metadata in video files.
        embed_subtitles: Whether to embed subtitles.
        subtitle_languages: Comma-separated list of subtitle languages.
        write_subtitles: Whether to download subtitles as separate files.
        max_height: Resolution cap for MP4 downloads (1080, 1440, 2160), or None for no cap.
    """

    embed_thumbnail: bool = True
    embed_metadata: bool = True
    embed_subtitles: bool = False
    subtitle_languages: str = "en"
    write_subtitles: bool = False
    max_height: int | None = None

    def to_args(self) -> list[str]:
        """Convert settings to yt-dlp command-line arguments.

        Returns:
            List of command-line arguments for video downloads.
        """
        args = []

        if self.embed_metadata:
            args.extend(["--embed-metadata", "--add-metadata"])

        if self.embed_thumbnail:
            args.append("--embed-thumbnail")

        if self.write_subtitles or self.embed_subtitles:
            args.append("--write-subs")
            args.extend(["--sub-langs", self.subtitle_languages])

            if self.embed_subtitles:
                args.append("--embed-subs")

        return args


#: The resolution caps the app offers. None (no cap) is always allowed.
ALLOWED_MAX_HEIGHTS: Final[tuple[int, ...]] = (1080, 1440, 2160)


def _as_max_height(value: Any, default: int | None) -> int | None:
    """Return a usable resolution cap: an offered height, None (no cap) or the default."""
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value in ALLOWED_MAX_HEIGHTS:
        return value
    return default


def _as_number(value: Any, default: float) -> float:
    """Coerce a config value to a non-negative number, or fall back.

    config.json is hand-editable, and a string or negative value here would
    otherwise reach yt-dlp as an argument it rejects.
    """
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number >= 0 else default


def _format_seconds(value: float) -> str:
    """Render seconds without a trailing ".0", so 15.0 reaches yt-dlp as "15"."""
    return f"{value:g}"


@dataclass
class ArchiveSettings:
    """Pacing for archive mode, tuned to stay under YouTube's rate limits.

    Archive mode walks an entire channel and requests several extra files per
    video (description, info JSON, thumbnail, subtitles), so it waits far longer
    than the regular modes. Only the waits are configurable; the retry count is
    fixed on purpose, because retrying forever against a rate limit is what
    turns a temporary block into a longer one.

    Attributes:
        sleep_requests: Seconds to wait between metadata/API requests.
        sleep_interval: Minimum seconds to wait before each video download.
        max_sleep_interval: Maximum seconds to wait before each video download.
        sleep_subtitles: Seconds to wait before each subtitle download.
        max_height: Resolution cap for archive downloads (1080, 1440, 2160), or None for no cap.
    """

    #: Retries per download and per fragment. Deliberately not "infinite".
    RETRIES = 10

    sleep_requests: float = 1.5
    sleep_interval: float = 15
    max_sleep_interval: float = 45
    sleep_subtitles: float = 5
    max_height: int | None = 1080

    def to_args(self) -> list[str]:
        """Convert the pacing and retry policy to yt-dlp arguments."""
        # yt-dlp rejects a sleep window whose upper bound is below its lower one.
        max_sleep = max(self.max_sleep_interval, self.sleep_interval)
        return [
            "--sleep-requests",
            _format_seconds(self.sleep_requests),
            "--sleep-interval",
            _format_seconds(self.sleep_interval),
            "--max-sleep-interval",
            _format_seconds(max_sleep),
            "--sleep-subtitles",
            _format_seconds(self.sleep_subtitles),
            "--retries",
            str(self.RETRIES),
            "--fragment-retries",
            str(self.RETRIES),
        ]

    def listing_args(self) -> list[str]:
        """Arguments for the playlist listing: only the wait between requests.

        The listing is a few requests, not a download, so the per-video waits and
        the retry policy of to_args do not apply.
        """
        return ["--sleep-requests", _format_seconds(self.sleep_requests)]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArchiveSettings:
        """Create archive settings, replacing unusable values with defaults."""
        defaults = cls()
        return cls(
            sleep_requests=_as_number(data.get("sleep_requests"), defaults.sleep_requests),
            sleep_interval=_as_number(data.get("sleep_interval"), defaults.sleep_interval),
            max_sleep_interval=_as_number(
                data.get("max_sleep_interval"), defaults.max_sleep_interval
            ),
            sleep_subtitles=_as_number(data.get("sleep_subtitles"), defaults.sleep_subtitles),
            max_height=_as_max_height(
                data.get("max_height", defaults.max_height), defaults.max_height
            ),
        )

    def to_dict(self) -> dict[str, float | None]:
        """Convert archive settings to a dictionary."""
        return {
            "sleep_requests": self.sleep_requests,
            "sleep_interval": self.sleep_interval,
            "max_sleep_interval": self.max_sleep_interval,
            "sleep_subtitles": self.sleep_subtitles,
            "max_height": self.max_height,
        }


@dataclass
class OutputSettings:
    """Settings for output file naming and organization.

    Attributes:
        single_video_template: Output template for single video downloads.
        single_audio_template: Output template for single audio downloads.
        playlist_video_template: Output template for playlist video downloads.
        playlist_audio_template: Output template for playlist audio downloads.
        archive_template: Output template for archive mode, relative to the
            videos folder's yt-dlp directory. Every video gets its own folder
            so its description, info JSON, thumbnail and subtitles stay together.
    """

    single_video_template: str = "%(title)s.%(ext)s"
    single_audio_template: str = "%(title)s.%(ext)s"
    playlist_video_template: str = "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"
    playlist_audio_template: str = "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"
    archive_template: str = (
        "%(channel)s/%(upload_date)s - %(title).80B [%(id)s]/%(title).80B.%(ext)s"
    )


@dataclass
class AppSettings:
    """Complete application settings.

    Persisted under the "settings" key of config.json. The interface language
    and the download directories are deliberately not here: they live at the top
    level of config.json because they are resolved before the settings are read.

    Attributes:
        download: Download behavior settings.
        audio: Audio extraction settings.
        video: Video download settings.
        output: Output template settings.
        archive: Archive mode pacing.
    """

    download: DownloadSettings = field(default_factory=DownloadSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    video: VideoSettings = field(default_factory=VideoSettings)
    output: OutputSettings = field(default_factory=OutputSettings)
    archive: ArchiveSettings = field(default_factory=ArchiveSettings)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppSettings:
        """Create settings from a dictionary.

        Args:
            data: Dictionary with settings values.

        Returns:
            AppSettings instance with values from the dictionary.
        """
        settings = cls()

        # Download settings
        if "download" in data:
            dl = data["download"]
            settings.download = DownloadSettings(
                concurrent_fragments=dl.get("concurrent_fragments", 4),
                sleep_interval=dl.get("sleep_interval", 1),
                max_sleep_interval=dl.get("max_sleep_interval", 3),
                retries=dl.get("retries", "infinite"),
                fragment_retries=dl.get("fragment_retries", "infinite"),
                rate_limit=dl.get("rate_limit"),
                proxy=dl.get("proxy"),
            )

        # Audio settings
        if "audio" in data:
            au = data["audio"]
            settings.audio = AudioSettings(
                audio_quality=au.get("audio_quality", 0),
                audio_format=au.get("audio_format", "mp3"),
                embed_thumbnail=au.get("embed_thumbnail", True),
                embed_metadata=au.get("embed_metadata", True),
                convert_thumbnails=au.get("convert_thumbnails", "jpg"),
            )

        # Video settings
        if "video" in data:
            vi = data["video"]
            settings.video = VideoSettings(
                embed_thumbnail=vi.get("embed_thumbnail", True),
                embed_metadata=vi.get("embed_metadata", True),
                embed_subtitles=vi.get("embed_subtitles", False),
                subtitle_languages=vi.get("subtitle_languages", "en"),
                write_subtitles=vi.get("write_subtitles", False),
                max_height=_as_max_height(vi.get("max_height"), None),
            )

        # Output settings
        if "output" in data:
            ou = data["output"]
            defaults = OutputSettings()
            settings.output = OutputSettings(
                single_video_template=ou.get("single_video_template", "%(title)s.%(ext)s"),
                single_audio_template=ou.get("single_audio_template", "%(title)s.%(ext)s"),
                playlist_video_template=ou.get(
                    "playlist_video_template",
                    "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s",
                ),
                playlist_audio_template=ou.get(
                    "playlist_audio_template",
                    "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s",
                ),
                archive_template=ou.get("archive_template", defaults.archive_template),
            )

        # Archive settings
        if isinstance(data.get("archive"), dict):
            settings.archive = ArchiveSettings.from_dict(data["archive"])

        return settings

    def to_dict(self) -> dict[str, Any]:
        """Convert settings to a dictionary.

        Returns:
            Dictionary representation of all settings.
        """
        return {
            "download": {
                "concurrent_fragments": self.download.concurrent_fragments,
                "sleep_interval": self.download.sleep_interval,
                "max_sleep_interval": self.download.max_sleep_interval,
                "retries": self.download.retries,
                "fragment_retries": self.download.fragment_retries,
                "rate_limit": self.download.rate_limit,
                "proxy": self.download.proxy,
            },
            "audio": {
                "audio_quality": self.audio.audio_quality,
                "audio_format": self.audio.audio_format,
                "embed_thumbnail": self.audio.embed_thumbnail,
                "embed_metadata": self.audio.embed_metadata,
                "convert_thumbnails": self.audio.convert_thumbnails,
            },
            "video": {
                "embed_thumbnail": self.video.embed_thumbnail,
                "embed_metadata": self.video.embed_metadata,
                "embed_subtitles": self.video.embed_subtitles,
                "subtitle_languages": self.video.subtitle_languages,
                "write_subtitles": self.video.write_subtitles,
                "max_height": self.video.max_height,
            },
            "output": {
                "single_video_template": self.output.single_video_template,
                "single_audio_template": self.output.single_audio_template,
                "playlist_video_template": self.output.playlist_video_template,
                "playlist_audio_template": self.output.playlist_audio_template,
                "archive_template": self.output.archive_template,
            },
            "archive": self.archive.to_dict(),
        }
