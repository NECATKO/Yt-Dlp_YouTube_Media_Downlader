"""In-app settings menu.

Lets the user change the interface language, the download folders, and the
advanced settings without editing config.json by hand. Every change is written
through to disk immediately, so a crash never loses more than the edit in
progress.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .config import normalize_user_path, save_settings
from .i18n import get_available_languages, get_language_name, set_language, t
from .logging_utils import Colors, paint
from .models import UserConfig

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from .settings import AppSettings
    from .ui import UI

#: Audio containers offered for extraction. "best" keeps the source codec.
AUDIO_FORMATS = ("mp3", "m4a", "opus", "flac", "wav", "best")

#: yt-dlp's audio quality scale, best to worst.
_QUALITY_MIN, _QUALITY_MAX = 0, 9

#: Typed by the user to clear an optional value rather than keep it.
_CLEAR = "-"


class SettingsMenu:
    """Interactive editor for the persisted configuration."""

    def __init__(
        self,
        ui: UI,
        cfg: dict[str, Any],
        settings: AppSettings,
        config: UserConfig,
        config_file: Path,
    ) -> None:
        """Initialize the menu.

        Args:
            ui: The UI interface.
            cfg: The raw config.json contents; mutated and persisted in place.
            settings: The advanced settings; mutated in place.
            config: The directories currently in use.
            config_file: Where to persist changes.
        """
        self.ui = ui
        self.cfg = cfg
        self.settings = settings
        self.config = config
        self.config_file = config_file

    # -- persistence ------------------------------------------------------

    def _persist(self) -> None:
        """Write the current state to disk and confirm it to the user."""
        save_settings(self.config_file, self.cfg, self.settings)
        self.ui.print(paint(t("settings_saved"), Colors.GREEN))

    # -- input helpers ----------------------------------------------------

    def _show_current(self, value: object) -> None:
        """Print the value an edit is about to replace."""
        shown = t("settings_unset") if value in (None, "") else str(value)
        self.ui.print(paint(t("settings_current", value=shown), Colors.YELLOW))

    def _prompt_header(self, label: str, current: object, hint: str) -> None:
        self.ui.print("\n" + paint(label, Colors.CYAN, Colors.BOLD))
        self._show_current(current)
        if hint:
            self.ui.print(paint(hint, Colors.WHITE))

    def _ask_text(self, label: str, current: str, hint: str = "") -> str | None:
        """Ask for a required string.

        Returns:
            The new value, or None if the user pressed Enter to keep it.
        """
        self._prompt_header(label, current, hint)
        self.ui.print(paint(t("settings_keep_hint"), Colors.WHITE))
        return self.ui.ask_text(t("settings_value_prompt")) or None

    def _ask_optional_text(self, label: str, current: str | None, hint: str = "") -> str | None:
        """Ask for a value that may also be cleared.

        Returns:
            The new value, None if the user pressed Enter to keep it, or the
            _CLEAR sentinel if they asked to unset it.
        """
        self._prompt_header(label, current, hint)
        self.ui.print(paint(t("settings_clear_hint", clear=_CLEAR), Colors.WHITE))
        return self.ui.ask_text(t("settings_value_prompt")) or None

    def _ask_int(self, label: str, current: int, low: int, high: int) -> int | None:
        """Ask for a bounded integer.

        Returns:
            The new value, or None if the user pressed Enter to keep it.
        """
        while True:
            self._prompt_header(label, current, "")
            self.ui.print(paint(t("settings_keep_hint"), Colors.WHITE))

            answer = self.ui.ask_text(t("settings_value_prompt"))
            if not answer:
                return None
            try:
                value = int(answer)
            except ValueError:
                pass
            else:
                if low <= value <= high:
                    return value
            self.ui.print(paint(t("settings_invalid_number", min=low, max=high), Colors.RED))

    def _ask_bool(self, label: str, current: bool) -> bool:
        """Ask a yes/no question, showing the current value first."""
        self._prompt_header(label, t("label_yes") if current else t("label_no"), "")
        return self.ui.pick(label, [t("label_yes"), t("label_no")]) == 1

    # -- top level --------------------------------------------------------

    def _entries(self) -> list[tuple[str, Callable[[], None]]]:
        """Build the menu, translated with whatever language is active now."""
        return [
            (t("settings_language"), self._edit_language),
            (t("settings_videos_dir"), self._edit_videos_dir),
            (t("settings_music_dir"), self._edit_music_dir),
            (t("settings_download"), self._edit_download),
            (t("settings_audio"), self._edit_audio),
            (t("settings_subtitles"), self._edit_subtitles),
        ]

    def run(self) -> UserConfig:
        """Show the menu until the user goes back.

        Returns:
            The directories to use from now on. The caller must adopt these:
            UserConfig is frozen, so changing a folder rebuilds it.
        """
        while True:
            # Rebuilt each pass so the labels follow a language change made in
            # the previous one.
            entries = self._entries()
            labels = [label for label, _ in entries] + [t("settings_back")]

            choice = self.ui.pick(t("settings_title"), labels)
            if choice == len(labels):
                return self.config

            entries[choice - 1][1]()

    # -- individual editors -----------------------------------------------

    def _edit_language(self) -> None:
        available = get_available_languages()
        if len(available) < 2:
            return

        choice = self.ui.pick(
            t("settings_language"),
            [get_language_name(code) for code in available],
        )
        language = available[choice - 1]

        set_language(language)
        self.cfg["language"] = language
        self._persist()

    def _edit_directory(self, label: str, current: Path) -> Path | None:
        """Prompt for a folder and create it.

        Returns:
            The new directory, or None if unchanged or unusable.
        """
        answer = self._ask_text(label, str(current))
        if answer is None:
            return None

        candidate = normalize_user_path(answer)
        try:
            candidate.mkdir(parents=True, exist_ok=True)
        except OSError as ex:
            # Better to reject it here than to persist a config pointing at a
            # folder that cannot be created, which would fail every download.
            self.ui.print(paint(t("settings_dir_error", error=ex), Colors.RED))
            return None
        return candidate

    def _edit_videos_dir(self) -> None:
        new_dir = self._edit_directory(t("settings_videos_dir"), self.config.videos_dir)
        if new_dir is None:
            return

        self.config = UserConfig(
            app=self.config.app,
            videos_dir=new_dir,
            music_dir=self.config.music_dir,
            saved_at=self.config.saved_at,
        )
        self.cfg["videos_dir"] = str(new_dir)
        self._persist()

    def _edit_music_dir(self) -> None:
        new_dir = self._edit_directory(t("settings_music_dir"), self.config.music_dir)
        if new_dir is None:
            return

        self.config = UserConfig(
            app=self.config.app,
            videos_dir=self.config.videos_dir,
            music_dir=new_dir,
            saved_at=self.config.saved_at,
        )
        self.cfg["music_dir"] = str(new_dir)
        self._persist()

    def _edit_download(self) -> None:
        download = self.settings.download

        proxy = self._ask_optional_text(
            t("settings_proxy"), download.proxy, t("settings_proxy_hint")
        )
        if proxy == _CLEAR:
            download.proxy = None
        elif proxy:
            download.proxy = proxy

        rate = self._ask_optional_text(
            t("settings_rate_limit"), download.rate_limit, t("settings_rate_limit_hint")
        )
        if rate == _CLEAR:
            download.rate_limit = None
        elif rate:
            download.rate_limit = rate

        fragments = self._ask_int(t("settings_concurrent"), download.concurrent_fragments, 1, 64)
        if fragments is not None:
            download.concurrent_fragments = fragments

        sleep = self._ask_int(t("settings_sleep"), download.sleep_interval, 0, 3600)
        if sleep is not None:
            download.sleep_interval = sleep

        max_sleep = self._ask_int(t("settings_max_sleep"), download.max_sleep_interval, 0, 3600)
        if max_sleep is not None:
            download.max_sleep_interval = max_sleep

        # yt-dlp rejects a sleep window whose upper bound is below its lower one.
        if download.max_sleep_interval < download.sleep_interval:
            download.max_sleep_interval = download.sleep_interval
            self.ui.print(paint(t("settings_sleep_adjusted"), Colors.YELLOW))

        self._persist()

    def _edit_audio(self) -> None:
        audio = self.settings.audio

        self._prompt_header(t("settings_audio_format"), audio.audio_format, "")
        choice = self.ui.pick(t("settings_audio_format"), list(AUDIO_FORMATS))
        audio.audio_format = AUDIO_FORMATS[choice - 1]

        quality = self._ask_int(
            t("settings_audio_quality"), audio.audio_quality, _QUALITY_MIN, _QUALITY_MAX
        )
        if quality is not None:
            audio.audio_quality = quality

        audio.embed_thumbnail = self._ask_bool(t("settings_embed_thumbnail"), audio.embed_thumbnail)
        audio.embed_metadata = self._ask_bool(t("settings_embed_metadata"), audio.embed_metadata)

        self._persist()

    def _edit_subtitles(self) -> None:
        video = self.settings.video

        video.write_subtitles = self._ask_bool(t("settings_write_subs"), video.write_subtitles)
        video.embed_subtitles = self._ask_bool(t("settings_embed_subs"), video.embed_subtitles)

        if video.write_subtitles or video.embed_subtitles:
            langs = self._ask_text(
                t("settings_sub_langs"), video.subtitle_languages, t("settings_sub_langs_hint")
            )
            if langs:
                video.subtitle_languages = langs

        self._persist()


def run_settings_menu(
    ui: UI,
    cfg: dict[str, Any],
    settings: AppSettings,
    config: UserConfig,
    config_file: Path,
) -> UserConfig:
    """Open the settings menu and return the directories to use afterwards."""
    return SettingsMenu(ui, cfg, settings, config, config_file).run()


__all__ = ["AUDIO_FORMATS", "SettingsMenu", "run_settings_menu"]
