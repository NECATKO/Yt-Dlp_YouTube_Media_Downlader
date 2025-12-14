from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

Mode = Literal["mp4", "mp3"]


class CaptureRunner(Protocol):
    def __call__(self, cmd: list[str]) -> tuple[int, str, str]: ...


@dataclass(frozen=True, slots=True)
class AppPaths:
    app_dir: Path
    config_file: Path
    logs_dir: Path
    archives_dir: Path


@dataclass(frozen=True, slots=True)
class UserConfig:
    app: str
    videos_dir: Path
    music_dir: Path
    saved_at: str | None = None


@dataclass(frozen=True, slots=True)
class PlaylistEntry:
    playlist_index: int
    id: str
    title: str
    watch_url: str


@dataclass(frozen=True, slots=True)
class DownloadPlan:
    url: str
    mode: Mode
    is_playlist: bool
    playlist_id: str | None
    mp4_profile: int | None
    remux_container: int | None
    base_dir: Path
    output_template: str
    archive_path: Path
    log_path: Path
    playlist_flag: str
    js_args: list[str]
    stability_args: list[str]
    post_args: list[str]
    common_args: list[str]
