"""The decisions of the MP4 compatibility plugin, on ffprobe-shaped data (no ffmpeg needed)."""

import importlib.util
from pathlib import Path
from typing import Any

import pytest

from ytdlp_app.yt_dlp import PLUGINS_DIR

pytest.importorskip("yt_dlp")

BASE = PLUGINS_DIR / "mp4_compat" / "yt_dlp_plugins" / "postprocessor"


def load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, BASE / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def plugin() -> Any:
    return load("ytdlp_app_mp4_compat")


def probe(
    video: str | None = "h264", audio: str | None = "aac", fmt: str = "mov,mp4,m4a,3gp"
) -> dict:
    streams: list[dict[str, Any]] = []
    if video:
        streams.append({"codec_type": "video", "codec_name": video})
    if audio:
        streams.append({"codec_type": "audio", "codec_name": audio})
    return {"streams": streams, "format": {"format_name": fmt}}


NOTHING = {"video": False, "audio": False, "container": False}


class TestPlan:
    def test_h264_aac_mp4_needs_nothing(self, plugin: Any) -> None:
        assert plugin.plan_conversion(probe(), "a.mp4") == NOTHING
        assert plugin.meets_contract(probe(), "a.mp4")

    @pytest.mark.parametrize("codec", ["av1", "vp9", "hevc", "mpeg4"])
    def test_a_video_codec_other_than_h264_is_converted_even_inside_mp4(
        self, plugin: Any, codec: str
    ) -> None:
        plan = plugin.plan_conversion(probe(video=codec), "a.mp4")

        assert plan == {**NOTHING, "video": True}

    @pytest.mark.parametrize("codec", ["opus", "mp3", "vorbis", "ac3"])
    def test_an_audio_codec_other_than_aac_is_converted_and_video_kept(
        self, plugin: Any, codec: str
    ) -> None:
        assert plugin.plan_conversion(probe(audio=codec), "a.mp4") == {**NOTHING, "audio": True}

    @pytest.mark.parametrize(
        ("path", "fmt"), [("a.mkv", "matroska,webm"), ("a.webm", "matroska,webm")]
    )
    def test_another_container_is_remuxed(self, plugin: Any, path: str, fmt: str) -> None:
        plan = plugin.plan_conversion(probe(fmt=fmt), path)

        assert plan == {**NOTHING, "container": True}

    def test_an_mp4_name_on_a_matroska_file_is_not_trusted(self, plugin: Any) -> None:
        assert plugin.plan_conversion(probe(fmt="matroska,webm"), "a.mp4")["container"]

    def test_cover_art_is_not_a_video_stream(self, plugin: Any) -> None:
        data = probe()
        data["streams"].append(
            {"codec_type": "video", "codec_name": "mjpeg", "disposition": {"attached_pic": 1}}
        )

        assert plugin.plan_conversion(data, "a.mp4") == NOTHING

    def test_a_file_without_video_never_meets_the_contract(self, plugin: Any) -> None:
        assert not plugin.meets_contract(probe(video=None), "a.mp4")

    def test_a_file_without_audio_is_acceptable(self, plugin: Any) -> None:
        assert plugin.meets_contract(probe(audio=None), "a.mp4")


class TestFfmpegOptions:
    def test_copy_what_is_already_right(self, plugin: Any) -> None:
        options = plugin.ffmpeg_options({"video": False, "audio": True, "container": False})

        assert options[options.index("-c:v") + 1] == "copy"
        assert options[options.index("-c:a") + 1] == "aac"

    def test_encode_video_but_copy_good_audio(self, plugin: Any) -> None:
        options = plugin.ffmpeg_options({"video": True, "audio": False, "container": False})

        assert options[options.index("-c:v") + 1] == "libx264"
        assert options[options.index("-c:a") + 1] == "copy"
        assert options[options.index("-pix_fmt") + 1] == "yuv420p"

    def test_only_audio_and_video_streams_are_mapped(self, plugin: Any) -> None:
        options = plugin.ffmpeg_options({"video": True, "audio": True, "container": True})

        assert "-sn" in options and "-dn" in options
        assert "0:v" in options and "0:a?" in options


class TestLedger:
    def test_appends_one_line_per_finished_item(self, tmp_path: Path) -> None:
        module = _ledger_module()
        manifest = tmp_path / "state" / "a.files.tsv"
        pp = module.DownloadLedgerPP(None, str(manifest))

        pp.run({"id": "X1", "filepath": "/v/one.mkv"})
        pp.run({"id": "X2", "filepath": "/v/two.mkv"})

        assert manifest.read_text(encoding="utf-8").splitlines() == [
            "X1\t/v/one.mkv",
            "X2\t/v/two.mkv",
        ]

    def test_decodes_the_escaped_path(self, tmp_path: Path) -> None:
        module = _ledger_module()
        real = tmp_path / "odd;dir %20"
        encoded = str(real).replace("%", "%25").replace(";", "%3B")

        module.DownloadLedgerPP(None, encoded).run({"id": "X1", "filepath": "/v/one.mkv"})

        assert (real).exists()

    def test_an_unwritable_manifest_fails_the_item(self, tmp_path: Path) -> None:
        from yt_dlp.utils import PostProcessingError  # noqa: PLC0415

        module = _ledger_module()
        blocked = tmp_path / "file"
        blocked.write_text("not a directory")

        with pytest.raises(PostProcessingError):
            module.DownloadLedgerPP(None, str(blocked / "a.tsv")).run(
                {"id": "X1", "filepath": "/v/one.mkv"}
            )

    def test_items_without_a_path_are_ignored(self, tmp_path: Path) -> None:
        module = _ledger_module()
        manifest = tmp_path / "a.tsv"

        module.DownloadLedgerPP(None, str(manifest)).run({"id": "X1"})

        assert not manifest.exists()


def _ledger_module() -> Any:
    path = PLUGINS_DIR / "ledger" / "yt_dlp_plugins" / "postprocessor" / "ytdlp_app_ledger.py"
    spec = importlib.util.spec_from_file_location("ytdlp_app_ledger", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
