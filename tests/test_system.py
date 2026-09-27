"""Tests for how yt-dlp is located and launched."""

import sys

import pytest

from ytdlp_app import exec as exec_module
from ytdlp_app import system
from ytdlp_app.exec import resolve_program


@pytest.fixture(autouse=True)
def _fresh_cache():
    system.refresh_tool_cache()
    yield
    system.refresh_tool_cache()


def test_prefers_the_yt_dlp_of_the_running_interpreter(monkeypatch) -> None:
    """The regression: the launchers never put .venv/runtime on PATH, so a
    PATH lookup missed the yt-dlp installed right next to the app."""
    monkeypatch.setattr(system.shutil, "which", lambda _name: None)
    assert system.ytdlp_command() == (sys.executable, "-m", "yt_dlp")
    assert system.yt_dlp_available() is True


def test_falls_back_to_path(monkeypatch) -> None:
    monkeypatch.setattr(system.importlib.util, "find_spec", lambda _name: None)
    monkeypatch.setattr(system.shutil, "which", lambda _name: "/usr/bin/yt-dlp")
    assert system.ytdlp_command() == ("/usr/bin/yt-dlp",)


def test_reports_missing(monkeypatch) -> None:
    monkeypatch.setattr(system.importlib.util, "find_spec", lambda _name: None)
    monkeypatch.setattr(system.shutil, "which", lambda _name: None)
    assert system.yt_dlp_available() is False


class TestResolveProgram:
    def test_expands_the_logical_name(self, monkeypatch) -> None:
        monkeypatch.setattr(exec_module, "ytdlp_command", lambda: ("py", "-m", "yt_dlp"))
        assert resolve_program(["yt-dlp", "--version"]) == ["py", "-m", "yt_dlp", "--version"]

    def test_leaves_other_programs_alone(self) -> None:
        assert resolve_program(["ffmpeg", "-version"]) == ["ffmpeg", "-version"]

    def test_leaves_the_command_alone_when_yt_dlp_is_missing(self, monkeypatch) -> None:
        monkeypatch.setattr(exec_module, "ytdlp_command", lambda: None)
        assert resolve_program(["yt-dlp", "-U"]) == ["yt-dlp", "-U"]

    def test_run_capture_really_launches_it(self) -> None:
        """End to end, with the yt-dlp installed in the test interpreter."""
        rc, out, _err = exec_module.run_capture(["yt-dlp", "--version"])
        assert rc == 0
        assert out.strip()
