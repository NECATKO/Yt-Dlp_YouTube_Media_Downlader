from __future__ import annotations

from pathlib import Path

from .models import Mode


def build_js_args() -> list[str]:
    return ["--js-runtime", "deno", "--remote-components", "ejs:github"]


def build_stability_args() -> list[str]:
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
