"""Tests for application data-directory resolution."""

from pathlib import Path

import pytest

from ytdlp_app import app


def test_portable_launcher_keeps_state_beside_script(monkeypatch, tmp_path: Path) -> None:
    launcher = tmp_path / "downloader.py"
    monkeypatch.setattr(app.sys, "argv", [str(launcher)])

    assert app._resolve_app_dir() == tmp_path


def test_linux_console_script_uses_xdg_data_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(app.sys, "argv", ["/venv/bin/ytdlp-downloader"])
    monkeypatch.setattr(app.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    assert app._resolve_app_dir() == tmp_path / "ytdlp-downloader"


def test_windows_console_script_uses_local_app_data(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(app.sys, "argv", [r"C:\\venv\\Scripts\\ytdlp-downloader.exe"])
    monkeypatch.setattr(app.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert app._resolve_app_dir() == tmp_path / "ytdlp-downloader"


def test_macos_console_script_uses_application_support(monkeypatch) -> None:
    monkeypatch.setattr(app.sys, "argv", ["/venv/bin/ytdlp-downloader"])
    monkeypatch.setattr(app.sys, "platform", "darwin")

    assert app._resolve_app_dir() == (
        Path.home() / "Library" / "Application Support" / "ytdlp-downloader"
    )


class _StopAfterSetup(BaseException):
    """Escapes run()'s catch-all handler, which would otherwise log a crash."""


def _run_until_config(monkeypatch, argv0: str) -> list[Path]:
    """Run app.run() up to the first config read, recording environment setup."""
    configured: list[Path] = []
    monkeypatch.setattr(app.sys, "argv", [argv0])
    monkeypatch.setattr("ytdlp_app.portable.configure_environment", configured.append)

    def stop(_config_file: Path) -> dict:
        raise _StopAfterSetup

    monkeypatch.setattr(app, "load_config", stop)
    with pytest.raises(_StopAfterSetup):
        app.run()
    return configured


def test_portable_launch_configures_the_portable_environment(monkeypatch, tmp_path: Path) -> None:
    configured = _run_until_config(monkeypatch, str(tmp_path / "downloader.py"))
    assert configured == [tmp_path]


def test_installed_launch_leaves_the_environment_alone(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    configured = _run_until_config(monkeypatch, "/venv/bin/ytdlp-downloader")
    assert configured == []
