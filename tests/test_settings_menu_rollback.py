"""A failed save must not leave the running app believing in settings the disk lacks."""

import json
from pathlib import Path
from typing import Any

import pytest

import ytdlp_app.settings_menu as menu_module
from tests.test_settings_menu import BACK, FakeUI, _menu
from ytdlp_app.i18n import get_language, set_language, t
from ytdlp_app.models import DownloadMode, UserConfig
from ytdlp_app.settings import AppSettings


@pytest.fixture(autouse=True)
def _english():
    set_language("en")
    yield
    set_language("en")


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    return tmp_path / "config.json"


@pytest.fixture
def user_config(tmp_path: Path) -> UserConfig:
    return UserConfig(app="yt-dlp-downloader", videos_dir=tmp_path / "V", music_dir=tmp_path / "M")


@pytest.fixture
def disk_full(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*_a: Any, **_k: Any) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(menu_module, "save_settings", broken)
    monkeypatch.setattr(menu_module, "save_config", broken, raising=False)


DOWNLOAD, LANGUAGE, VIDEOS_DIR = 4, 1, 2


class TestFailedSave:
    def test_settings_and_cfg_stay_as_they_were(
        self, disk_full: None, config_file: Path, user_config: UserConfig
    ) -> None:
        settings, cfg = AppSettings(), {"language": "en"}
        # Download menu: proxy, keep the rest (Enter = keep) x4, then leave.
        ui = FakeUI(picks=[DOWNLOAD, BACK], texts=["http://proxy:8080", "", "", "", ""])

        _menu(ui, config_file, user_config, settings, cfg).run()

        assert settings.download.proxy is None
        assert cfg == {"language": "en"}
        assert t("settings_save_failed", error="No space left on device") in "\n".join(ui.printed)

    def test_the_menu_carries_on_after_a_failed_save(
        self, disk_full: None, config_file: Path, user_config: UserConfig
    ) -> None:
        ui = FakeUI(picks=[DOWNLOAD, BACK], texts=["http://proxy:8080", "", "", "", ""])

        result = _menu(ui, config_file, user_config).run()

        assert result == user_config
        assert not ui.picks

    def test_a_failed_language_change_is_reverted(
        self, disk_full: None, config_file: Path, user_config: UserConfig
    ) -> None:
        cfg = {"language": "en"}
        ui = FakeUI(picks=[LANGUAGE, 2, BACK])

        _menu(ui, config_file, user_config, cfg=cfg).run()

        assert get_language() == "en"
        assert cfg["language"] == "en"

    def test_a_failed_folder_change_keeps_the_old_folder(
        self, disk_full: None, config_file: Path, user_config: UserConfig, tmp_path: Path
    ) -> None:
        cfg = {"videos_dir": "V"}
        ui = FakeUI(picks=[VIDEOS_DIR, BACK], texts=[str(tmp_path / "Elsewhere")])

        result = _menu(ui, config_file, user_config, cfg=cfg).run()

        assert result.videos_dir == user_config.videos_dir
        assert cfg == {"videos_dir": "V"}

    def test_a_later_good_save_does_not_carry_the_failed_edit(
        self, monkeypatch: pytest.MonkeyPatch, config_file: Path, user_config: UserConfig
    ) -> None:
        real = menu_module.save_settings
        failures = iter([True, False])

        def flaky(path: Path, cfg: dict[str, Any], settings: AppSettings) -> None:
            if next(failures):
                raise OSError("full")
            real(path, cfg, settings)

        monkeypatch.setattr(menu_module, "save_settings", flaky)
        settings, cfg = AppSettings(), {}
        ui = FakeUI(
            picks=[DOWNLOAD, DOWNLOAD, BACK],
            # First pass: proxy edit (save fails). Second pass: only the speed limit.
            texts=["http://proxy:8080", "", "", "", "", "-", "2M", "", "", ""],
        )

        _menu(ui, config_file, user_config, settings, cfg).run()

        on_disk = json.loads(config_file.read_text(encoding="utf-8"))
        assert on_disk["settings"]["download"]["proxy"] is None
        assert on_disk["settings"]["download"]["rate_limit"] == "2M"
        assert settings.download.proxy is None


class TestInterruptedEdit:
    def test_ctrl_c_in_the_middle_of_an_edit_discards_the_half_made_change(
        self, config_file: Path, user_config: UserConfig
    ) -> None:
        settings = AppSettings()

        class Interrupting(FakeUI):
            def ask_text(self, prompt: str) -> str:
                if not self.texts:
                    raise KeyboardInterrupt
                return super().ask_text(prompt)

        ui = Interrupting(picks=[DOWNLOAD], texts=["http://proxy:8080"])

        with pytest.raises(KeyboardInterrupt):
            _menu(ui, config_file, user_config, settings).run()

        assert settings.download.proxy is None
        assert not config_file.exists()


class TestSessionDefaultHeight:
    def test_a_failed_save_reverts_the_default_it_was_asked_to_save(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import ytdlp_app.session as session_module  # noqa: PLC0415
        from ytdlp_app.models import AppPaths  # noqa: PLC0415
        from ytdlp_app.session import InteractiveSession  # noqa: PLC0415

        paths = AppPaths(tmp_path, tmp_path / "config.json", tmp_path / "logs", tmp_path / "a")
        session = InteractiveSession(
            FakeUI(),
            UserConfig("x", tmp_path, tmp_path),
            paths,  # type: ignore[arg-type]
        )
        monkeypatch.setattr(
            session_module, "save_settings", lambda *_a: (_ for _ in ()).throw(OSError("full"))
        )

        with pytest.raises(OSError, match="full"):
            session._persist_default_height(DownloadMode.VIDEO, 1440)
        with pytest.raises(OSError, match="full"):
            session._persist_default_height(DownloadMode.ARCHIVE, None)

        assert session.settings.video.max_height is None
        assert session.settings.archive.max_height == 1080
