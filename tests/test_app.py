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


class TestStartupResilience:
    """A hand-edited config.json must never stop the app from starting."""

    def prepare(self, monkeypatch, tmp_path: Path, config: object) -> Path:
        import json  # noqa: PLC0415

        data_dir = tmp_path / "data" / "ytdlp-downloader"
        data_dir.mkdir(parents=True)
        (data_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
        monkeypatch.setattr(app.sys, "argv", ["/venv/bin/ytdlp-downloader"])
        monkeypatch.setattr(app.sys, "platform", "linux")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.setattr(app.Path, "home", classmethod(lambda _cls: tmp_path / "home"))
        return data_dir

    def run_quietly(self, monkeypatch, answers: list[str]) -> int:
        replies = iter(answers)
        monkeypatch.setattr("builtins.input", lambda _prompt="": next(replies))
        return app.run()

    def test_unusable_sections_are_reported_by_name_and_the_app_starts(
        self, monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self.prepare(
            monkeypatch,
            tmp_path,
            {
                "language": "en",
                "videos_dir": str(tmp_path / "V"),
                "music_dir": str(tmp_path / "M"),
                "settings": {
                    "audio": None,
                    "download": [],
                    "video": "bad",
                    "output": False,
                    "archive": {"sleep_interval": "inf"},
                },
            },
        )

        code = self.run_quietly(monkeypatch, [""])  # blank URL: leave

        out = capsys.readouterr().out
        assert code == 0
        for name in ("audio", "download", "video", "output", "archive.sleep_interval"):
            assert name in out

    @pytest.mark.parametrize("bad", [5, [], {"x": 1}, True, "bad\x00path"])
    def test_a_folder_setting_of_the_wrong_type_is_asked_again_not_a_crash(
        self, monkeypatch, tmp_path: Path, capsys, bad: object
    ) -> None:
        self.prepare(
            monkeypatch,
            tmp_path,
            {"language": "en", "videos_dir": bad, "music_dir": str(tmp_path / "M")},
        )

        code = self.run_quietly(monkeypatch, [str(tmp_path / "V2"), "", ""])

        assert code == 0
        assert "videos_dir" in capsys.readouterr().out
        assert (tmp_path / "V2").is_dir()

    def test_a_config_that_is_not_json_is_kept_aside_and_the_app_starts(
        self, monkeypatch, tmp_path: Path, capsys
    ) -> None:
        data_dir = self.prepare(monkeypatch, tmp_path, {})
        (data_dir / "config.json").write_text("{not json", encoding="utf-8")

        code = self.run_quietly(monkeypatch, ["1", str(tmp_path / "V"), str(tmp_path / "M"), ""])

        assert code == 0
        assert list(data_dir.glob("config.json.corrupt*"))

    def test_an_old_config_is_migrated_in_memory_and_the_file_left_alone_until_a_save(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        import json  # noqa: PLC0415

        from ytdlp_app.settings import LEGACY_TEMPLATES  # noqa: PLC0415

        old = {
            "language": "en",
            "videos_dir": str(tmp_path / "V"),
            "music_dir": str(tmp_path / "M"),
            "settings": {"output": dict(LEGACY_TEMPLATES)},
        }
        data_dir = self.prepare(monkeypatch, tmp_path, old)
        before = (data_dir / "config.json").read_text(encoding="utf-8")

        self.run_quietly(monkeypatch, [""])

        assert (data_dir / "config.json").read_text(encoding="utf-8") == before
        assert json.loads(before)["settings"]["output"] == dict(LEGACY_TEMPLATES)


class TestAuditCommand:
    def test_the_audit_subcommand_needs_no_prompts_and_changes_nothing(
        self, monkeypatch, tmp_path: Path, capsys
    ) -> None:
        import json  # noqa: PLC0415

        data_dir = tmp_path / "data" / "ytdlp-downloader"
        (data_dir / "archives").mkdir(parents=True)
        (data_dir / "archives" / "a.txt").write_text("youtube gone\n", encoding="utf-8")
        (data_dir / "archives" / "a.files.tsv").write_text(
            f"gone\t{tmp_path / 'missing.mp4'}\n", encoding="utf-8"
        )
        (data_dir / "config.json").write_text(
            json.dumps(
                {
                    "language": "en",
                    "videos_dir": str(tmp_path / "V"),
                    "music_dir": str(tmp_path / "M"),
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(app.sys, "argv", ["/venv/bin/ytdlp-downloader", "audit"])
        monkeypatch.setattr(app.sys, "platform", "linux")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
        monkeypatch.setattr(
            "builtins.input", lambda _p="": (_ for _ in ()).throw(AssertionError("no prompts"))
        )

        code = app.run()

        out = capsys.readouterr().out
        assert code == 0
        assert "a.txt" in out and "1 missing" in out
        assert (data_dir / "archives" / "a.txt").read_text(encoding="utf-8") == "youtube gone\n"


class TestConsoleEncoding:
    def test_a_console_that_cannot_encode_turkish_does_not_crash_the_app(self) -> None:
        import io  # noqa: PLC0415

        stream = io.TextIOWrapper(io.BytesIO(), encoding="ascii")

        app.make_streams_forgiving(stream)
        print("İndirilenler çğıöşü", file=stream, flush=True)

        assert b"?" in stream.buffer.getvalue()  # type: ignore[attr-defined]
