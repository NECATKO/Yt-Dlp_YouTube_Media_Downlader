"""Helpers for tests that run the real yt-dlp and ffmpeg on generated media.

Nothing here touches the network: media is produced by ffmpeg into a temporary
folder and handed to yt-dlp as ``file://`` URLs through ``--load-info-json``, so
the whole extraction, download, merge, post-processing and archive path of the real
engine runs, offline and in a fraction of a second per item.
"""

from __future__ import annotations

import functools
import json
import os
import re
import shutil
import subprocess
from typing import TYPE_CHECKING, Any

import pytest

from ytdlp_app.yt_dlp import CommandBuilder

if TYPE_CHECKING:
    from pathlib import Path

HAS_TOOLS = all(shutil.which(tool) for tool in ("ffmpeg", "ffprobe"))

# One CI job sets this so that a missing ffmpeg, ffprobe or encoder fails the run instead
# of quietly skipping the tests that prove the real engine works.
REQUIRED = os.environ.get("YTDLP_REQUIRE_ENGINE") == "1"

requires_media_tools = pytest.mark.skipif(
    not HAS_TOOLS and not REQUIRED,
    reason="ffmpeg and ffprobe are needed to generate and inspect media",
)


@functools.cache
def has_encoder(name: str) -> bool:
    """Whether this ffmpeg build can encode with ``name`` (builds differ in what they include)."""
    try:
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return False
    return re.search(rf"^\s*[VAS][\w.]{{5}}\s+{re.escape(name)}\s", out, re.MULTILINE) is not None


def make_media(
    path: Path,
    *,
    vcodec: str | None = "libx264",
    acodec: str | None = "aac",
    seconds: float = 0.3,
) -> Path:
    """Generate a tiny clip with the given codecs (None leaves that stream out).

    Skips the test when this ffmpeg lacks an encoder, unless the run requires the engine.
    """
    for encoder in (vcodec, acodec):
        if encoder and not REQUIRED and not has_encoder(encoder):
            pytest.skip(f"this ffmpeg has no {encoder} encoder")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    if vcodec:
        cmd += ["-f", "lavfi", "-i", f"color=c=blue:s=64x64:d={seconds}:r=10"]
    if acodec:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
    if vcodec:
        cmd += ["-c:v", vcodec]
        if vcodec == "libx264":
            cmd += ["-pix_fmt", "yuv420p"]
    if acodec:
        cmd += ["-c:a", acodec]
    cmd += ["-shortest", str(path)]
    subprocess.run(cmd, check=True)
    return path


def probe(path: Path) -> dict[str, Any]:
    """ffprobe's JSON for a file: streams, format and chapters."""
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-show_chapters",
            "-print_format",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    data: dict[str, Any] = json.loads(out)
    return data


def codecs(path: Path) -> dict[str, str]:
    """{"video": codec, "audio": codec} of the first stream of each kind."""
    result: dict[str, str] = {}
    for stream in probe(path)["streams"]:
        result.setdefault(stream["codec_type"], stream["codec_name"])
    return result


def item(
    item_id: str,
    title: str,
    source: Path,
    *,
    vcodec: str = "avc1.640028",
    acodec: str = "mp4a.40.2",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """An info dict for one combined-stream file, as an extractor would return it."""
    info: dict[str, Any] = {
        "id": item_id,
        "title": title,
        "url": source.as_uri(),
        "ext": source.suffix.lstrip("."),
        "extractor": "synthetic",
        "extractor_key": "Synthetic",
        "webpage_url": f"https://example.invalid/{item_id}",
        "duration": 0.3,
        "height": 64,
        "width": 64,
        "vcodec": vcodec,
        "acodec": acodec,
        "protocol": "file",
    }
    info.update(extra or {})
    return info


def write_info(folder: Path, info: dict[str, Any]) -> Path:
    path = folder / f"{info['id']}.info.json"
    path.write_text(json.dumps(info), encoding="utf-8")
    return path


def write_playlist(folder: Path, entries: list[dict[str, Any]], title: str = "PL") -> Path:
    """An info file for a playlist whose entries are already resolved."""
    path = folder / "playlist.info.json"
    path.write_text(
        json.dumps(
            {
                "id": "PLsynthetic",
                "title": title,
                "_type": "playlist",
                "extractor": "synthetic",
                "extractor_key": "Synthetic",
                "entries": entries,
            }
        ),
        encoding="utf-8",
    )
    return path


def builder(folder: Path, settings: Any = None, *, is_playlist: bool = False) -> CommandBuilder:
    """A CommandBuilder writing into ``folder`` with pacing switched off."""
    from ytdlp_app.settings import AppSettings  # noqa: PLC0415

    settings = settings or AppSettings()
    settings.download.sleep_interval = settings.download.max_sleep_interval = 0
    settings.archive.sleep_requests = 0
    settings.archive.sleep_interval = settings.archive.max_sleep_interval = 0
    settings.archive.sleep_subtitles = 0
    return CommandBuilder(
        url="placeholder",
        output_template=str(folder / settings.output.single_video_template),
        # Beside the output folder, so the folder holds nothing but media.
        archive_path=folder.parent / "state" / "archive.txt",
        is_playlist=is_playlist,
        use_deno=False,
        settings=settings,
    )


def engine_program(cmd: list[str]) -> list[str]:
    """``cmd`` with "yt-dlp" replaced as the app replaces it, or by YTDLP_ENGINE_PYTHON.

    YTDLP_ENGINE_PYTHON names another interpreter whose yt-dlp runs the engine tests
    (an older release, to check the minimum version; a runtime with every extra).
    """
    from ytdlp_app.exec import resolve_program  # noqa: PLC0415

    program = resolve_program(cmd)
    other = os.environ.get("YTDLP_ENGINE_PYTHON")
    if other and program[1:3] == ["-m", "yt_dlp"]:
        program = [other, *program[1:]]
    return program


def engine_has_module(name: str) -> bool:
    """Whether the Python that runs yt-dlp in these tests can import ``name``."""
    program = engine_program(["yt-dlp"])
    if len(program) < 3 or program[1:3] != ["-m", "yt_dlp"]:
        return False
    found = subprocess.run([program[0], "-c", f"import {name}"], capture_output=True, check=False)
    return found.returncode == 0


def run_engine(
    cmd: list[str],
    info_file: Path,
    *,
    env: dict[str, str] | None = None,
    timeout: float = 120,
) -> subprocess.CompletedProcess[str]:
    """Run a built command on a local info file instead of a URL.

    The trailing URL is swapped for ``--load-info-json``; everything else is exactly
    what the app would run, including the launcher substitution of ``resolve_program``.
    """
    assert cmd[-1] == "placeholder"
    real = engine_program(
        [
            *cmd[:-1],
            "--enable-file-urls",
            # Without this yt-dlp strips a playlist's entries when it reads the file back.
            "--no-clean-info-json",
            "--load-info-json",
            str(info_file),
        ]
    )
    child_env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", **(env or {})}
    return subprocess.run(
        real,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=child_env,
        timeout=timeout,
        check=False,
        cwd=info_file.parent,
        stdin=subprocess.DEVNULL,
    )


def archive_ids(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.split()[-1] for line in path.read_text(encoding="utf-8").splitlines() if line]


def only(files: list[Path]) -> Path:
    assert len(files) == 1, files
    return files[0]


__all__ = [
    "archive_ids",
    "builder",
    "codecs",
    "item",
    "make_media",
    "only",
    "probe",
    "requires_media_tools",
    "run_engine",
    "write_info",
    "write_playlist",
]
