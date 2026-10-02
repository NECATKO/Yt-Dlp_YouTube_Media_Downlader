"""What the commands promise, checked against the real yt-dlp and ffmpeg.

Command-shape tests only prove that a flag is present. These run the engine on
generated media and look at the files and the download archive, which is where the
promises (one file per video, no false "done" records, H.264 + AAC, MKV) live.
"""

import http.server
import subprocess
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.engine import (
    archive_ids,
    builder,
    codecs,
    item,
    make_media,
    only,
    probe,
    requires_media_tools,
    run_engine,
    write_info,
    write_playlist,
)
from ytdlp_app.outcome import read_manifest
from ytdlp_app.settings import AppSettings

pytestmark = [requires_media_tools, pytest.mark.integration]


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[Path, Path]:
    src, out = tmp_path / "src", tmp_path / "out"
    src.mkdir()
    out.mkdir()
    return src, out


class TestFileNames:
    @pytest.mark.parametrize(
        ("first", "second"),
        [
            ("Same title", "Same title"),
            ("Trailing dot.", "Trailing dot"),
            ("Fresh: cut", "Fresh cut"),
        ],
    )
    def test_different_ids_with_the_same_title_are_two_files(
        self, workspace: tuple[Path, Path], first: str, second: str
    ) -> None:
        src, out = workspace
        media = make_media(src / "clip.mp4")
        b = builder(out)
        for ident, title in (("idAAAAAAAA1", first), ("idBBBBBBBB2", second)):
            info = write_info(src, item(ident, title, media))
            assert run_engine(b.build_mp4_quality_remux(), info).returncode == 0

        files = sorted(out.glob("*.mp4"))
        assert len(files) == 2, [f.name for f in files]
        assert {"idAAAAAAAA1", "idBBBBBBBB2"} == {
            i for i in ("idAAAAAAAA1", "idBBBBBBBB2") if any(i in f.name for f in files)
        }
        assert archive_ids(b.archive_path) == ["idAAAAAAAA1", "idBBBBBBBB2"]

    def test_the_same_id_twice_is_still_one_file(self, workspace: tuple[Path, Path]) -> None:
        src, out = workspace
        media = make_media(src / "clip.mp4")
        b = builder(out)
        info = write_info(src, item("idAAAAAAAA1", "Title", media))
        for _ in range(2):
            assert run_engine(b.build_mp4_quality_remux(), info).returncode == 0

        assert len(list(out.glob("*.mp4"))) == 1

    def test_playlist_position_is_kept_next_to_the_id(self, workspace: tuple[Path, Path]) -> None:
        src, out = workspace
        media = make_media(src / "clip.mp4")
        settings = AppSettings()
        b = builder(out, settings, is_playlist=True)
        b.output_template = str(out / settings.output.playlist_video_template)
        entries = [item("idFILLERFIL", "Filler", media), item("idAAAAAAAA1", "Title", media)]
        info = write_playlist(src, entries)
        assert run_engine(b.build_mp4_quality_remux(), info).returncode == 0

        name = only([p for p in (out / "PL").glob("*.mp4") if "idAAAAAAAA1" in p.name]).name
        assert name.startswith("002 - ")
        assert "[idAAAAAAAA1]" in name


class TestPostProcessingFailures:
    def failing(self, cmd: list[str]) -> list[str]:
        """The same command with a step after post-processing that always fails."""
        return [*cmd[:-1], "--exec", "after_move:exit 1", cmd[-1]]

    def test_a_failed_post_processing_step_is_not_recorded_as_done(
        self, workspace: tuple[Path, Path]
    ) -> None:
        src, out = workspace
        media = make_media(src / "clip.mp4")
        b = builder(out)
        info = write_info(src, item("idAAAAAAAA1", "Title", media))

        result = run_engine(self.failing(b.build_mp4_compatibility_stage1()), info)

        assert result.returncode != 0
        assert archive_ids(b.archive_path) == []

    def test_the_second_stage_really_reprocesses_the_item(
        self, workspace: tuple[Path, Path]
    ) -> None:
        src, out = workspace
        media = make_media(src / "clip.mp4")
        b = builder(out)
        info = write_info(src, item("idAAAAAAAA1", "Title", media))

        stage1 = run_engine(self.failing(b.build_mp4_compatibility_stage1()), info)
        stage2 = run_engine(b.build_mp4_compatibility_stage2(), info)

        assert stage1.returncode != 0
        assert stage2.returncode == 0
        assert "already been recorded in the archive" not in stage2.stdout
        assert archive_ids(b.archive_path) == ["idAAAAAAAA1"]
        assert codecs(only(list(out.glob("*.mp4")))) == {"video": "h264", "audio": "aac"}

    def test_playlist_download_errors_still_continue_with_the_next_item(
        self, workspace: tuple[Path, Path]
    ) -> None:
        """Dropping --ignore-errors must not turn one bad item into a stopped playlist."""
        src, out = workspace
        media = make_media(src / "clip.mp4")
        b = builder(out, is_playlist=True)
        # The default retries forever, which for a file that is simply gone never ends.
        b.settings.download.retries = b.settings.download.fragment_retries = "0"
        bad = item("idBADBADBAD", "Bad", media, extra={"url": (src / "gone.mp4").as_uri()})
        good = item("idGOODGOOD1", "Good", media)
        playlist = write_playlist(src, [bad, good])

        result = run_engine(b.build_mp4_quality_remux(), playlist)

        assert result.returncode != 0
        assert archive_ids(b.archive_path) == ["idGOODGOOD1"]


class TestCompatibilityCodecs:
    @pytest.mark.parametrize(
        ("vcodec", "acodec", "suffix"),
        [
            ("libaom-av1", "aac", ".mp4"),
            ("libvpx-vp9", "libopus", ".webm"),
            ("libx264", "libopus", ".mkv"),
            ("libx264", "aac", ".mkv"),
        ],
    )
    def test_the_result_is_h264_and_aac_in_mp4(
        self, workspace: tuple[Path, Path], vcodec: str, acodec: str, suffix: str
    ) -> None:
        src, out = workspace
        media = make_media(src / f"clip{suffix}", vcodec=vcodec, acodec=acodec)
        b = builder(out)
        info = write_info(src, item("idAAAAAAAA1", "Title", media))

        result = run_engine(b.build_mp4_compatibility_stage2(), info)

        assert result.returncode == 0, result.stdout + result.stderr
        final = only(list(out.iterdir()))
        assert final.suffix == ".mp4"
        assert codecs(final) == {"video": "h264", "audio": "aac"}
        assert probe(final)["format"]["format_name"].startswith("mov,mp4")

    def test_an_already_compatible_file_is_not_re_encoded(
        self, workspace: tuple[Path, Path]
    ) -> None:
        src, out = workspace
        media = make_media(src / "clip.mp4")
        b = builder(out)
        # The profile embeds metadata, which rewrites the container, so compare the
        # video stream itself: a re-encode would change its bytes, a copy does not.
        b.settings.video.embed_metadata = False
        b.settings.video.embed_thumbnail = False
        info = write_info(src, item("idAAAAAAAA1", "Title", media))

        assert run_engine(b.build_mp4_compatibility_stage2(), info).returncode == 0

        final = only(list(out.glob("*.mp4")))
        assert _video_payload(final) == _video_payload(media)

    def test_good_video_is_copied_when_only_the_audio_is_wrong(
        self, workspace: tuple[Path, Path]
    ) -> None:
        src, out = workspace
        media = make_media(src / "clip.mp4", vcodec="libx264", acodec="libopus")
        b = builder(out)
        b.settings.video.embed_metadata = False
        b.settings.video.embed_thumbnail = False
        info = write_info(src, item("idAAAAAAAA1", "Title", media))

        assert run_engine(b.build_mp4_compatibility_stage2(), info).returncode == 0

        final = only(list(out.glob("*.mp4")))
        assert codecs(final) == {"video": "h264", "audio": "aac"}
        assert _video_payload(final) == _video_payload(media)

    def test_metadata_survives_the_conversion(self, workspace: tuple[Path, Path]) -> None:
        src, out = workspace
        media = make_media(src / "clip.mp4", vcodec="libaom-av1")
        b = builder(out)
        info = write_info(src, item("idAAAAAAAA1", "A Title", media))

        assert run_engine(b.build_mp4_compatibility_stage2(), info).returncode == 0

        tags = probe(only(list(out.glob("*.mp4"))))["format"].get("tags", {})
        assert tags.get("title") == "A Title"

    def test_a_missing_ffmpeg_fails_the_item_instead_of_keeping_the_wrong_codec(
        self, workspace: tuple[Path, Path]
    ) -> None:
        src, out = workspace
        media = make_media(src / "clip.mp4", vcodec="libaom-av1")
        b = builder(out)
        info = write_info(src, item("idAAAAAAAA1", "Title", media))
        cmd = [*b.build_mp4_compatibility_stage2()]
        cmd[-1:-1] = ["--ffmpeg-location", str(src / "no-such-ffmpeg")]

        result = run_engine(cmd, info)

        assert result.returncode != 0
        assert archive_ids(b.archive_path) == []


def _video_payload(path: Path) -> str:
    """A hash of the video packets, independent of container and metadata."""
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0", "-c", "copy", "-f", "md5", "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


class TestMkv:
    def test_a_single_combined_stream_becomes_mkv(self, workspace: tuple[Path, Path]) -> None:
        src, out = workspace
        media = make_media(src / "clip.mp4")
        b = builder(out)
        info = write_info(src, item("idAAAAAAAA1", "Title", media))

        result = run_engine(b.build_mp4_quality_mkv(), info)

        assert result.returncode == 0, result.stdout
        assert [f.suffix for f in out.iterdir()] == [".mkv"]

    def test_separate_video_and_audio_streams_become_mkv(
        self, workspace: tuple[Path, Path]
    ) -> None:
        src, out = workspace
        video = make_media(src / "video.mp4", acodec=None)
        audio = make_media(src / "audio.m4a", vcodec=None)
        info_dict = item("idAAAAAAAA1", "Title", video)
        info_dict.pop("url")
        info_dict.pop("ext")
        info_dict["formats"] = [
            {
                "format_id": "v",
                "url": video.as_uri(),
                "ext": "mp4",
                "vcodec": "avc1.640028",
                "acodec": "none",
                "protocol": "file",
                "height": 64,
            },
            {
                "format_id": "a",
                "url": audio.as_uri(),
                "ext": "m4a",
                "vcodec": "none",
                "acodec": "mp4a.40.2",
                "protocol": "file",
            },
        ]
        info = write_info(src, info_dict)
        b = builder(out)

        result = run_engine(b.build_mp4_quality_mkv(), info)

        assert result.returncode == 0, result.stdout
        final = only(list(out.glob("*.mkv")))
        assert set(codecs(final)) == {"video", "audio"}

    def test_the_mp4_container_choice_still_gives_mp4(self, workspace: tuple[Path, Path]) -> None:
        src, out = workspace
        media = make_media(src / "clip.mp4")
        b = builder(out)
        info = write_info(src, item("idAAAAAAAA1", "Title", media))

        assert run_engine(b.build_mp4_quality_remux(), info).returncode == 0
        assert len(list(out.glob("*.mp4"))) == 1


class TestArchiveMode:
    def archive_item(self, src: Path) -> dict:
        media = make_media(src / "clip.mp4")
        thumb = src / "thumb.jpg"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=red:s=32x32",
                "-frames:v",
                "1",
                str(thumb),
            ],
            check=True,
        )
        sub = src / "sub.srt"
        sub.write_text("1\n00:00:00,000 --> 00:00:00,200\nhello\n", encoding="utf-8")
        return item(
            "idAAAAAAAA1",
            "Archived",
            media,
            extra={
                "channel": "Chan",
                "description": "About this video",
                "upload_date": "20260101",
                "thumbnail": thumb.as_uri(),
                "chapters": [
                    {"start_time": 0, "end_time": 0.15, "title": "One"},
                    {"start_time": 0.15, "end_time": 0.3, "title": "Two"},
                ],
                "subtitles": {"en": [{"url": sub.as_uri(), "ext": "srt"}]},
            },
        )

    def test_a_single_combined_stream_is_delivered_as_mkv_with_everything_kept(
        self, workspace: tuple[Path, Path]
    ) -> None:
        src, out = workspace
        settings = AppSettings()
        b = builder(out, settings)
        b.output_template = str(out / settings.output.archive_template)
        info = write_info(src, self.archive_item(src))

        result = run_engine(b.build_archive(), info)

        assert result.returncode == 0, result.stdout
        folder = only([p for p in out.rglob("*") if p.is_dir() and "[idAAAAAAAA1]" in p.name])
        names = sorted(p.suffix for p in folder.iterdir())
        assert ".mkv" in names
        assert ".mp4" not in names
        assert ".description" in names and ".json" in names
        assert ".jpg" in names or ".webp" in names or ".png" in names
        assert any(p.name.endswith(".en.srt") for p in folder.iterdir())
        movie = only(list(folder.glob("*.mkv")))
        data = probe(movie)
        assert data["format"]["tags"]["title"] == "Archived"
        assert len(data["chapters"]) == 2
        assert archive_ids(b.archive_path) == ["idAAAAAAAA1"]


class _Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args: object) -> None:
        pass


@pytest.fixture
def hls_server(tmp_path: Path) -> Iterator[tuple[str, Path]]:
    """A local HTTP server with a two-fragment HLS stream whose second fragment is missing."""
    root = tmp_path / "hls"
    root.mkdir()
    clip = make_media(tmp_path / "hls_clip.mp4")
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(clip),
            "-c",
            "copy",
            "-f",
            "mpegts",
            str(root / "good.ts"),
        ],
        check=True,
    )
    (root / "list.m3u8").write_text(
        "#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXT-X-MEDIA-SEQUENCE:0\n"
        "#EXTINF:0.3,\ngood.ts\n#EXTINF:0.3,\nmissing.ts\n#EXT-X-ENDLIST\n"
    )
    handler = lambda *a, **k: _Handler(*a, directory=str(root), **k)  # noqa: E731
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/list.m3u8", root
    finally:
        server.shutdown()
        server.server_close()


class TestMissingFragments:
    def test_a_missing_fragment_fails_the_item_and_it_is_not_archived(
        self, workspace: tuple[Path, Path], hls_server: tuple[str, Path]
    ) -> None:
        src, out = workspace
        url, _ = hls_server
        settings = AppSettings()
        b = builder(out, settings)
        b.output_template = str(out / settings.output.archive_template)
        hls = item(
            "idHLSHLSHLS",
            "Partial",
            src / "unused.mp4",
            extra={
                "url": url,
                "ext": "mp4",
                "protocol": "m3u8_native",
                "channel": "C",
                "upload_date": "20260101",
            },
        )
        info = write_info(src, hls)

        result = run_engine(b.build_archive(), info)

        assert result.returncode != 0, result.stdout
        # For the right reason: the fragment is missing, not the format unavailable.
        assert "404" in result.stdout + result.stderr
        assert archive_ids(b.archive_path) == []

    def test_a_later_run_retries_the_item_once_the_fragment_exists(
        self, workspace: tuple[Path, Path], hls_server: tuple[str, Path]
    ) -> None:
        src, out = workspace
        url, root = hls_server
        settings = AppSettings()
        b = builder(out, settings)
        b.output_template = str(out / settings.output.archive_template)
        hls = item(
            "idHLSHLSHLS",
            "Partial",
            src / "unused.mp4",
            extra={
                "url": url,
                "ext": "mp4",
                "protocol": "m3u8_native",
                "channel": "C",
                "upload_date": "20260101",
            },
        )
        info = write_info(src, hls)
        assert run_engine(b.build_archive(), info).returncode != 0

        (root / "missing.ts").write_bytes((root / "good.ts").read_bytes())
        result = run_engine(b.build_archive(), info)

        assert result.returncode == 0, result.stdout
        assert archive_ids(b.archive_path) == ["idHLSHLSHLS"]

    def test_the_regular_modes_do_not_skip_fragments_either(
        self, workspace: tuple[Path, Path], hls_server: tuple[str, Path]
    ) -> None:
        src, out = workspace
        url, _ = hls_server
        b = builder(out)
        b.settings.download.retries = b.settings.download.fragment_retries = "1"
        hls = item(
            "idHLSHLSHLS",
            "Partial",
            src / "unused.mp4",
            extra={"url": url, "ext": "mp4", "protocol": "m3u8_native"},
        )
        info = write_info(src, hls)

        result = run_engine(b.build_mp4_quality_remux(), info)

        assert result.returncode != 0
        assert archive_ids(b.archive_path) == []


class TestDownloadManifest:
    def test_a_finished_download_is_recorded_with_its_final_path(
        self, workspace: tuple[Path, Path]
    ) -> None:
        src, out = workspace
        media = make_media(src / "clip.mp4")
        b = builder(out)
        info = write_info(src, item("idAAAAAAAA1", "Title", media))

        assert run_engine(b.build_mp4_quality_mkv(), info).returncode == 0

        assert read_manifest(b.manifest_path) == {"idAAAAAAAA1": only(list(out.glob("*.mkv")))}

    def test_inside_the_program_folder_the_record_survives_moving_it(
        self, workspace: tuple[Path, Path], tmp_path: Path
    ) -> None:
        src, out = workspace
        media = make_media(src / "clip.mp4")
        b = builder(out)
        b.app_dir = tmp_path
        info = write_info(src, item("idAAAAAAAA1", "Title", media))

        assert run_engine(b.build_mp4_quality_mkv(), info).returncode == 0

        record = b.manifest_path.read_text(encoding="utf-8").splitlines()[1]
        assert not Path(record.split("\t")[1]).is_absolute()
        moved = tmp_path.parent / (tmp_path.name + "-moved")
        tmp_path.rename(moved)
        manifest = moved / b.manifest_path.relative_to(tmp_path)
        assert (
            read_manifest(manifest)["idAAAAAAAA1"].resolve()
            == only(list((moved / out.relative_to(tmp_path)).glob("*.mkv"))).resolve()
        )

    def test_an_item_whose_post_processing_failed_is_not_recorded(
        self, workspace: tuple[Path, Path]
    ) -> None:
        src, out = workspace
        media = make_media(src / "clip.mp4", vcodec="libaom-av1")
        b = builder(out)
        info = write_info(src, item("idAAAAAAAA1", "Title", media))
        cmd = [*b.build_mp4_compatibility_stage2()]
        cmd[-1:-1] = ["--ffmpeg-location", str(src / "no-such-ffmpeg")]

        assert run_engine(cmd, info).returncode != 0
        assert not b.manifest_path.exists()

    def test_a_path_with_a_semicolon_survives_the_argument_syntax(self, tmp_path: Path) -> None:
        src, out = tmp_path / "src", tmp_path / "out;odd %20 dir"
        src.mkdir()
        out.mkdir()
        media = make_media(src / "clip.mp4")
        b = builder(out)
        info = write_info(src, item("idAAAAAAAA1", "Title", media))

        assert run_engine(b.build_mp4_quality_remux(), info).returncode == 0
        assert list(read_manifest(b.manifest_path)) == ["idAAAAAAAA1"]


class TestConfigIsolation:
    @pytest.fixture
    def hostile_home(self, tmp_path: Path) -> dict[str, str]:
        """A user yt-dlp config that would turn every download into something else."""
        home = tmp_path / "home"
        (home / ".config" / "yt-dlp").mkdir(parents=True)
        (home / ".config" / "yt-dlp" / "config").write_text(
            "--skip-download\n--extract-audio\n--audio-format wav\n", encoding="utf-8"
        )
        return {"HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"), "APPDATA": str(home)}

    def test_the_apps_settings_decide_by_default(
        self, workspace: tuple[Path, Path], hostile_home: dict[str, str]
    ) -> None:
        src, out = workspace
        media = make_media(src / "clip.mp4")
        b = builder(out)
        info = write_info(src, item("idAAAAAAAA1", "Title", media))

        result = run_engine(b.build_mp4_quality_remux(), info, env=hostile_home)

        assert result.returncode == 0
        assert [f.suffix for f in out.glob("*.mp4")] == [".mp4"]
        assert not list(out.glob("*.wav"))

    def test_an_explicit_opt_in_lets_the_external_config_apply(
        self, workspace: tuple[Path, Path], hostile_home: dict[str, str]
    ) -> None:
        src, out = workspace
        media = make_media(src / "clip.mp4")
        settings = AppSettings()
        settings.download.allow_external_config = True
        b = builder(out, settings)
        info = write_info(src, item("idAAAAAAAA1", "Title", media))

        run_engine(b.build_mp4_quality_remux(), info, env=hostile_home)

        assert not list(out.glob("*.mp4"))


class TestOptionalPartsInArchiveMode:
    """A part the video does not have is fine; a part it has but that could not be saved is
    not: the item must not be recorded as done, so the next run fetches it again."""

    def run_archive(self, workspace: tuple[Path, Path], extra: dict, name: str = "idAAAAAAAA1"):
        src, out = workspace
        media = make_media(src / "clip.mp4")
        settings = AppSettings()
        b = builder(out, settings)
        b.output_template = str(out / settings.output.archive_template)
        b.settings.download.retries = "0"
        info = write_info(
            src,
            item(name, "T", media, extra={"channel": "C", "upload_date": "20260101", **extra}),
        )
        return b, run_engine(b.build_archive(), info), src

    def test_a_video_with_no_subtitles_thumbnail_or_description_is_complete(
        self, workspace: tuple[Path, Path]
    ) -> None:
        b, result, _ = self.run_archive(workspace, {})

        assert result.returncode == 0, result.stdout
        assert archive_ids(b.archive_path) == ["idAAAAAAAA1"]

    def test_a_subtitle_that_exists_but_cannot_be_downloaded_leaves_the_item_undone(
        self, workspace: tuple[Path, Path]
    ) -> None:
        src, _ = workspace
        b, result, _ = self.run_archive(
            workspace,
            {"subtitles": {"en": [{"url": (src / "missing.srt").as_uri(), "ext": "srt"}]}},
        )

        assert result.returncode != 0
        assert archive_ids(b.archive_path) == []

    def test_a_missing_automatic_caption_counts_the_same(
        self, workspace: tuple[Path, Path]
    ) -> None:
        src, _ = workspace
        b, result, _ = self.run_archive(
            workspace,
            {"automatic_captions": {"en": [{"url": (src / "missing.vtt").as_uri(), "ext": "vtt"}]}},
        )

        assert result.returncode != 0
        assert archive_ids(b.archive_path) == []

    def test_a_thumbnail_that_exists_but_cannot_be_downloaded_leaves_the_item_undone(
        self, workspace: tuple[Path, Path]
    ) -> None:
        src, _ = workspace
        b, result, _ = self.run_archive(workspace, {"thumbnail": (src / "missing.jpg").as_uri()})

        assert result.returncode != 0
        assert archive_ids(b.archive_path) == []

    def test_a_worse_thumbnail_is_enough_when_the_best_one_is_gone(
        self, workspace: tuple[Path, Path]
    ) -> None:
        """YouTube's best thumbnail often 404s; yt-dlp then uses the next, and so is complete."""
        src, _ = workspace
        good = src / "small.jpg"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=red:s=32x32",
                "-frames:v",
                "1",
                str(good),
            ],
            check=True,
        )
        b, result, _ = self.run_archive(
            workspace,
            {
                "thumbnails": [
                    {"url": good.as_uri(), "id": "1", "preference": 0},
                    {"url": (src / "best.jpg").as_uri(), "id": "2", "preference": 1},
                ]
            },
        )

        assert result.returncode == 0, result.stdout
        assert archive_ids(b.archive_path) == ["idAAAAAAAA1"]

    def test_a_later_run_completes_the_item_once_the_part_is_available(
        self, workspace: tuple[Path, Path]
    ) -> None:
        src, _out = workspace
        sub_url = src / "later.srt"
        b, first, _ = self.run_archive(
            workspace, {"subtitles": {"en": [{"url": sub_url.as_uri(), "ext": "srt"}]}}
        )
        assert first.returncode != 0
        sub_url.write_text("1\n00:00:00,000 --> 00:00:00,200\nhi\n", encoding="utf-8")

        second = run_engine(b.build_archive(), src / "idAAAAAAAA1.info.json")

        assert second.returncode == 0, second.stdout
        assert archive_ids(b.archive_path) == ["idAAAAAAAA1"]

    def test_the_failed_part_stops_the_video_from_being_downloaded_pointlessly(
        self, workspace: tuple[Path, Path]
    ) -> None:
        src, out = workspace
        _b, _result, _ = self.run_archive(
            workspace,
            {"subtitles": {"en": [{"url": (src / "missing.srt").as_uri(), "ext": "srt"}]}},
        )

        assert not list(out.rglob("*.mkv"))


class TestAudioMode:
    @pytest.mark.parametrize(
        ("fmt", "suffix", "codec"),
        [("mp3", ".mp3", "mp3"), ("opus", ".opus", "opus"), ("wav", ".wav", "pcm_s16le")],
    )
    def test_the_chosen_format_is_delivered_named_by_id_and_recorded(
        self, workspace: tuple[Path, Path], fmt: str, suffix: str, codec: str
    ) -> None:
        src, out = workspace
        media = make_media(src / "clip.mp4")
        settings = AppSettings()
        settings.audio.audio_format = fmt
        settings.audio.embed_thumbnail = False
        b = builder(out, settings)
        b.output_template = str(out / settings.output.single_audio_template)
        info = write_info(src, item("idAAAAAAAA1", "Song", media))

        result = run_engine(b.build_mp3(), info)

        assert result.returncode == 0, result.stdout
        final = only(list(out.iterdir()))
        assert final.name == f"Song [idAAAAAAAA1]{suffix}"
        assert codecs(final)["audio"] == codec
        assert list(read_manifest(b.manifest_path)) == ["idAAAAAAAA1"]
        assert archive_ids(b.archive_path) == ["idAAAAAAAA1"]

    def test_two_songs_with_one_title_are_two_files(self, workspace: tuple[Path, Path]) -> None:
        src, out = workspace
        media = make_media(src / "clip.mp4")
        settings = AppSettings()
        settings.audio.embed_thumbnail = False
        b = builder(out, settings)
        b.output_template = str(out / settings.output.single_audio_template)
        for ident in ("idAAAAAAAA1", "idBBBBBBBB2"):
            info = write_info(src, item(ident, "Same song", media))
            assert run_engine(b.build_mp3(), info).returncode == 0

        assert len(list(out.glob("*.mp3"))) == 2


class TestArchivePlaylistKeepsGoing:
    def test_an_incomplete_item_does_not_stop_the_items_after_it(
        self, workspace: tuple[Path, Path]
    ) -> None:
        src, out = workspace
        media = make_media(src / "clip.mp4")
        settings = AppSettings()
        b = builder(out, settings, is_playlist=True)
        b.output_template = str(out / settings.output.archive_template)
        b.settings.download.retries = "0"
        common = {"channel": "C", "upload_date": "20260101"}
        broken = item(
            "idBROKENSUB",
            "Broken",
            media,
            extra={
                **common,
                "subtitles": {"en": [{"url": (src / "missing.srt").as_uri(), "ext": "srt"}]},
            },
        )
        fine = item("idFINEFINE1", "Fine", media, extra=common)
        playlist = write_playlist(src, [broken, fine])

        result = run_engine(b.build_archive(), playlist)

        assert result.returncode != 0
        assert archive_ids(b.archive_path) == ["idFINEFINE1"]
