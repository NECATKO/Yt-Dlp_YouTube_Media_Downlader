"""Advanced configuration settings for ytdlp_app.

This module provides extended configuration options that allow users
to customize download behavior, performance settings, and output formats.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Final

#: Audio containers offered for extraction. "best" keeps the source codec.
AUDIO_FORMATS: Final[tuple[str, ...]] = ("mp3", "m4a", "opus", "flac", "wav", "best")

#: Thumbnail formats yt-dlp can convert to; "" leaves the thumbnail as it is.
THUMBNAIL_FORMATS: Final[tuple[str, ...]] = ("jpg", "png", "webp")

#: Upper bound for any wait, in seconds.
MAX_WAIT_SECONDS: Final = 3600

#: Upper bound for a retry count.
MAX_RETRIES: Final = 1000

#: The resolution caps the app offers. None (no cap) is always allowed.
ALLOWED_MAX_HEIGHTS: Final[tuple[int, ...]] = (1080, 1440, 2160)

_RATE_LIMIT_RE = re.compile(r"^\d+(?:\.\d+)?[KMGkmg]?$")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_INFINITE_SPELLINGS: Final = frozenset({"infinite", "inf", "infinity"})

#: The templates shipped up to config_version 1. They name a file by title alone
#: (or by playlist position and title), so two different videos with the same title
#: land on one file and the second is silently taken for a duplicate. A saved
#: setting that still equals one of these is migrated; anything else is the user's own.
LEGACY_TEMPLATES: Final[dict[str, str]] = {
    "single_video_template": "%(title)s.%(ext)s",
    "single_audio_template": "%(title)s.%(ext)s",
    "playlist_video_template": "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s",
    "playlist_audio_template": "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s",
}


@dataclass(frozen=True, slots=True)
class SettingsIssue:
    """One unusable (or questionable) value found while reading the settings.

    Attributes:
        field: Dotted path of the setting, such as "download.retries".
        problem: What is wrong with the value, in English (it is quoted to the user).
        fallback: The value used instead, or None when the value was kept (a warning).
    """

    field: str
    problem: str
    fallback: str | None = None


def _report(
    issues: list[SettingsIssue] | None, path: str, problem: str, fallback: object = None
) -> None:
    if issues is not None:
        issues.append(SettingsIssue(path, problem, None if fallback is None else str(fallback)))


def _section(data: dict[str, Any], name: str, issues: list[SettingsIssue] | None) -> dict[str, Any]:
    """Return a settings section, or {} (with a report) when it is not a mapping."""
    if name not in data:
        return {}
    value = data[name]
    if isinstance(value, dict):
        return value
    _report(issues, name, f"expected an object, found {type(value).__name__}", "defaults")
    return {}


def _bool(
    section: dict[str, Any], key: str, default: bool, path: str, issues: list[SettingsIssue] | None
) -> bool:
    if key not in section:
        return default
    value = section[key]
    if isinstance(value, bool):
        return value
    _report(issues, path, f"expected true or false, found {value!r}", default)
    return default


def _number(
    section: dict[str, Any],
    key: str,
    default: float,
    path: str,
    issues: list[SettingsIssue] | None,
    *,
    low: float = 0,
    high: float = MAX_WAIT_SECONDS,
    integer: bool = False,
    strings: bool = False,
) -> float:
    """Read a finite number in [low, high]; a whole number when integer is set.

    Numeric strings are accepted only where strings is set (a hand-written wait such
    as "4"); booleans, NaN and infinity never are.
    """
    if key not in section or section[key] is None:
        return default
    value = section[key]
    number: float | None = None
    if not isinstance(value, bool):
        if isinstance(value, int | float):
            number = float(value)
        elif strings and isinstance(value, str):
            try:
                number = float(value)
            except ValueError:
                number = None
    if number is None or not math.isfinite(number) or not low <= number <= high:
        _report(
            issues, path, f"expected a number from {low:g} to {high:g}, found {value!r}", default
        )
        return default
    if integer and not number.is_integer():
        _report(issues, path, f"expected a whole number, found {value!r}", default)
        return default
    return int(number) if number.is_integer() else number


def _retries(
    section: dict[str, Any], key: str, path: str, issues: list[SettingsIssue] | None
) -> str:
    """Read a retry count: a whole number, or 'infinite' (also spelled inf/infinity)."""
    if key not in section or section[key] is None:
        return "infinite"
    value = section[key]
    if isinstance(value, str) and value.strip().lower() in _INFINITE_SPELLINGS:
        return "infinite"
    number: float | None = None
    if not isinstance(value, bool):
        if isinstance(value, int):
            number = float(value)
        elif isinstance(value, str) and value.strip().isdigit():
            # isdigit() also passes "²", which is not a number: float() decides.
            try:
                number = float(value.strip())
            except ValueError:
                number = None
    if number is None or not 0 <= number <= MAX_RETRIES:
        _report(
            issues, path, f"expected 0-{MAX_RETRIES} or 'infinite', found {value!r}", "infinite"
        )
        return "infinite"
    return str(int(number))


def _plain_text(value: object) -> str | None:
    """A string that is safe to hand to a child process as a value, else None."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text.startswith("-") or _CONTROL_CHARS_RE.search(text):
        return None
    return text


def _choice(
    section: dict[str, Any],
    key: str,
    default: str,
    allowed: tuple[str, ...],
    path: str,
    issues: list[SettingsIssue] | None,
    *,
    allow_empty: bool = False,
) -> str:
    if key not in section or section[key] is None:
        return default
    value = section[key]
    if isinstance(value, str) and (value in allowed or (allow_empty and value == "")):
        return value
    _report(issues, path, f"expected one of {', '.join(allowed)}, found {value!r}", default)
    return default


def _optional_text(
    section: dict[str, Any],
    key: str,
    path: str,
    issues: list[SettingsIssue] | None,
    *,
    pattern: re.Pattern[str] | None = None,
    no_spaces: bool = False,
) -> str | None:
    """Read an optional argument value (a proxy, a rate limit); blank means unset."""
    if key not in section or section[key] is None:
        return None
    value = section[key]
    if isinstance(value, str) and not value.strip():
        return None
    if isinstance(value, int | float) and not isinstance(value, bool) and pattern is not None:
        value = str(int(value)) if float(value).is_integer() else None
    text = _plain_text(value)
    if text is not None and no_spaces and re.search(r"\s", text):
        text = None
    if text is not None and pattern is not None and not pattern.match(text):
        text = None
    if text is None:
        _report(issues, path, f"unusable value {section[key]!r}", "unset")
    return text


def _text(
    section: dict[str, Any],
    key: str,
    default: str,
    path: str,
    issues: list[SettingsIssue] | None,
) -> str:
    if key not in section or section[key] is None:
        return default
    text = _plain_text(section[key])
    if text is None:
        _report(issues, path, f"unusable value {section[key]!r}", default)
        return default
    return text


def _template(
    section: dict[str, Any],
    key: str,
    default: str,
    path: str,
    issues: list[SettingsIssue] | None,
    *,
    needs_id: bool = True,
) -> str:
    """Read an output template, refusing anything that could leave the target folder.

    A custom template without the content id is kept (it is the user's choice) but
    flagged, since two different videos with the same title would then collide.
    """
    if key not in section or section[key] is None:
        return default
    value = section[key]
    problem = None
    if not isinstance(value, str) or not value.strip():
        problem = "expected a non-empty template"
    elif _CONTROL_CHARS_RE.search(value):
        problem = "contains control characters"
    else:
        text = value.strip()
        parts = re.split(r"[\\/]", text)
        if (
            PurePosixPath(text).is_absolute()
            or PureWindowsPath(text).is_absolute()
            or PureWindowsPath(text).drive
            or text.startswith("~")
        ):
            problem = "must be relative to the download folder"
        elif ".." in parts:
            problem = "must not contain '..'"
        elif "%(ext)s" not in text:
            problem = "must contain %(ext)s"
    if problem is not None:
        _report(issues, path, f"{problem}, found {value!r}", default)
        return default
    text = str(value).strip()
    if needs_id and "%(id)s" not in text:
        _report(
            issues,
            path,
            "custom template has no %(id)s: videos with the same title would share one file",
        )
    return text


@dataclass
class DownloadSettings:
    """Settings for download behavior and performance.

    These settings control how yt-dlp handles downloads, including
    retry behavior, rate limiting, and parallel downloads.

    Attributes:
        concurrent_fragments: Number of fragments to download in parallel.
        sleep_interval: Minimum seconds to sleep between downloads.
        max_sleep_interval: Maximum seconds to sleep between downloads.
        retries: Number of retries for failed downloads ('infinite' or a number).
        fragment_retries: Number of retries for failed fragments.
        rate_limit: Download speed limit (e.g., '1M', '500K'), or None.
        proxy: HTTP/SOCKS proxy URL, or None. It applies to every yt-dlp call the
            app makes (downloads, listings, skip probes) and to the speed test.
        allow_external_config: Let yt-dlp also read the user's own yt-dlp config
            files. Off by default: the app's settings then decide every option,
            and a stray ``--skip-download`` or ``--extract-audio`` in someone's
            yt-dlp.conf cannot change what a download does.
        speed_test: Measure the connection speed before a playlist download, to
            turn the size estimate into a time estimate.
    """

    concurrent_fragments: int = 4
    sleep_interval: float = 1
    max_sleep_interval: float = 3
    retries: str = "infinite"
    fragment_retries: str = "infinite"
    rate_limit: str | None = None
    proxy: str | None = None
    allow_external_config: bool = False
    speed_test: bool = True

    def to_args(self) -> list[str]:
        """Convert settings to yt-dlp command-line arguments.

        There is deliberately no ``--ignore-errors``: it makes yt-dlp treat a failed
        post-processing step (a conversion, a merge, an embed) as success, and the
        item is then written to the download archive as done. What is wanted is the
        default, ``--no-abort-on-error``: a download error skips to the next playlist
        item, while a post-processing error leaves the item unarchived so the next
        run (or the compatibility profile's second stage) retries it. A fragment
        that stays unavailable after the retries fails the item instead of being
        skipped, which would leave a file with a hole in it.

        The proxy and the speed limit are not part of this: they belong to the network
        context (netctx.NetworkContext), which every call shares.

        Returns:
            List of command-line arguments.
        """
        max_sleep = max(self.max_sleep_interval, self.sleep_interval)
        args = [
            "--continue",
            "--no-abort-on-error",
            "--abort-on-unavailable-fragments",
            "--retries",
            self.retries,
            "--fragment-retries",
            self.fragment_retries,
            "--concurrent-fragments",
            str(self.concurrent_fragments),
            "--sleep-interval",
            _format_seconds(self.sleep_interval),
            "--max-sleep-interval",
            _format_seconds(max_sleep),
        ]
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

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], issues: list[SettingsIssue] | None = None
    ) -> DownloadSettings:
        """Create download settings, replacing unusable values with defaults."""
        d = cls()
        return cls(
            concurrent_fragments=int(
                _number(
                    data,
                    "concurrent_fragments",
                    d.concurrent_fragments,
                    "download.concurrent_fragments",
                    issues,
                    low=1,
                    high=64,
                    integer=True,
                )
            ),
            sleep_interval=_number(
                data, "sleep_interval", d.sleep_interval, "download.sleep_interval", issues
            ),
            max_sleep_interval=_number(
                data,
                "max_sleep_interval",
                d.max_sleep_interval,
                "download.max_sleep_interval",
                issues,
            ),
            retries=_retries(data, "retries", "download.retries", issues),
            fragment_retries=_retries(
                data, "fragment_retries", "download.fragment_retries", issues
            ),
            rate_limit=_optional_text(
                data, "rate_limit", "download.rate_limit", issues, pattern=_RATE_LIMIT_RE
            ),
            proxy=_optional_text(data, "proxy", "download.proxy", issues, no_spaces=True),
            allow_external_config=_bool(
                data,
                "allow_external_config",
                d.allow_external_config,
                "download.allow_external_config",
                issues,
            ),
            speed_test=_bool(data, "speed_test", d.speed_test, "download.speed_test", issues),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert download settings to a dictionary."""
        return {
            "concurrent_fragments": self.concurrent_fragments,
            "sleep_interval": self.sleep_interval,
            "max_sleep_interval": self.max_sleep_interval,
            "retries": self.retries,
            "fragment_retries": self.fragment_retries,
            "rate_limit": self.rate_limit,
            "proxy": self.proxy,
            "allow_external_config": self.allow_external_config,
            "speed_test": self.speed_test,
        }


@dataclass
class AudioSettings:
    """Settings for audio extraction and conversion.

    Attributes:
        audio_quality: Audio quality (0=best, 9=worst).
        audio_format: Target audio format (one of AUDIO_FORMATS).
        embed_thumbnail: Whether to embed thumbnail in audio files.
        embed_metadata: Whether to embed metadata in audio files.
        convert_thumbnails: Format to convert thumbnails to (jpg, png, webp), or "".
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

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], issues: list[SettingsIssue] | None = None
    ) -> AudioSettings:
        """Create audio settings, replacing unusable values with defaults."""
        d = cls()
        return cls(
            audio_quality=int(
                _number(
                    data,
                    "audio_quality",
                    d.audio_quality,
                    "audio.audio_quality",
                    issues,
                    low=0,
                    high=9,
                    integer=True,
                )
            ),
            audio_format=_choice(
                data, "audio_format", d.audio_format, AUDIO_FORMATS, "audio.audio_format", issues
            ),
            embed_thumbnail=_bool(
                data, "embed_thumbnail", d.embed_thumbnail, "audio.embed_thumbnail", issues
            ),
            embed_metadata=_bool(
                data, "embed_metadata", d.embed_metadata, "audio.embed_metadata", issues
            ),
            convert_thumbnails=_choice(
                data,
                "convert_thumbnails",
                d.convert_thumbnails,
                THUMBNAIL_FORMATS,
                "audio.convert_thumbnails",
                issues,
                allow_empty=True,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert audio settings to a dictionary."""
        return {
            "audio_quality": self.audio_quality,
            "audio_format": self.audio_format,
            "embed_thumbnail": self.embed_thumbnail,
            "embed_metadata": self.embed_metadata,
            "convert_thumbnails": self.convert_thumbnails,
        }


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

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], issues: list[SettingsIssue] | None = None
    ) -> VideoSettings:
        """Create video settings, replacing unusable values with defaults."""
        d = cls()
        return cls(
            embed_thumbnail=_bool(
                data, "embed_thumbnail", d.embed_thumbnail, "video.embed_thumbnail", issues
            ),
            embed_metadata=_bool(
                data, "embed_metadata", d.embed_metadata, "video.embed_metadata", issues
            ),
            embed_subtitles=_bool(
                data, "embed_subtitles", d.embed_subtitles, "video.embed_subtitles", issues
            ),
            subtitle_languages=_text(
                data, "subtitle_languages", d.subtitle_languages, "video.subtitle_languages", issues
            ),
            write_subtitles=_bool(
                data, "write_subtitles", d.write_subtitles, "video.write_subtitles", issues
            ),
            max_height=_max_height(data, "max_height", None, "video.max_height", issues),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert video settings to a dictionary."""
        return {
            "embed_thumbnail": self.embed_thumbnail,
            "embed_metadata": self.embed_metadata,
            "embed_subtitles": self.embed_subtitles,
            "subtitle_languages": self.subtitle_languages,
            "write_subtitles": self.write_subtitles,
            "max_height": self.max_height,
        }


def _max_height(
    section: dict[str, Any],
    key: str,
    default: int | None,
    path: str,
    issues: list[SettingsIssue] | None,
) -> int | None:
    """Return a usable resolution cap: an offered height, None (no cap) or the default."""
    if key not in section:
        return default
    value = section[key]
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value in ALLOWED_MAX_HEIGHTS:
        return value
    _report(
        issues, path, f"expected one of {ALLOWED_MAX_HEIGHTS} or null, found {value!r}", default
    )
    return default


def _as_max_height(value: Any, default: int | None) -> int | None:
    """Return a usable resolution cap: an offered height, None (no cap) or the default."""
    return _max_height({"v": value}, "v", default, "", None)


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
        """Convert the pacing and retry policy to yt-dlp arguments.

        ``--abort-on-unavailable-fragments`` makes a fragment that is still missing
        after the retries fail the item, instead of yt-dlp's default of skipping it and
        reporting success. The item then stays out of the download archive and the next
        run fetches it again; an archive with holes in its videos defeats its purpose.
        """
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
            "--abort-on-unavailable-fragments",
        ]

    def listing_args(self) -> list[str]:
        """Arguments for the playlist listing: only the wait between requests.

        The listing is a few requests, not a download, so the per-video waits and
        the retry policy of to_args do not apply.
        """
        return ["--sleep-requests", _format_seconds(self.sleep_requests)]

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], issues: list[SettingsIssue] | None = None
    ) -> ArchiveSettings:
        """Create archive settings, replacing unusable values with defaults."""
        d = cls()
        return cls(
            sleep_requests=_number(
                data,
                "sleep_requests",
                d.sleep_requests,
                "archive.sleep_requests",
                issues,
                strings=True,
            ),
            sleep_interval=_number(
                data,
                "sleep_interval",
                d.sleep_interval,
                "archive.sleep_interval",
                issues,
                strings=True,
            ),
            max_sleep_interval=_number(
                data,
                "max_sleep_interval",
                d.max_sleep_interval,
                "archive.max_sleep_interval",
                issues,
                strings=True,
            ),
            sleep_subtitles=_number(
                data,
                "sleep_subtitles",
                d.sleep_subtitles,
                "archive.sleep_subtitles",
                issues,
                strings=True,
            ),
            max_height=_max_height(data, "max_height", d.max_height, "archive.max_height", issues),
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

    Every default template carries ``%(id)s``: the title alone is not unique (two
    videos may share it, and sanitising can make different titles equal), and a
    second video that finds its target file already there is skipped by yt-dlp as a
    duplicate yet still recorded in the download archive. The playlist position is
    kept as a prefix, for ordering only.

    Attributes:
        single_video_template: Output template for single video downloads.
        single_audio_template: Output template for single audio downloads.
        playlist_video_template: Output template for playlist video downloads.
        playlist_audio_template: Output template for playlist audio downloads.
        archive_template: Output template for archive mode, relative to the
            videos folder's yt-dlp directory. Every video gets its own folder
            so its description, info JSON, thumbnail and subtitles stay together.
    """

    single_video_template: str = "%(title).150B [%(id)s].%(ext)s"
    single_audio_template: str = "%(title).150B [%(id)s].%(ext)s"
    playlist_video_template: str = (
        "%(playlist_title)s/%(playlist_index)03d - %(title).150B [%(id)s].%(ext)s"
    )
    playlist_audio_template: str = (
        "%(playlist_title)s/%(playlist_index)03d - %(title).150B [%(id)s].%(ext)s"
    )
    archive_template: str = (
        "%(channel)s/%(upload_date)s - %(title).80B [%(id)s]/%(title).80B.%(ext)s"
    )

    _KEYS = (
        "single_video_template",
        "single_audio_template",
        "playlist_video_template",
        "playlist_audio_template",
        "archive_template",
    )

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], issues: list[SettingsIssue] | None = None
    ) -> OutputSettings:
        """Create output settings; unusable templates fall back, custom ones are kept."""
        d = cls()
        values = {
            key: _template(
                data,
                key,
                getattr(d, key),
                f"output.{key}",
                issues,
                # The archive template names a folder [id]; a custom one is checked for it too.
                needs_id=True,
            )
            for key in cls._KEYS
        }
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        """Convert output settings to a dictionary."""
        return {key: getattr(self, key) for key in self._KEYS}


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
    def from_dict(
        cls, data: dict[str, Any], issues: list[SettingsIssue] | None = None
    ) -> AppSettings:
        """Create settings from a dictionary, tolerating anything a hand edit can produce.

        A section or field of the wrong type, a non-finite or out-of-range number, an
        unknown choice or a template that could leave the download folder never raises:
        the field falls back to its default and is reported by name.

        Args:
            data: Dictionary with settings values.
            issues: When given, receives one SettingsIssue per problem found.

        Returns:
            AppSettings instance with values from the dictionary.
        """
        return cls(
            download=DownloadSettings.from_dict(_section(data, "download", issues), issues),
            audio=AudioSettings.from_dict(_section(data, "audio", issues), issues),
            video=VideoSettings.from_dict(_section(data, "video", issues), issues),
            output=OutputSettings.from_dict(_section(data, "output", issues), issues),
            archive=ArchiveSettings.from_dict(_section(data, "archive", issues), issues),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert settings to a dictionary.

        Returns:
            Dictionary representation of all settings.
        """
        return {
            "download": self.download.to_dict(),
            "audio": self.audio.to_dict(),
            "video": self.video.to_dict(),
            "output": self.output.to_dict(),
            "archive": self.archive.to_dict(),
        }
