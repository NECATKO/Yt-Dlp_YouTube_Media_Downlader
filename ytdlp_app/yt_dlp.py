"""yt-dlp command builders for ytdlp_app.

This module provides the CommandBuilder class to construct yt-dlp command-line
arguments for various download modes (MP4, MP3, archive) and quality profiles.
"""

from __future__ import annotations

from pathlib import Path

from .models import DownloadMode
from .netctx import NetworkContext, js_runtime_args
from .settings import AppSettings

#: Archive mode keeps everything a channel publishes that could be lost with it:
#: the video (capped by the archive resolution limit, 1080p by default, to bound
#: disk use), its description, the raw metadata, the thumbnail, and both uploaded
#: and auto-generated subtitles. The format selector is built per run by
#: video_format(), because the cap can change.
ARCHIVE_CONTENT_ARGS = [
    "--merge-output-format",
    "mkv",
    # --merge-output-format only acts when separate streams are merged. A video that
    # arrives as one combined stream (a single mp4) would stay an mp4, so it is also
    # remuxed: a stream copy into MKV, no re-encode. Metadata, chapters, the thumbnail
    # and the subtitles are embedded or written after this step, on the MKV.
    "--remux-video",
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

#: Holds the yt-dlp plugins the app ships (see each plugin's docstring):
#: OriginalSubsOnly drops YouTube's machine-translated subtitles (archive mode),
#: Mp4Compat guarantees the compatibility profile's H.264 + AAC in MP4, and
#: DownloadLedger records where each finished item was written, and ArchiveComplete
#: (archive mode) refuses an item whose subtitles or thumbnail could not be saved.
PLUGINS_DIR = Path(__file__).parent / "plugins"

#: Suffix of the manifest kept beside a download archive: "<id>\t<final path>" lines.
MANIFEST_SUFFIX = ".files.tsv"


def plugin_dirs_args() -> list[str]:
    """Make yt-dlp load the bundled plugins."""
    return ["--plugin-dirs", str(PLUGINS_DIR)]


def original_subs_args() -> list[str]:
    """Build the arguments that restrict archive mode to original subtitles.

    OriginalSubsOnly runs at when=video: after the subtitles are selected and before
    any of them is downloaded.
    """
    return [*plugin_dirs_args(), "--use-postprocessor", "OriginalSubsOnly:when=video"]


def archive_complete_args() -> list[str]:
    """Arguments that fail an item whose subtitles or thumbnail could not be saved.

    One step notes what the video lists before anything is written (when=video), the other
    checks it once the parts were written and before the video is downloaded (when=before_dl).
    """
    return [
        "--use-postprocessor",
        "ArchiveComplete:when=video;stage=snapshot",
        "--use-postprocessor",
        "ArchiveComplete:when=before_dl;stage=check",
    ]


def mp4_compat_args() -> list[str]:
    """Arguments that make the finished file H.264 + AAC in MP4 (see Mp4Compat).

    when=post_process runs before the metadata, chapter, subtitle and thumbnail
    embedding, so those act on the final MP4.
    """
    return ["--use-postprocessor", "Mp4Compat:when=post_process"]


def _encode_option(value: Path) -> str:
    """Percent-encode ";" and "%": yt-dlp splits a post-processor option on ";"."""
    return str(value).replace("%", "%25").replace(";", "%3B")


def ledger_args(manifest: Path, root: Path | None = None) -> list[str]:
    """Arguments that append each finished item to a manifest (see DownloadLedger).

    yt-dlp splits the option on ";", so the paths are percent-encoded for ";" and "%".
    With ``root`` (the program folder) files inside it are recorded relative to the
    manifest, so moving the whole folder keeps the records valid.
    """
    value = f"DownloadLedger:when=after_move;path={_encode_option(manifest)}"
    if root is not None:
        value += f";root={_encode_option(root)}"
    return ["--use-postprocessor", value]


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
        app_dir: Path | None = None,
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
            app_dir: The program folder. Files downloaded inside it are recorded in the
                manifest relative to it, so the folder can be moved; None records
                absolute paths.
        """
        self.url = url
        self.output_template = output_template
        self.archive_path = archive_path
        self.is_playlist = is_playlist
        self.use_deno = use_deno
        self.app_dir = app_dir
        self.settings = settings if settings is not None else AppSettings()
        self.network = NetworkContext(self.settings, use_deno)
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
    def manifest_path(self) -> Path:
        """Where DownloadLedger records this archive's finished items."""
        return self.archive_path.with_name(self.archive_path.stem + MANIFEST_SUFFIX)

    @property
    def stability_args(self) -> list[str]:
        """Build the retry, pacing and error-handling arguments for yt-dlp."""
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

    def _assemble(
        self, selection: list[str], mode: DownloadMode, extra: list[str] | None = None
    ) -> list[str]:
        """Combine a format selection with the arguments every command shares.

        common_args must stay last: it ends with the URL, which yt-dlp reads
        positionally.
        """
        return [
            selection[0],
            *self.network.download_args(),
            *selection[1:],
            *self.stability_args,
            *self.build_post_args(mode),
            *plugin_dirs_args(),
            *(extra or []),
            *ledger_args(self.manifest_path, self.app_dir),
            *self.common_args,
        ]

    def build_mp4_compatibility_stage1(self) -> list[str]:
        """Build Stage 1 command for MP4 compatibility mode.

        Asks for an H.264 + AAC rendition, which merges into MP4 without re-encoding.
        Mp4Compat then only verifies it (and would still convert should the selector
        ever let something else through).
        """
        return self._assemble(
            [
                "yt-dlp",
                "-f",
                compat_stage1_format(self._cap(self.settings.video.max_height)),
                "--merge-output-format",
                "mp4",
            ],
            DownloadMode.VIDEO,
            mp4_compat_args(),
        )

    def build_mp4_compatibility_stage2(self) -> list[str]:
        """Build Stage 2 command for MP4 compatibility mode.

        Takes the best rendition whatever its codecs and has Mp4Compat make it H.264 +
        AAC in MP4. ``--recode-video mp4`` is not used: it judges by container, so an
        AV1 or VP9 file that already is an .mp4 would be reported as "already in target
        format" and kept.
        """
        return self._assemble(
            ["yt-dlp", "-f", video_format(self._cap(self.settings.video.max_height))],
            DownloadMode.VIDEO,
            mp4_compat_args(),
        )

    def build_mp4_quality_mkv(self) -> list[str]:
        """Build command for MP4 quality mode with MKV container.

        ``--merge-output-format mkv`` only applies when separate streams are merged;
        ``--remux-video mkv`` (a stream copy) covers a single combined stream.
        """
        return self._assemble(
            [
                "yt-dlp",
                "-f",
                video_format(self._cap(self.settings.video.max_height)),
                "--merge-output-format",
                "mkv",
                "--remux-video",
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
            *self.network.download_args(),
            "-f",
            video_format(self._cap(self.settings.archive.max_height)),
            *ARCHIVE_CONTENT_ARGS,
            *original_subs_args(),
            *archive_complete_args(),
            *ledger_args(self.manifest_path, self.app_dir),
            *self.settings.archive.to_args(),
            *self.common_args,
        ]

    def build_mp3(self) -> list[str]:
        """Build command for audio extraction.

        The extraction flags come from the audio settings via build_post_args,
        so the target format follows whatever the user configured.
        """
        return self._assemble(["yt-dlp", "-f", "bestaudio/best"], DownloadMode.AUDIO)
