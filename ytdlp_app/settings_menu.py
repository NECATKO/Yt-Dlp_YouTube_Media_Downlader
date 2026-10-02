"""In-app settings menu.

Lets the user change the interface language, the download folders, and the
advanced settings without editing config.json by hand. Every change is written
through to disk immediately, so a crash never loses more than the edit in
progress.
"""

from __future__ import annotations

import copy
import dataclasses
from typing import TYPE_CHECKING, Any

from .config import normalize_user_path, save_settings, to_config_path
from .i18n import get_available_languages, get_language, get_language_name, set_language, t
from .logging_utils import Colors, paint
from .models import UserConfig
from .redact import redact_secrets, register_proxy
from .settings import (
    AUDIO_FORMATS,
    AppSettings,
    check_proxy,
    check_rate_limit,
    check_text,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from .ui import UI

#: yt-dlp's audio quality scale, best to worst.
_QUALITY_MIN, _QUALITY_MAX = 0, 9

#: Typed by the user to clear an optional value rather than keep it.
_CLEAR = "-"

#: Upper bound for any archive-mode wait, in seconds.
_MAX_WAIT_SECONDS = 3600

#: The resolution caps offered in the menu, in the order shown; None is "unlimited".
_HEIGHT_CHOICES: tuple[int | None, ...] = (1080, 1440, 2160, None)


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
        """Write the current state to disk and confirm it to the user.

        Raises:
            OSError: The file could not be written. run() then puts every part of the
                edit back, so the running app and config.json keep agreeing.
        """
        save_settings(self.config_file, self.cfg, self.settings)
        register_proxy(self.settings.download.proxy)
        self.ui.print(paint(t("settings_saved"), Colors.GREEN))

    def _snapshot(self) -> tuple[AppSettings, dict[str, Any], UserConfig, str]:
        """Everything an editor may change, as it is now."""
        return (
            copy.deepcopy(self.settings),
            copy.deepcopy(self.cfg),
            self.config,
            get_language(),
        )

    def _restore(self, snapshot: tuple[AppSettings, dict[str, Any], UserConfig, str]) -> None:
        """Put back what _snapshot captured, in the same objects the session holds."""
        settings, cfg, config, language = snapshot
        for f in dataclasses.fields(AppSettings):
            setattr(self.settings, f.name, getattr(settings, f.name))
        self.cfg.clear()
        self.cfg.update(cfg)
        self.config = config
        set_language(language)
        register_proxy(None)
        register_proxy(self.settings.download.proxy)

    # -- input helpers ----------------------------------------------------

    def _show_current(self, value: object) -> None:
        """Print the value an edit is about to replace."""
        # A proxy URL may carry a password, and this line is printed to the console.
        shown = t("settings_unset") if value in (None, "") else redact_secrets(str(value))
        self.ui.print(paint(t("settings_current", value=shown), Colors.YELLOW))

    def _prompt_header(self, label: str, current: object, hint: str) -> None:
        self.ui.print("\n" + paint(label, Colors.CYAN, Colors.BOLD))
        self._show_current(current)
        if hint:
            self.ui.print(paint(hint, Colors.WHITE))

    def _checked(
        self, answer: str, check: Callable[[object], str | None] | None, hint: str
    ) -> str | None:
        """``answer`` as the setting will hold it, or None after saying why it cannot."""
        if check is None:
            return answer
        value = check(answer)
        if value is None:
            # The same rule the config loader applies: a value it would throw away on the
            # next start must not be saved now.
            shown = redact_secrets(answer)
            self.ui.print(paint(t("settings_invalid_value", value=shown, hint=hint), Colors.RED))
        return value

    def _ask_text(
        self,
        label: str,
        current: str,
        hint: str = "",
        check: Callable[[object], str | None] | None = None,
    ) -> str | None:
        """Ask for a required string, again until ``check`` accepts it.

        Returns:
            The new value, or None if the user pressed Enter to keep it.
        """
        while True:
            self._prompt_header(label, current, hint)
            self.ui.print(paint(t("settings_keep_hint"), Colors.WHITE))
            answer = self.ui.ask_text(t("settings_value_prompt"))
            if not answer:
                return None
            value = self._checked(answer, check, hint)
            if value is not None:
                return value

    def _ask_optional_text(
        self,
        label: str,
        current: str | None,
        hint: str = "",
        check: Callable[[object], str | None] | None = None,
    ) -> str | None:
        """Ask for a value that may also be cleared, again until ``check`` accepts it.

        Returns:
            The new value, None if the user pressed Enter to keep it, or the
            _CLEAR sentinel if they asked to unset it.
        """
        while True:
            self._prompt_header(label, current, hint)
            self.ui.print(paint(t("settings_clear_hint", clear=_CLEAR), Colors.WHITE))
            answer = self.ui.ask_text(t("settings_value_prompt"))
            if not answer:
                return None
            if answer == _CLEAR:
                return _CLEAR
            value = self._checked(answer, check, hint)
            if value is not None:
                return value

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

    def _ask_seconds(self, label: str, current: float, high: float) -> float | None:
        """Ask for a non-negative, possibly fractional, number of seconds.

        Accepts a decimal comma as well, since that is what Turkish users type.

        Returns:
            The new value, or None if the user pressed Enter to keep it.
        """
        while True:
            self._prompt_header(label, f"{current:g}", "")
            self.ui.print(paint(t("settings_keep_hint"), Colors.WHITE))

            answer = self.ui.ask_text(t("settings_value_prompt"))
            if not answer:
                return None
            try:
                value = float(answer.replace(",", "."))
            except ValueError:
                pass
            else:
                # float() also accepts "nan" and "inf", which the bounds reject.
                if 0 <= value <= high:
                    # 5.0 is stored as 5, so the config file keeps reading naturally.
                    return int(value) if value.is_integer() else value
            self.ui.print(paint(t("settings_invalid_seconds", max=f"{high:g}"), Colors.RED))

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
            (t("settings_archive"), self._edit_archive),
            (t("settings_video_height"), self._edit_video_height),
            (t("settings_archive_height"), self._edit_archive_height),
            (t("settings_external_config"), self._edit_external_config),
            (t("settings_speed_test"), self._edit_speed_test),
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

            self._run_editor(entries[choice - 1][1])

    def _run_editor(self, editor: Callable[[], None]) -> None:
        """Run one editor as a unit: it is applied whole, or not at all.

        Editors change the live settings as they go and save at the end. If the save
        fails (a full or read-only disk), or the user interrupts halfway, the changes
        made so far are taken back, because they exist nowhere but in memory.
        """
        snapshot = self._snapshot()
        try:
            editor()
        except OSError as ex:
            self._restore(snapshot)
            self.ui.print(paint(t("settings_save_failed", error=ex.strerror or ex), Colors.RED))
        except BaseException:
            self._restore(snapshot)
            raise

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

        candidate = normalize_user_path(answer, self.config_file.parent)
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
        self.cfg["videos_dir"] = to_config_path(new_dir, self.config_file.parent)
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
        self.cfg["music_dir"] = to_config_path(new_dir, self.config_file.parent)
        self._persist()

    def _edit_download(self) -> None:
        download = self.settings.download

        proxy = self._ask_optional_text(
            t("settings_proxy"), download.proxy, t("settings_proxy_hint"), check_proxy
        )
        if proxy == _CLEAR:
            download.proxy = None
        elif proxy:
            download.proxy = proxy

        rate = self._ask_optional_text(
            t("settings_rate_limit"),
            download.rate_limit,
            t("settings_rate_limit_hint"),
            check_rate_limit,
        )
        if rate == _CLEAR:
            download.rate_limit = None
        elif rate:
            download.rate_limit = rate

        fragments = self._ask_int(t("settings_concurrent"), download.concurrent_fragments, 1, 64)
        if fragments is not None:
            download.concurrent_fragments = fragments

        sleep = self._ask_seconds(t("settings_sleep"), download.sleep_interval, _MAX_WAIT_SECONDS)
        if sleep is not None:
            download.sleep_interval = sleep

        max_sleep = self._ask_seconds(
            t("settings_max_sleep"), download.max_sleep_interval, _MAX_WAIT_SECONDS
        )
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
                t("settings_sub_langs"),
                video.subtitle_languages,
                t("settings_sub_langs_hint"),
                check_text,
            )
            if langs:
                video.subtitle_languages = langs

        self._persist()

    def _edit_archive(self) -> None:
        archive = self.settings.archive

        prompts = (
            ("sleep_requests", t("settings_archive_sleep_requests")),
            ("sleep_interval", t("settings_archive_sleep_interval")),
            ("max_sleep_interval", t("settings_archive_max_sleep")),
            ("sleep_subtitles", t("settings_archive_sleep_subtitles")),
        )
        for attr, label in prompts:
            value = self._ask_seconds(label, getattr(archive, attr), _MAX_WAIT_SECONDS)
            if value is not None:
                setattr(archive, attr, value)

        # yt-dlp rejects a sleep window whose upper bound is below its lower one.
        if archive.max_sleep_interval < archive.sleep_interval:
            archive.max_sleep_interval = archive.sleep_interval
            self.ui.print(paint(t("settings_sleep_adjusted"), Colors.YELLOW))

        self._persist()

    def _height_label(self, height: int | None, current: int | None) -> str:
        label = (
            t("resolution_unlimited") if height is None else t("resolution_option", height=height)
        )
        return t("resolution_default_mark", label=label) if height == current else label

    def _pick_height(self, label: str, current: int | None) -> int | None:
        """Ask for a resolution cap; the current one is marked as the default."""
        shown = (
            t("resolution_unlimited") if current is None else t("resolution_option", height=current)
        )
        self._prompt_header(label, shown, "")
        options = [self._height_label(h, current) for h in _HEIGHT_CHOICES]
        return _HEIGHT_CHOICES[self.ui.pick(label, options) - 1]

    def _edit_video_height(self) -> None:
        video = self.settings.video
        video.max_height = self._pick_height(t("settings_video_height"), video.max_height)
        self._persist()

    def _edit_archive_height(self) -> None:
        archive = self.settings.archive
        archive.max_height = self._pick_height(t("settings_archive_height"), archive.max_height)
        self._persist()

    def _edit_external_config(self) -> None:
        download = self.settings.download
        self.ui.print(paint(t("settings_external_config_hint"), Colors.WHITE))
        download.allow_external_config = self._ask_bool(
            t("settings_external_config"), download.allow_external_config
        )
        self._persist()

    def _edit_speed_test(self) -> None:
        download = self.settings.download
        self.ui.print(paint(t("settings_speed_test_hint"), Colors.WHITE))
        download.speed_test = self._ask_bool(t("settings_speed_test"), download.speed_test)
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
