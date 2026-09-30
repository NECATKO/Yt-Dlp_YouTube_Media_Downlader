"""The decisions of the archive completeness plugin, without running yt-dlp."""

import importlib.util
from pathlib import Path
from typing import Any

import pytest

from ytdlp_app.yt_dlp import PLUGINS_DIR

pytest.importorskip("yt_dlp")

FILE = PLUGINS_DIR / "complete" / "yt_dlp_plugins" / "postprocessor" / "ytdlp_app_complete.py"


@pytest.fixture(scope="module")
def plugin() -> Any:
    spec = importlib.util.spec_from_file_location("ytdlp_app_complete", FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def touch(path: Path) -> str:
    path.write_bytes(b"x")
    return str(path)


class TestMissingParts:
    def test_nothing_requested_nothing_missing(self, plugin: Any) -> None:
        assert plugin.missing_parts({}, thumbnails_listed=0) == []

    def test_a_saved_subtitle_is_fine(self, plugin: Any, tmp_path: Path) -> None:
        info = {"requested_subtitles": {"en": {"filepath": touch(tmp_path / "a.srt")}}}

        assert plugin.missing_parts(info, thumbnails_listed=0) == []

    def test_a_subtitle_whose_file_is_not_there_is_missing(
        self, plugin: Any, tmp_path: Path
    ) -> None:
        info = {
            "requested_subtitles": {
                "en": {"filepath": touch(tmp_path / "a.srt")},
                "tr": {"filepath": str(tmp_path / "gone.srt")},
                "de": {},
            }
        }

        assert plugin.missing_parts(info, thumbnails_listed=0) == ["subtitle de", "subtitle tr"]

    def test_listed_thumbnails_none_of_which_arrived_are_missing(self, plugin: Any) -> None:
        # yt-dlp drops a thumbnail that failed from the list, so only the count noted
        # earlier still says there was one.
        assert plugin.missing_parts({"thumbnails": []}, thumbnails_listed=3) == ["thumbnail"]

    def test_one_saved_thumbnail_is_enough(self, plugin: Any, tmp_path: Path) -> None:
        info = {"thumbnails": [{"filepath": touch(tmp_path / "t.jpg")}]}

        assert plugin.missing_parts(info, thumbnails_listed=3) == []

    def test_a_video_that_lists_no_thumbnail_needs_none(self, plugin: Any) -> None:
        assert plugin.missing_parts({"thumbnails": []}, thumbnails_listed=0) == []
