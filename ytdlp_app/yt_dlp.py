"""yt-dlp command builders for ytdlp_app.

This module provides functions to construct yt-dlp command-line arguments
for various download modes (MP4, MP3) and quality profiles.
"""

from __future__ import annotations

from pathlib import Path

from .models import Mode


def build_js_args(use_deno: bool = True) -> list[str]:
    """Build JavaScript runtime arguments for yt-dlp.

    These arguments configure how yt-dlp handles JavaScript challenges
    that some sites use for bot protection.

    Args:
        use_deno: Whether to use Deno as the JS runtime. If False,
            falls back to default behavior without explicit runtime.

    Returns:
        List of command-line arguments for JS configuration.
    """
    base = ["--remote-components", "ejs:github"]
    if not use_deno:
        return base
    return ["--js-runtime", "deno"] + base


def build_stability_args() -> list[str]:
    """Build stability and retry arguments for yt-dlp.

    These arguments ensure downloads are resilient to network issues
    and can resume after interruptions.

    Returns:
        List of command-line arguments for retry and stability settings.
    """
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


def build_common_args(
    *, output_template: str, archive_path: Path, playlist_flag: str, url: str
) -> list[str]:
    """Build common arguments used in all download commands.

    Args:
        output_template: The yt-dlp output filename template.
        archive_path: Path to the download archive file.
        playlist_flag: Either '--yes-playlist' or '--no-playlist'.
        url: The URL to download.

    Returns:
        List of common command-line arguments.
    """
    return [
        "-o",
        output_template,
        "--download-archive",
        str(archive_path),
        "--progress",
        playlist_flag,
        url,
    ]


def build_post_args(mode: Mode) -> list[str]:
    """Build post-processing arguments for yt-dlp.

    Configures metadata embedding and thumbnail handling based
    on the download mode.

    Args:
        mode: The download mode ('mp4' or 'mp3').

    Returns:
        List of post-processing command-line arguments.
    """
    post_args = ["--embed-metadata", "--add-metadata"]
    if mode == "mp3":
        post_args += ["--embed-thumbnail", "--convert-thumbnails", "jpg"]
    else:
        post_args += ["--embed-thumbnail"]
    return post_args


def build_mp4_compatibility_stage1_cmd(
    *,
    stability_args: list[str],
    js_args: list[str],
    post_args: list[str],
    common_args: list[str],
) -> list[str]:
    """Build Stage 1 command for MP4 compatibility mode.

    Stage 1 attempts to download with lossless merging when
    avc1 video and mp4a audio codecs are available.

    Args:
        stability_args: Retry and stability arguments.
        js_args: JavaScript runtime arguments.
        post_args: Post-processing arguments.
        common_args: Common arguments (output, archive, URL).

    Returns:
        Complete yt-dlp command for Stage 1.
    """
    return (
        [
            "yt-dlp",
            "-f",
            "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[vcodec^=avc1]",
            "--merge-output-format",
            "mp4",
        ]
        + stability_args
        + js_args
        + post_args
        + common_args
    )


def build_mp4_compatibility_stage2_cmd(
    *,
    stability_args: list[str],
    js_args: list[str],
    post_args: list[str],
    common_args: list[str],
) -> list[str]:
    """Build Stage 2 command for MP4 compatibility mode.

    Stage 2 downloads remaining items and recodes to MP4,
    used when native avc1+mp4a is not available.

    Args:
        stability_args: Retry and stability arguments.
        js_args: JavaScript runtime arguments.
        post_args: Post-processing arguments.
        common_args: Common arguments (output, archive, URL).

    Returns:
        Complete yt-dlp command for Stage 2.
    """
    return (
        ["yt-dlp", "-f", "bv*+ba/b", "--recode-video", "mp4"]
        + stability_args
        + js_args
        + post_args
        + common_args
    )


def build_mp4_quality_mkv_cmd(
    *,
    stability_args: list[str],
    js_args: list[str],
    post_args: list[str],
    common_args: list[str],
) -> list[str]:
    """Build command for MP4 quality mode with MKV container.

    Downloads best video + audio without transcoding, using MKV
    container which supports all codecs.

    Args:
        stability_args: Retry and stability arguments.
        js_args: JavaScript runtime arguments.
        post_args: Post-processing arguments.
        common_args: Common arguments (output, archive, URL).

    Returns:
        Complete yt-dlp command for quality MKV mode.
    """
    return (
        ["yt-dlp", "-f", "bv*+ba/b", "--merge-output-format", "mkv"]
        + stability_args
        + js_args
        + post_args
        + common_args
    )


def build_mp4_quality_mp4_remux_cmd(
    *,
    stability_args: list[str],
    js_args: list[str],
    post_args: list[str],
    common_args: list[str],
) -> list[str]:
    """Build command for MP4 quality mode with MP4 remux.

    Downloads best video + audio and remuxes to MP4 container.
    May fail if codecs are incompatible with MP4.

    Args:
        stability_args: Retry and stability arguments.
        js_args: JavaScript runtime arguments.
        post_args: Post-processing arguments.
        common_args: Common arguments (output, archive, URL).

    Returns:
        Complete yt-dlp command for quality MP4 remux mode.
    """
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
        + stability_args
        + js_args
        + post_args
        + common_args
    )


def build_mp3_cmd(
    *,
    stability_args: list[str],
    js_args: list[str],
    post_args: list[str],
    common_args: list[str],
) -> list[str]:
    """Build command for MP3 audio extraction.

    Downloads best available audio and converts to MP3 with
    highest quality settings.

    Args:
        stability_args: Retry and stability arguments.
        js_args: JavaScript runtime arguments.
        post_args: Post-processing arguments.
        common_args: Common arguments (output, archive, URL).

    Returns:
        Complete yt-dlp command for MP3 extraction.
    """
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
        + stability_args
        + js_args
        + post_args
        + common_args
    )
