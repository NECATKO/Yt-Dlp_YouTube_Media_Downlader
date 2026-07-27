"""yt-dlp command builders for ytdlp_app.

This module provides the CommandBuilder class to construct yt-dlp command-line
arguments for various download modes (MP4, MP3) and quality profiles.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import DownloadMode
from .settings import AppSettings

if TYPE_CHECKING:
    from pathlib import Path


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
        settings: AppSettings | None = None,
    ) -> None:
        """Initialize the CommandBuilder.

        Args:
            url: The URL to download.
            output_template: The yt-dlp output filename template.
            archive_path: Path to the download archive file.
            is_playlist: Whether the URL is a playlist.
            use_deno: Whether to use Deno as the JS runtime.
            settings: User settings driving retry, rate limit, proxy, audio
                format and subtitle behavior. Defaults are used when omitted.
        """
        self.url = url
        self.output_template = output_template
        self.archive_path = archive_path
        self.is_playlist = is_playlist
        self.use_deno = use_deno
        self.settings = settings if settings is not None else AppSettings()

    @property
    def js_args(self) -> list[str]:
        """Build JavaScript runtime arguments for yt-dlp."""
        base = ["--remote-components", "ejs:github"]
        if not self.use_deno:
            return base
        return ["--js-runtime", "deno", *base]

    @property
    def stability_args(self) -> list[str]:
        """Build stability and retry arguments for yt-dlp.

        Also carries the rate limit and proxy, which are off by default.
        """
        return self.settings.download.to_args()

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
        """Build post-processing arguments for yt-dlp.

        For audio this also carries the extraction flags (--extract-audio and
        the target format), so build_mp3 only has to pick the source stream.
        """
        if mode == DownloadMode.AUDIO:
            return self.settings.audio.to_args()
        return self.settings.video.to_args()

    def _assemble(self, selection: list[str], mode: DownloadMode) -> list[str]:
        """Combine a format selection with the arguments every command shares.

        common_args must stay last: it ends with the URL, which yt-dlp reads
        positionally.
        """
        return [
            *selection,
            *self.stability_args,
            *self.js_args,
            *self.build_post_args(mode),
            *self.common_args,
        ]

    def build_mp4_compatibility_stage1(self) -> list[str]:
        """Build Stage 1 command for MP4 compatibility mode."""
        return self._assemble(
            [
                "yt-dlp",
                "-f",
                "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[vcodec^=avc1]",
                "--merge-output-format",
                "mp4",
            ],
            DownloadMode.VIDEO,
        )

    def build_mp4_compatibility_stage2(self) -> list[str]:
        """Build Stage 2 command for MP4 compatibility mode."""
        return self._assemble(
            ["yt-dlp", "-f", "bv*+ba/b", "--recode-video", "mp4"],
            DownloadMode.VIDEO,
        )

    def build_mp4_quality_mkv(self) -> list[str]:
        """Build command for MP4 quality mode with MKV container."""
        return self._assemble(
            ["yt-dlp", "-f", "bv*+ba/b", "--merge-output-format", "mkv"],
            DownloadMode.VIDEO,
        )

    def build_mp4_quality_remux(self) -> list[str]:
        """Build command for MP4 quality mode with MP4 remux."""
        return self._assemble(
            [
                "yt-dlp",
                "-f",
                "bv*+ba/b",
                "--merge-output-format",
                "mp4",
                "--remux-video",
                "mp4",
            ],
            DownloadMode.VIDEO,
        )

    def build_mp3(self) -> list[str]:
        """Build command for audio extraction.

        The extraction flags come from the audio settings via build_post_args,
        so the target format follows whatever the user configured.
        """
        return self._assemble(["yt-dlp", "-f", "bestaudio/best"], DownloadMode.AUDIO)
