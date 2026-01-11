"""yt-dlp command builders for ytdlp_app.

This module provides the CommandBuilder class to construct yt-dlp command-line
arguments for various download modes (MP4, MP3) and quality profiles.
"""

from __future__ import annotations

from pathlib import Path

from .models import DownloadMode


class CommandBuilder:
    """Builder for yt-dlp command-line arguments.

    Encapsulates the logic for constructing complex yt-dlp commands
    based on configuration and download modes.
    """

    def __init__(
        self,
        url: str,
        output_template: str,
        archive_path: Path,
        is_playlist: bool,
        use_deno: bool = True,
    ):
        """Initialize the CommandBuilder.

        Args:
            url: The URL to download.
            output_template: The yt-dlp output filename template.
            archive_path: Path to the download archive file.
            is_playlist: Whether the URL is a playlist.
            use_deno: Whether to use Deno as the JS runtime.
        """
        self.url = url
        self.output_template = output_template
        self.archive_path = archive_path
        self.is_playlist = is_playlist
        self.use_deno = use_deno

    @property
    def js_args(self) -> list[str]:
        """Build JavaScript runtime arguments for yt-dlp."""
        base = ["--remote-components", "ejs:github"]
        if not self.use_deno:
            return base
        return ["--js-runtime", "deno"] + base

    @property
    def stability_args(self) -> list[str]:
        """Build stability and retry arguments for yt-dlp."""
        return [
            "--continue",
            "--ignore-errors",
            "--retries",
            "infinite",
            "--fragment-retries",
            "infinite",
            "--concurrent-fragments",
            "4",
            "--sleep-interval",
            "1",
            "--max-sleep-interval",
            "3",
        ]

    @property
    def common_args(self) -> list[str]:
        """Build common arguments used in all download commands."""
        playlist_flag = "--yes-playlist" if self.is_playlist else "--no-playlist"
        return [
            "-o",
            self.output_template,
            "--download-archive",
            str(self.archive_path),
            "--progress",
            playlist_flag,
            self.url,
        ]

    def build_post_args(self, mode: DownloadMode) -> list[str]:
        """Build post-processing arguments for yt-dlp."""
        post_args = ["--embed-metadata", "--add-metadata"]
        if mode == DownloadMode.AUDIO:
            post_args += ["--embed-thumbnail", "--convert-thumbnails", "jpg"]
        else:
            post_args += ["--embed-thumbnail"]
        return post_args

    def build_mp4_compatibility_stage1(self) -> list[str]:
        """Build Stage 1 command for MP4 compatibility mode."""
        return (
            [
                "yt-dlp",
                "-f",
                "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[vcodec^=avc1]",
                "--merge-output-format",
                "mp4",
            ]
            + self.stability_args
            + self.js_args
            + self.build_post_args(DownloadMode.VIDEO)
            + self.common_args
        )

    def build_mp4_compatibility_stage2(self) -> list[str]:
        """Build Stage 2 command for MP4 compatibility mode."""
        return (
            ["yt-dlp", "-f", "bv*+ba/b", "--recode-video", "mp4"]
            + self.stability_args
            + self.js_args
            + self.build_post_args(DownloadMode.VIDEO)
            + self.common_args
        )

    def build_mp4_quality_mkv(self) -> list[str]:
        """Build command for MP4 quality mode with MKV container."""
        return (
            ["yt-dlp", "-f", "bv*+ba/b", "--merge-output-format", "mkv"]
            + self.stability_args
            + self.js_args
            + self.build_post_args(DownloadMode.VIDEO)
            + self.common_args
        )

    def build_mp4_quality_remux(self) -> list[str]:
        """Build command for MP4 quality mode with MP4 remux."""
        return (
            [
                "yt-dlp",
                "-f",
                "bv*+ba/b",
                "--merge-output-format",
                "mp4",
                "--remux-video",
                "mp4",
            ]
            + self.stability_args
            + self.js_args
            + self.build_post_args(DownloadMode.VIDEO)
            + self.common_args
        )

    def build_mp3(self) -> list[str]:
        """Build command for MP3 audio extraction."""
        return (
            [
                "yt-dlp",
                "-f",
                "bestaudio/best",
                "--extract-audio",
                "--audio-format",
                "mp3",
                "--audio-quality",
                "0",
            ]
            + self.stability_args
            + self.js_args
            + self.build_post_args(DownloadMode.AUDIO)
            + self.common_args
        )
