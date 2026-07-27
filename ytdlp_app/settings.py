"""Advanced configuration settings for ytdlp_app.

This module provides extended configuration options that allow users
to customize download behavior, performance settings, and output formats.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
    """

    embed_thumbnail: bool = True
    embed_metadata: bool = True
    embed_subtitles: bool = False
    subtitle_languages: str = "en"
    write_subtitles: bool = False

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


@dataclass
class OutputSettings:
    """Settings for output file naming and organization.

    Attributes:
        single_video_template: Output template for single video downloads.
        single_audio_template: Output template for single audio downloads.
        playlist_video_template: Output template for playlist video downloads.
        playlist_audio_template: Output template for playlist audio downloads.
    """

    single_video_template: str = "%(title)s.%(ext)s"
    single_audio_template: str = "%(title)s.%(ext)s"
    playlist_video_template: str = "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"
    playlist_audio_template: str = "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"


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
    """

    download: DownloadSettings = field(default_factory=DownloadSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    video: VideoSettings = field(default_factory=VideoSettings)
    output: OutputSettings = field(default_factory=OutputSettings)

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
            )

        # Output settings
        if "output" in data:
            ou = data["output"]
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
            )

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
            },
            "output": {
                "single_video_template": self.output.single_video_template,
                "single_audio_template": self.output.single_audio_template,
                "playlist_video_template": self.output.playlist_video_template,
                "playlist_audio_template": self.output.playlist_audio_template,
            },
        }
