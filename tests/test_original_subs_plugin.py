"""Tests for the bundled yt-dlp plugin that drops machine-translated subtitles."""

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from ytdlp_app.yt_dlp import PLUGINS_DIR

pytest.importorskip("yt_dlp")

PLUGIN_FILE = (
    PLUGINS_DIR
    / "original_subs"
    / "yt_dlp_plugins"
    / "postprocessor"
    / "ytdlp_app_original_subs.py"
)

BASE = "https://www.youtube.com/api/timedtext?v=izx6nkLpoOA&lang=en&kind=asr&fmt=vtt"


def _load_plugin() -> Any:
    spec = importlib.util.spec_from_file_location("ytdlp_app_original_subs", PLUGIN_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def plugin() -> Any:
    return _load_plugin()


class TestIsTranslation:
    def test_translation_has_tlang(self, plugin: Any) -> None:
        assert plugin.is_translation({"url": f"{BASE}&tlang=tr"})

    def test_original_auto_caption_is_kept(self, plugin: Any) -> None:
        assert not plugin.is_translation({"url": BASE})

    def test_entry_without_url_is_kept(self, plugin: Any) -> None:
        """Some extractors hand over subtitle data inline instead of a URL."""
        assert not plugin.is_translation({"data": "WEBVTT"})

    def test_tlang_in_another_parameter_value_does_not_count(self, plugin: Any) -> None:
        assert not plugin.is_translation({"url": f"{BASE}&name=tlang"})


class TestOriginalSubsOnlyPP:
    def test_drops_only_translations(self, plugin: Any) -> None:
        info = {
            "requested_subtitles": {
                "en": {"url": BASE, "ext": "vtt"},
                "en-orig": {"url": BASE, "ext": "vtt"},
                "tr": {"url": f"{BASE}&tlang=tr", "ext": "vtt"},
            }
        }
        files, result = plugin.OriginalSubsOnlyPP(None).run(info)
        assert files == []
        assert set(result["requested_subtitles"]) == {"en"}

    def test_orig_copy_of_the_same_track_is_dropped(self, plugin: Any) -> None:
        """YouTube lists the original auto caption twice, as "en" and "en-orig"."""
        info = {
            "requested_subtitles": {
                "en-orig": {"url": BASE, "ext": "vtt"},
                "en": {"url": BASE, "ext": "vtt"},
            }
        }
        _, result = plugin.OriginalSubsOnlyPP(None).run(info)
        assert list(result["requested_subtitles"]) == ["en"]

    def test_orig_is_kept_when_it_is_a_different_track(self, plugin: Any) -> None:
        """An uploaded "en" subtitle and the auto caption "en-orig" are both originals."""
        manual = "https://www.youtube.com/api/timedtext?v=x&lang=en&fmt=vtt"
        info = {
            "requested_subtitles": {
                "en-orig": {"url": BASE, "ext": "vtt"},
                "en": {"url": manual, "ext": "vtt"},
            }
        }
        _, result = plugin.OriginalSubsOnlyPP(None).run(info)
        assert set(result["requested_subtitles"]) == {"en", "en-orig"}

    def test_orig_is_kept_when_the_plain_code_was_not_requested(self, plugin: Any) -> None:
        info = {"requested_subtitles": {"en-orig": {"url": BASE, "ext": "vtt"}}}
        _, result = plugin.OriginalSubsOnlyPP(None).run(info)
        assert set(result["requested_subtitles"]) == {"en-orig"}

    def test_uploaded_turkish_subtitles_are_kept(self, plugin: Any) -> None:
        manual = "https://www.youtube.com/api/timedtext?v=x&lang=tr&fmt=vtt"
        info = {"requested_subtitles": {"tr": {"url": manual, "ext": "vtt"}}}
        _, result = plugin.OriginalSubsOnlyPP(None).run(info)
        assert set(result["requested_subtitles"]) == {"tr"}

    @pytest.mark.parametrize("requested", [None, {}])
    def test_nothing_requested(self, plugin: Any, requested: Any) -> None:
        info = {"requested_subtitles": requested}
        _, result = plugin.OriginalSubsOnlyPP(None).run(info)
        assert result["requested_subtitles"] == requested


def test_yt_dlp_finds_the_plugin_through_plugin_dirs(tmp_path: Path) -> None:
    """The exact flags archive mode passes must make yt-dlp load the plugin.

    Runs in a child process because yt-dlp registers plugins globally.
    """
    code = (
        "import sys, yt_dlp\n"
        "from yt_dlp.postprocessor import get_postprocessor\n"
        "from yt_dlp.plugins import load_all_plugins, plugin_dirs\n"
        "plugin_dirs.value = [sys.argv[1]]\n"
        "load_all_plugins()\n"
        "print(get_postprocessor('OriginalSubsOnly').__name__)\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code, str(PLUGINS_DIR)],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )
    assert out.stdout.strip() == "OriginalSubsOnlyPP"
