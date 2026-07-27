"""Tests for the in-app settings menu."""

import json
from pathlib import Path
from typing import Any

import pytest

from ytdlp_app.config import load_settings
from ytdlp_app.i18n import get_language, set_language
from ytdlp_app.models import UserConfig
from ytdlp_app.settings import AppSettings
from ytdlp_app.settings_menu import AUDIO_FORMATS, SettingsMenu

BACK = "back"


class FakeUI:
    """A UI that replays scripted answers instead of reading stdin.

    ``picks`` and ``texts`` are consumed in order. The literal BACK marker in
    ``picks`` selects the last option of whatever menu is showing, which is how
    every menu here is exited without hardcoding its length.
    """

    def __init__(self, picks: list[Any] | None = None, texts: list[str] | None = None) -> None:
        self.picks = list(picks or [])
        self.texts = list(texts or [])
        self.printed: list[str] = []

    def print(self, text: str = "") -> None:
        self.printed.append(text)

    def print_panel(self, text: str, title: str | None = None, color: str = "") -> None:
        self.printed.append(text)

    def pick(self, prompt: str, options: list[str]) -> int:
        if not self.picks:
            raise AssertionError(f"unexpected pick(): {prompt!r} with {options!r}")
        choice = self.picks.pop(0)
        return len(options) if choice is BACK else int(choice)

    def ask_text(self, prompt: str) -> str:
        if not self.texts:
            raise AssertionError(f"unexpected ask_text(): {prompt!r}")
        return self.texts.pop(0)

    def prompt_exit_on_failure(self) -> bool:
        return True


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    return tmp_path / "config.json"


@pytest.fixture
def user_config(tmp_path: Path) -> UserConfig:
    return UserConfig(
        app="yt-dlp-downloader",
        videos_dir=tmp_path / "Videos",
        music_dir=tmp_path / "Music",
    )


@pytest.fixture(autouse=True)
def _english():
    """Menus are language sensitive; start each test from a known state."""
    set_language("en")
    yield
    set_language("en")


def _menu(
    ui: FakeUI,
    config_file: Path,
    user_config: UserConfig,
    settings: AppSettings | None = None,
    cfg: dict[str, Any] | None = None,
) -> SettingsMenu:
    return SettingsMenu(
        ui=ui,
        cfg=cfg if cfg is not None else {},
        settings=settings if settings is not None else AppSettings(),
        config=user_config,
        config_file=config_file,
    )


class TestNavigation:
    """The menu has to be exitable and must not act on its own."""

    def test_back_returns_immediately(self, config_file: Path, user_config: UserConfig) -> None:
        ui = FakeUI(picks=[BACK])
        result = _menu(ui, config_file, user_config).run()

        assert result == user_config
        assert not config_file.exists(), "leaving the menu must not write anything"

    def test_back_returns_the_current_directories(
        self, config_file: Path, user_config: UserConfig
    ) -> None:
        ui = FakeUI(picks=[BACK])
        assert _menu(ui, config_file, user_config).run().videos_dir == user_config.videos_dir


class TestLanguage:
    """Changing the language must take effect and survive a restart."""

    def test_switch_persists_and_applies(self, config_file: Path, user_config: UserConfig) -> None:
        cfg: dict[str, Any] = {"language": "en"}
        # Menu entry 1 (language), then Turkish, then leave.
        ui = FakeUI(picks=[1, 2, BACK])

        _menu(ui, config_file, user_config, cfg=cfg).run()

        assert cfg["language"] == "tr"
        assert get_language() == "tr"
        assert json.loads(config_file.read_text(encoding="utf-8"))["language"] == "tr"


class TestDirectories:
    """Folder edits rebuild the frozen UserConfig and create the folder."""

    def test_videos_dir_is_changed_and_created(
        self, tmp_path: Path, config_file: Path, user_config: UserConfig
    ) -> None:
        target = tmp_path / "NewVideos"
        cfg: dict[str, Any] = {}
        ui = FakeUI(picks=[2, BACK], texts=[str(target)])

        result = _menu(ui, config_file, user_config, cfg=cfg).run()

        assert result.videos_dir == target
        assert target.is_dir()
        assert cfg["videos_dir"] == str(target)
        # The other folder must survive the rebuild untouched.
        assert result.music_dir == user_config.music_dir

    def test_music_dir_is_changed(
        self, tmp_path: Path, config_file: Path, user_config: UserConfig
    ) -> None:
        target = tmp_path / "NewMusic"
        ui = FakeUI(picks=[3, BACK], texts=[str(target)])

        result = _menu(ui, config_file, user_config).run()

        assert result.music_dir == target
        assert result.videos_dir == user_config.videos_dir

    def test_blank_input_keeps_the_current_folder(
        self, config_file: Path, user_config: UserConfig
    ) -> None:
        ui = FakeUI(picks=[2, BACK], texts=[""])

        result = _menu(ui, config_file, user_config).run()

        assert result.videos_dir == user_config.videos_dir
        assert not config_file.exists()


class TestDownloadSettings:
    """The download submenu asks six questions in a fixed order."""

    def _run(
        self,
        answers: list[str],
        config_file: Path,
        user_config: UserConfig,
        settings: AppSettings,
    ) -> None:
        ui = FakeUI(picks=[4, BACK], texts=answers)
        _menu(ui, config_file, user_config, settings=settings).run()

    def test_values_are_stored(self, config_file: Path, user_config: UserConfig) -> None:
        settings = AppSettings()
        # proxy, rate limit, fragments, min sleep, max sleep
        self._run(
            ["http://127.0.0.1:8080", "1M", "8", "2", "5"],
            config_file,
            user_config,
            settings,
        )

        assert settings.download.proxy == "http://127.0.0.1:8080"
        assert settings.download.rate_limit == "1M"
        assert settings.download.concurrent_fragments == 8
        assert settings.download.sleep_interval == 2
        assert settings.download.max_sleep_interval == 5

    def test_blank_answers_keep_the_defaults(
        self, config_file: Path, user_config: UserConfig
    ) -> None:
        settings = AppSettings()
        self._run(["", "", "", "", ""], config_file, user_config, settings)

        assert settings.download.proxy is None
        assert settings.download.concurrent_fragments == 4

    def test_dash_clears_an_optional_value(
        self, config_file: Path, user_config: UserConfig
    ) -> None:
        settings = AppSettings()
        settings.download.proxy = "http://old:3128"
        settings.download.rate_limit = "500K"

        self._run(["-", "-", "", "", ""], config_file, user_config, settings)

        assert settings.download.proxy is None
        assert settings.download.rate_limit is None

    def test_invalid_number_is_rejected_then_accepted(
        self, config_file: Path, user_config: UserConfig
    ) -> None:
        settings = AppSettings()
        # "abc" and "999" are both refused for the fragment count before "6".
        self._run(["", "", "abc", "999", "6", "", ""], config_file, user_config, settings)

        assert settings.download.concurrent_fragments == 6

    def test_max_sleep_below_min_is_corrected(
        self, config_file: Path, user_config: UserConfig
    ) -> None:
        """yt-dlp rejects a window whose upper bound is under its lower one."""
        settings = AppSettings()
        self._run(["", "", "", "10", "3"], config_file, user_config, settings)

        assert settings.download.sleep_interval == 10
        assert settings.download.max_sleep_interval == 10


class TestAudioSettings:
    """The audio submenu picks a format, then asks quality and two toggles."""

    def test_format_quality_and_toggles(self, config_file: Path, user_config: UserConfig) -> None:
        settings = AppSettings()
        opus = AUDIO_FORMATS.index("opus") + 1
        # menu entry 5, format=opus, then quality text, thumbnail=no, metadata=yes
        ui = FakeUI(picks=[5, opus, 2, 1, BACK], texts=["5"])

        _menu(ui, config_file, user_config, settings=settings).run()

        assert settings.audio.audio_format == "opus"
        assert settings.audio.audio_quality == 5
        assert settings.audio.embed_thumbnail is False
        assert settings.audio.embed_metadata is True

    def test_quality_is_bounded(self, config_file: Path, user_config: UserConfig) -> None:
        settings = AppSettings()
        mp3 = AUDIO_FORMATS.index("mp3") + 1
        ui = FakeUI(picks=[5, mp3, 1, 1, BACK], texts=["42", "9"])

        _menu(ui, config_file, user_config, settings=settings).run()

        assert settings.audio.audio_quality == 9


class TestSubtitleSettings:
    """Languages are only asked for once subtitles are actually enabled."""

    def test_enabling_subtitles_asks_for_languages(
        self, config_file: Path, user_config: UserConfig
    ) -> None:
        settings = AppSettings()
        ui = FakeUI(picks=[6, 1, 1, BACK], texts=["en,tr"])

        _menu(ui, config_file, user_config, settings=settings).run()

        assert settings.video.write_subtitles is True
        assert settings.video.embed_subtitles is True
        assert settings.video.subtitle_languages == "en,tr"

    def test_declining_subtitles_skips_the_language_prompt(
        self, config_file: Path, user_config: UserConfig
    ) -> None:
        settings = AppSettings()
        # No texts scripted: asking for languages would raise in FakeUI.
        ui = FakeUI(picks=[6, 2, 2, BACK])

        _menu(ui, config_file, user_config, settings=settings).run()

        assert settings.video.write_subtitles is False
        assert settings.video.embed_subtitles is False


class TestPersistence:
    """Edits have to reach disk in the shape load_settings expects."""

    def test_changes_round_trip_through_config_json(
        self, config_file: Path, user_config: UserConfig
    ) -> None:
        settings = AppSettings()
        ui = FakeUI(picks=[4, BACK], texts=["http://proxy:9000", "", "", "", ""])

        _menu(ui, config_file, user_config, settings=settings).run()

        stored = json.loads(config_file.read_text(encoding="utf-8"))
        assert load_settings(stored).download.proxy == "http://proxy:9000"

    def test_unrelated_config_keys_survive(
        self, config_file: Path, user_config: UserConfig
    ) -> None:
        cfg: dict[str, Any] = {"app": "yt-dlp-downloader", "language": "en"}
        ui = FakeUI(picks=[4, BACK], texts=["", "", "", "", ""])

        _menu(ui, config_file, user_config, cfg=cfg).run()

        stored = json.loads(config_file.read_text(encoding="utf-8"))
        assert stored["app"] == "yt-dlp-downloader"
        assert stored["language"] == "en"
