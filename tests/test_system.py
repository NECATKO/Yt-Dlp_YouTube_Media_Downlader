"""Tests for how yt-dlp is located and launched."""

import functools
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


class TestImpersonationAvailable:
    def test_reports_the_running_interpreter(self, monkeypatch) -> None:
        monkeypatch.setattr(system.shutil, "which", lambda _name: None)
        real_find_spec = system.importlib.util.find_spec
        monkeypatch.setattr(
            system.importlib.util,
            "find_spec",
            lambda name: None if name == "curl_cffi" else real_find_spec(name),
        )
        assert system.impersonation_available() is False

    def test_unknown_for_a_separate_executable(self, monkeypatch) -> None:
        monkeypatch.setattr(system.importlib.util, "find_spec", lambda _name: None)
        monkeypatch.setattr(system.shutil, "which", lambda _name: "/usr/bin/yt-dlp")
        assert system.impersonation_available() is None


def launcher(*command: str):
    """A stand-in for ytdlp_command, cached like it (the module fixture clears caches)."""
    return functools.lru_cache(maxsize=1)(lambda: command)


class TestYtDlpVersion:
    """Which yt-dlp is installed, and whether it is new enough (B06)."""

    def test_the_module_version_is_read_from_its_metadata(self, monkeypatch) -> None:
        monkeypatch.setattr(system, "ytdlp_command", launcher(sys.executable, "-m", "yt_dlp"))
        monkeypatch.setattr(system.importlib.metadata, "version", lambda _name: "2026.08.19")

        assert system.ytdlp_version() == "2026.08.19"

    def test_an_executable_is_asked_for_its_version(self, monkeypatch) -> None:
        class Done:
            returncode = 0
            stdout = "2025.03.21\n"

        monkeypatch.setattr(system, "ytdlp_command", launcher("/usr/bin/yt-dlp"))
        monkeypatch.setattr(system.subprocess, "run", lambda *_a, **_k: Done())

        assert system.ytdlp_version() == "2025.03.21"

    def test_an_unreadable_version_is_none(self, monkeypatch) -> None:
        def broken(*_a, **_k):
            raise OSError("cannot run")

        monkeypatch.setattr(system, "ytdlp_command", launcher("/usr/bin/yt-dlp"))
        monkeypatch.setattr(system.subprocess, "run", broken)

        assert system.ytdlp_version() is None

    @pytest.mark.parametrize(
        ("version", "old"),
        [
            ("2025.03.21", True),
            ("2025.11.11", True),
            ("2025.11.12", False),
            ("2025.11.12.234512", False),
            ("2026.08.19", False),
            (None, False),
            ("garbage", False),
        ],
    )
    def test_too_old_means_known_and_below_the_minimum(self, version, old: bool) -> None:
        assert system.ytdlp_too_old(version) is old
