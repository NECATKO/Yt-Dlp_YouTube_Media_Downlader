"""yt-dlp command builders for ytdlp_app.

This module provides the CommandBuilder class to construct yt-dlp command-line
arguments for various download modes (MP4, MP3, archive) and quality profiles.
"""

from __future__ import annotations

from pathlib import Path

from .models import DownloadMode
from .settings import AppSettings

#: Archive mode keeps everything a channel publishes that could be lost with it:
#: the video (capped by the archive resolution limit, 1080p by default, to bound
#: disk use), its description, the raw metadata, the thumbnail, and both uploaded
#: and auto-generated subtitles. The format selector is built per run by
#: video_format(), because the cap can change.
ARCHIVE_CONTENT_ARGS = [
    "--merge-output-format",
    "mkv",
    "--write-description",
    "--write-info-json",
    "--write-thumbnail",
    "--write-subs",
    "--write-auto-subs",
    "--sub-langs",
    "tr.*,en.*",
    "--convert-subs",
    "srt",
    "--embed-metadata",
    "--embed-chapters",
]

#: Holds the yt-dlp plugin that drops YouTube's machine-translated subtitles.
#: See plugins/original_subs for why --sub-langs alone cannot exclude them.
PLUGINS_DIR = Path(__file__).parent / "plugins"


def original_subs_args() -> list[str]:
    """Build the arguments that restrict archive mode to original subtitles."""
    return [
        "--plugin-dirs",
        str(PLUGINS_DIR),
        "--use-postprocessor",
        "OriginalSubsOnly:when=video",
    ]


def _height_filter(max_height: int | None) -> str:
    return "" if max_height is None else f"[height<={max_height}]"


def video_format(max_height: int | None) -> str:
    """Build the video+audio format selector, capped at max_height (None = no cap).

    The cap is on both alternatives: without it on the "/b" fallback a video with
    only a combined stream above the cap would be downloaded anyway.
    """
    cap = _height_filter(max_height)
    return f"bv*{cap}+ba/b{cap}"


def compat_stage1_format(max_height: int | None) -> str:
    """Build the H.264 + AAC selector of the compatibility profile's first stage."""
    cap = _height_filter(max_height)
    return f"bestvideo[vcodec^=avc1]{cap}+bestaudio[acodec^=mp4a]/best[vcodec^=avc1]{cap}"


def js_runtime_args(use_deno: bool) -> list[str]:
    """Build JavaScript runtime arguments for yt-dlp.

    Standalone so lookups that run before a CommandBuilder exists (the archive
    mode channel lookup) can pass the same flags.
    """
    base = ["--remote-components", "ejs:github"]
    if not use_deno:
        return base
    return ["--js-runtime", "deno", *base]


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
        # The cap chosen for this download, once the user has been asked. Until
        # then each mode uses the default saved in the settings.
        self._max_height: int | None = None
        self._has_max_height = False

    def set_max_height(self, max_height: int | None) -> None:
        """Apply the resolution cap chosen for this download (None = no cap).

        Overrides the default saved in the settings for this builder only.
        """
        self._max_height = max_height
        self._has_max_height = True

    def _cap(self, saved: int | None) -> int | None:
        return self._max_height if self._has_max_height else saved

    @property
    def js_args(self) -> list[str]:
        """Build JavaScript runtime arguments for yt-dlp."""
        return js_runtime_args(self.use_deno)

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
                compat_stage1_format(self._cap(self.settings.video.max_height)),
                "--merge-output-format",
                "mp4",
            ],
            DownloadMode.VIDEO,
        )

    def build_mp4_compatibility_stage2(self) -> list[str]:
        """Build Stage 2 command for MP4 compatibility mode."""
        return self._assemble(
            [
                "yt-dlp",
                "-f",
                video_format(self._cap(self.settings.video.max_height)),
                "--recode-video",
                "mp4",
            ],
            DownloadMode.VIDEO,
        )

    def build_mp4_quality_mkv(self) -> list[str]:
        """Build command for MP4 quality mode with MKV container."""
        return self._assemble(
            [
                "yt-dlp",
                "-f",
                video_format(self._cap(self.settings.video.max_height)),
                "--merge-output-format",
                "mkv",
            ],
            DownloadMode.VIDEO,
        )

    def build_mp4_quality_remux(self) -> list[str]:
        """Build command for MP4 quality mode with MP4 remux."""
        return self._assemble(
            [
                "yt-dlp",
                "-f",
                video_format(self._cap(self.settings.video.max_height)),
                "--merge-output-format",
                "mp4",
                "--remux-video",
                "mp4",
            ],
            DownloadMode.VIDEO,
        )

    def build_archive(self) -> list[str]:
        """Build the archive-mode command.

        This deliberately does not go through _assemble: the regular stability
        arguments retry forever, use short waits and add --ignore-errors, all of
        which work against archiving a whole channel without being rate limited.
        Without --ignore-errors an item whose subtitles or thumbnail fail is not
        recorded in the download archive, so the next run retries it instead of
        silently keeping an incomplete copy. The rate limit and proxy still apply.
        """
        return [
            "yt-dlp",
            "-f",
            video_format(self._cap(self.settings.archive.max_height)),
            *ARCHIVE_CONTENT_ARGS,
            *original_subs_args(),
            *self.settings.archive.to_args(),
            *self.settings.download.network_args(),
            *self.js_args,
            *self.common_args,
        ]

    def build_mp3(self) -> list[str]:
        """Build command for audio extraction.

        The extraction flags come from the audio settings via build_post_args,
        so the target format follows whatever the user configured.
        """
        return self._assemble(["yt-dlp", "-f", "bestaudio/best"], DownloadMode.AUDIO)
