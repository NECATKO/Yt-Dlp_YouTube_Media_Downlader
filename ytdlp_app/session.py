"""Interactive session management for ytdlp_app.

This module handles the main application loop, user interaction, and
download process coordination.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .exceptions import ValidationError
from .exec import run_capture, run_cmd_tee
from .i18n import t
from .logging_utils import Colors, append_log, log_error, now_stamp, paint
from .models import (
    ActionChoice,
    AppPaths,
    ContainerChoice,
    DownloadMode,
    DownloadPlan,
    ModeChoice,
    PlaylistChoice,
    PlaylistEntry,
    ProfileChoice,
    UserConfig,
)
from .playlist import (
    fetch_playlist_entries,
    get_playlist_id,
    is_playlist_url,
    read_archive_ids,
)
from .settings import AppSettings
from .settings_menu import run_settings_menu
from .skip_probe import probe_skip_reason
from .system import deno_available, ffmpeg_available, refresh_tool_cache, yt_dlp_available
from .validators import validate_url
from .yt_dlp import CommandBuilder

if TYPE_CHECKING:
    from .ui import ConsoleUI

#: Typed at the URL prompt to open the settings menu instead of downloading.
SETTINGS_SHORTCUT = "s"


class CycleOutcome(IntEnum):
    """Result of one interactive cycle, including its process exit status."""

    CONTINUE = -1
    EXIT_SUCCESS = 0
    EXIT_FAILURE = 1
    INTERRUPTED = 130


class InteractiveSession:
    """Manages an interactive download session."""

    def __init__(
        self,
        ui: ConsoleUI,
        config: UserConfig,
        paths: AppPaths,
        settings: AppSettings | None = None,
        cfg: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the session.

        Args:
            ui: The UI interface.
            config: User configuration.
            paths: Application paths.
            settings: Advanced settings from config.json; defaults when omitted.
            cfg: The raw config.json contents, which the settings menu edits and
                persists. An empty dict is used when omitted.
        """
        self.ui = ui
        self.config = config
        self.paths = paths
        self.settings = settings if settings is not None else AppSettings()
        self.cfg = cfg if cfg is not None else {}
        self.log_path: Path | None = None

    def analyze_log_for_error(self, log_path: Path) -> str:
        """Read the log to find a user-friendly error cause."""
        if not log_path.exists():
            return t("error_log_missing")

        try:
            # yt-dlp redraws its progress bar with bare carriage returns and
            # run_cmd_tee writes them through verbatim, so splitting on "\n"
            # alone (or letting universal newlines treat "\r" as a terminator)
            # buries the real error under hundreds of progress fragments.
            raw = log_path.read_text(encoding="utf-8", errors="replace")
            lines = [ln.strip() for ln in re.split(r"[\r\n]+", raw) if ln.strip()]

            # Classify on the diagnostic lines rather than a positional window:
            # a long download can push the real error thousands of progress
            # fragments back from the end of the file.
            failures = [ln for ln in lines if "ERROR:" in ln or "WARNING:" in ln]
            content = "\n".join(failures or lines[-200:])

            if "is not a valid URL" in content:
                return t("error_invalid_url")
            # Checked before "Video unavailable": yt-dlp reports a copyright
            # takedown as an unavailable video with the reason appended, and the
            # specific cause is the more useful message.
            if "copyright" in content.lower():
                return t("error_copyright")
            if "Video unavailable" in content:
                return t("error_unavailable")
            if "Private video" in content:
                return t("error_private")
            if "members-only" in content or "members only" in content:
                return t("error_members_only")
            if "HTTP Error 403" in content:
                return t("error_forbidden")
            if "Sign in to confirm your age" in content:
                return t("error_age_restricted")
            if "Unsupported URL" in content:
                return t("error_unsupported_url")
            if "not available in your country" in content or "geo restricted" in content.lower():
                return t("error_region_blocked")
            if (
                "Name or service not known" in content
                or "Temporary failure in name resolution" in content
            ):
                return t("error_network")

            # Nothing matched a known cause: quote the last raw ERROR verbatim.
            for line in reversed(failures):
                if "ERROR:" in line:
                    detail = line.split("ERROR:", 1)[1].strip()
                    return t("error_details", detail=detail)

            return t("error_download_generic")
        except Exception:
            return t("error_log_unreadable")

    def handle_error(self, log_path: Path | None) -> bool:
        """Display a friendly error message and ask to continue.

        Returns:
            True if user wants to exit, False if they want to continue/retry.
        """
        friendly_msg = self.analyze_log_for_error(log_path) if log_path else t("error_system")

        self.ui.print(f"\n{Colors.RED}{Colors.BOLD}{t('download_failed')}{Colors.RESET}")
        self.ui.print(f"{Colors.YELLOW}{t('error_reason', reason=friendly_msg)}{Colors.RESET}")
        if log_path:
            self.ui.print(f"\n{Colors.WHITE}{t('error_log_hint')}{Colors.RESET}")
            self.ui.print(f"{Colors.WHITE}{log_path}{Colors.RESET}")

        return self.ui.prompt_exit_on_failure()

    def run_loop(self) -> int:
        """Run the main interactive loop.

        Returns:
            Exit code (0 on a clean exit, 1 if the session ended on an error).
        """
        while True:
            # The try sits inside the loop so that a failed cycle can return to
            # the URL prompt when the user asks to keep going.
            try:
                outcome = self._process_one_cycle()
                if outcome != CycleOutcome.CONTINUE:
                    return int(outcome)
            except (KeyboardInterrupt, EOFError):
                # EOF means stdin is gone (piped or closed); prompting again --
                # which is what the generic handler below would do -- can only
                # raise the same error.
                self.ui.print(f"\n>>> {t('status_cancelled')} (Ctrl+C).")
                return int(CycleOutcome.INTERRUPTED)
            except Exception as ex:
                log_error(self.log_path, t("error_unexpected"), ex)
                self.ui.print(t("error_check_logs"))
                if self.handle_error(self.log_path):
                    return 1

    def open_settings(self) -> None:
        """Open the settings menu and adopt whatever it changed."""
        self.config = run_settings_menu(
            self.ui,
            self.cfg,
            self.settings,
            self.config,
            self.paths.config_file,
        )

    def _ask_url(self) -> str | None:
        """Prompt for a URL until a usable one is given.

        Also accepts the settings shortcut, handling it before returning.

        Returns:
            The validated URL, or None when the user asked to exit.
        """
        while True:
            raw = self.ui.ask_text("\n" + t("prompt_url"))
            if not raw:
                self.ui.print(t("error_no_url"))
                return None
            if raw.strip().lower() == SETTINGS_SHORTCUT:
                self.open_settings()
                continue
            try:
                # Guards against input yt-dlp would misread, most importantly a
                # leading "-", which it would take as a command-line flag.
                return validate_url(raw)
            except ValidationError:
                self.ui.print(
                    f"{paint(t('label_error'), Colors.RED, Colors.BOLD)} "
                    f"{paint(t('error_url_invalid_input'), Colors.RED)}"
                )

    def _process_one_cycle(self) -> CycleOutcome:
        """Process one download cycle and preserve its exit semantics."""
        self.log_path = None

        # Tool availability is cached; drop it each cycle so a user who installs
        # a missing tool mid-session stops being warned about it.
        refresh_tool_cache()

        # 1) URL
        url = self._ask_url()
        if url is None:
            return CycleOutcome.EXIT_SUCCESS

        # 2) Mode selection
        mode_choice = self.ui.pick(t("prompt_mode"), [t("mode_video"), t("mode_audio")])
        mode = DownloadMode.VIDEO if mode_choice == ModeChoice.VIDEO else DownloadMode.AUDIO

        # 3) Pre-flight checks
        deno_ok = deno_available()

        if not yt_dlp_available():
            self.ui.print(
                f"{paint(t('label_error'), Colors.RED, Colors.BOLD)} "
                f"{paint(t('error_ytdlp_not_found'), Colors.RED)}"
            )
            return CycleOutcome.EXIT_FAILURE

        if not ffmpeg_available():
            self.ui.print(
                f"\n{paint(t('label_warning'), Colors.YELLOW, Colors.BOLD)} "
                f"{paint(t('error_ffmpeg_not_found'), Colors.YELLOW)}\n"
                f"{paint('- ' + t('warn_ffmpeg_mp3'), Colors.WHITE)}\n"
                f"{paint('- ' + t('warn_ffmpeg_mp4'), Colors.WHITE)}\n"
                f"{paint(t('warn_ffmpeg_fix'), Colors.CYAN)}\n"
            )

        if not deno_ok:
            self.ui.print(
                f"\n{paint(t('label_warning'), Colors.YELLOW, Colors.BOLD)} "
                f"{paint(t('warn_deno_missing'), Colors.YELLOW)}\n"
                f"{paint('- ' + t('warn_deno_detail'), Colors.WHITE)}\n"
                f"{paint('- ' + t('warn_deno_fix'), Colors.CYAN)}\n"
            )

        # 4) Playlist vs single video
        playlist_like = is_playlist_url(url)
        force_single = False
        if playlist_like:
            what = self.ui.pick(
                t("prompt_playlist"),
                [
                    t("playlist_full"),
                    t("playlist_single"),
                ],
            )
            if what == PlaylistChoice.SINGLE:
                force_single = True

        is_playlist = playlist_like and (not force_single)
        playlist_id = get_playlist_id(url) if is_playlist else None

        # 5) MP4 profile
        mp4_profile: ProfileChoice | None = None
        remux_container: ContainerChoice | None = None
        if mode == DownloadMode.VIDEO:
            mp4_profile = ProfileChoice(
                self.ui.pick(
                    t("prompt_mp4_profile"),
                    [
                        t("profile_compatibility"),
                        t("profile_quality"),
                    ],
                )
            )
            if mp4_profile == ProfileChoice.QUALITY:
                remux_container = ContainerChoice(
                    self.ui.pick(
                        t("prompt_container"),
                        [
                            t("container_mkv"),
                            t("container_mp4"),
                        ],
                    )
                )

        # 6) Directories and templates
        self.paths.archives_dir.mkdir(parents=True, exist_ok=True)
        self.paths.logs_dir.mkdir(parents=True, exist_ok=True)

        templates = self.settings.output
        if mode == DownloadMode.VIDEO:
            if is_playlist:
                base_dir = self.config.videos_dir / "yt-dlp"
                output_template = str(base_dir / templates.playlist_video_template)
                archive_path = self.paths.archives_dir / f"playlist_{playlist_id}_mp4.txt"
            else:
                base_dir = self.config.videos_dir / "Downloaded Videos"
                output_template = str(base_dir / templates.single_video_template)
                archive_path = self.paths.archives_dir / "single_videos_mp4.txt"
        elif is_playlist:
            base_dir = self.config.music_dir / "yt-dlp"
            output_template = str(base_dir / templates.playlist_audio_template)
            archive_path = self.paths.archives_dir / f"playlist_{playlist_id}_mp3.txt"
        else:
            base_dir = self.config.music_dir / "Downloaded Music"
            output_template = str(base_dir / templates.single_audio_template)
            archive_path = self.paths.archives_dir / "single_audios_mp3.txt"

        base_dir.mkdir(parents=True, exist_ok=True)
        log_path = (
            self.paths.logs_dir
            / f"yt-dlp_{mode}_{'playlist' if is_playlist else 'single'}_{now_stamp()}.log"
        )
        self.log_path = log_path

        self._print_summary_panel(
            mode,
            is_playlist,
            base_dir,
            output_template,
            archive_path,
            deno_ok,
            mp4_profile,
        )

        append_log(
            log_path,
            (
                "\n" + "=" * 80 + "\n"
                f"[{datetime.now().isoformat(timespec='seconds')}] START\n"
                f"mode={mode} is_playlist={is_playlist} url={url}\n"
                f"base_dir={base_dir}\n"
                f"output_template={output_template}\n"
                f"archive_path={archive_path}\n"
                f"ffmpeg_available={ffmpeg_available()} "
                f"yt_dlp_available={yt_dlp_available()} deno_available={deno_ok}\n"
                + "=" * 80
                + "\n"
            ),
        )

        # 7) Command Builder
        cmd_builder = CommandBuilder(
            url=url,
            output_template=output_template,
            archive_path=archive_path,
            is_playlist=is_playlist,
            use_deno=deno_ok,
            settings=self.settings,
        )

        plan = DownloadPlan(
            url=url,
            mode=mode,
            is_playlist=is_playlist,
            playlist_id=playlist_id,
            mp4_profile=mp4_profile,
            remux_container=remux_container,
            base_dir=base_dir,
            output_template=output_template,
            archive_path=archive_path,
            log_path=log_path,
            js_args=cmd_builder.js_args,
        )

        # 8) Playlist mapping
        entries = []
        if plan.is_playlist:
            try:
                entries = fetch_playlist_entries(plan.url, plan.js_args, run_capture)
            except Exception as ex:
                log_error(log_path, t("playlist_fetch_failed_log"), ex)
                self.ui.print(f"{t('playlist_fetch_failed')}\n{ex}\n")
                if self.ui.prompt_exit_on_failure():
                    return CycleOutcome.EXIT_FAILURE

        # 9) DOWNLOAD
        final_rc = self._execute_download(plan, cmd_builder)
        if final_rc == 130:
            return CycleOutcome.INTERRUPTED
        if final_rc != 0:
            if self.handle_error(log_path):
                return CycleOutcome.EXIT_FAILURE
            return CycleOutcome.CONTINUE

        append_log(
            log_path,
            f"\n[INFO {datetime.now().isoformat(timespec='seconds')}] "
            f"DOWNLOAD_FINISHED returncode={final_rc}\n",
        )

        # 10) Skip report
        self._show_skip_report(plan, entries)

        self.ui.print("\n" + t("tasks_completed"))
        self.ui.print(f"{t('info_log')} {log_path}")
        self.ui.print(f"{t('info_config')} {self.paths.config_file}")

        next_action = self.ui.pick(
            t("prompt_next"),
            [
                t("action_download"),
                t("action_settings"),
                t("action_exit"),
            ],
        )
        if next_action == ActionChoice.SETTINGS:
            self.open_settings()
            # Settings are not a terminal choice: fall through to the URL
            # prompt so the user can act on what they just changed.
            return CycleOutcome.CONTINUE
        if next_action == ActionChoice.DOWNLOAD_ANOTHER:
            return CycleOutcome.CONTINUE
        return CycleOutcome.EXIT_SUCCESS

    def _print_summary_panel(
        self,
        mode: DownloadMode,
        is_playlist: bool,
        base_dir: Path,
        output_template: str,
        archive_path: Path,
        deno_ok: bool,
        mp4_profile: ProfileChoice | None,
    ) -> None:
        """Print session summary before download using a panel."""
        lines = []
        lines.append(f"{paint(t('info_mode'), Colors.YELLOW)} {paint(mode, Colors.GREEN)}")
        lines.append(
            f"{paint(t('info_is_playlist'), Colors.YELLOW)} {paint(is_playlist, Colors.CYAN)}"
        )
        lines.append(
            f"{paint(t('info_output_folder'), Colors.YELLOW)} {paint(base_dir, Colors.WHITE)}"
        )
        lines.append(
            f"{paint(t('info_output_template'), Colors.YELLOW)} "
            f"{paint(output_template, Colors.WHITE)}"
        )
        lines.append(
            f"{paint(t('info_archive_file'), Colors.YELLOW)} {paint(archive_path, Colors.WHITE)}"
        )
        lines.append(
            f"{paint(t('info_log_file'), Colors.YELLOW)} {paint(self.log_path, Colors.WHITE)}"
        )

        deno_status = (
            f"{Colors.GREEN}{t('label_yes')}{Colors.RESET}"
            if deno_ok
            else f"{Colors.RED}{t('label_no')}{Colors.RESET}"
        )
        lines.append(f"{paint(t('info_deno'), Colors.YELLOW)} {deno_status}")

        if mode == DownloadMode.VIDEO:
            profile_name = (
                t("profile_compatibility_short")
                if mp4_profile == ProfileChoice.COMPATIBILITY
                else t("profile_quality_short")
            )
            lines.append(
                f"{paint(t('info_profile'), Colors.YELLOW)} {paint(profile_name, Colors.MAGENTA)}"
            )

        self.ui.print_panel("\n".join(lines), title=t("summary_title"), color=Colors.BLUE)

    def _execute_download(self, plan: DownloadPlan, cmd_builder: CommandBuilder) -> int:
        """Execute download commands and return the final process status."""
        final_rc = 1

        log_path = self.log_path
        if not log_path:
            self.ui.print(t("error_log_uninitialized"))
            return 1

        if plan.mode == DownloadMode.VIDEO:
            if plan.mp4_profile == ProfileChoice.COMPATIBILITY:
                cmd_stage1 = cmd_builder.build_mp4_compatibility_stage1()
                self.ui.print(
                    f"{paint('### ' + t('stage1_title'), Colors.BLUE, Colors.BOLD)} "
                    f"{paint(t('stage1_desc'), Colors.CYAN)}"
                )
                rc1 = run_cmd_tee(cmd_stage1, log_path)
                final_rc = rc1

                if rc1 == 130:
                    return 130
                if rc1 != 0:
                    # Expected whenever an item has no avc1+mp4a rendition --
                    # that is exactly what Stage 2 is for. Not a failure yet.
                    self.ui.print(f"{Colors.YELLOW}{t('stage1_partial')}{Colors.RESET}")

                cmd_stage2 = cmd_builder.build_mp4_compatibility_stage2()
                self.ui.print(
                    f"{paint('### ' + t('stage2_title'), Colors.BLUE, Colors.BOLD)} "
                    f"{paint(t('stage2_desc'), Colors.CYAN)}"
                )
                rc2 = run_cmd_tee(cmd_stage2, log_path)
                final_rc = rc2

                if rc2 == 130:
                    return 130

            else:
                if plan.remux_container == ContainerChoice.MKV:
                    cmd_quality = cmd_builder.build_mp4_quality_mkv()
                    self.ui.print(
                        f"{paint('### ' + t('quality_title'), Colors.MAGENTA, Colors.BOLD)} "
                        f"{paint(t('quality_mkv_desc'), Colors.GREEN)}"
                    )
                    rc = run_cmd_tee(cmd_quality, log_path)
                    final_rc = rc
                else:
                    cmd_quality_mp4 = cmd_builder.build_mp4_quality_remux()
                    self.ui.print(
                        f"{paint('### ' + t('quality_title'), Colors.MAGENTA, Colors.BOLD)} "
                        f"{paint(t('quality_mp4_desc'), Colors.GREEN)}"
                    )
                    rc = run_cmd_tee(cmd_quality_mp4, log_path)
                    final_rc = rc

                if final_rc == 130:
                    return 130
        else:
            cmd_audio = cmd_builder.build_mp3()
            self.ui.print(
                f"{paint('### ' + t('mp3_title'), Colors.GREEN, Colors.BOLD)} "
                f"{paint(t('mp3_desc'), Colors.CYAN)}"
            )
            rc = run_cmd_tee(cmd_audio, log_path)
            final_rc = rc

            if rc == 130:
                return 130

        return final_rc

    def _show_skip_report(self, plan: DownloadPlan, entries: list[PlaylistEntry]) -> None:
        """Show skipped items report."""
        if plan.is_playlist and entries:
            downloaded_ids = read_archive_ids(Path(plan.archive_path))
            skipped = [e for e in entries if e.id and e.id not in downloaded_ids]

            if skipped:
                header = t("skip_report_title")
                rule = "=" * len(header)
                self.ui.print(f"\n{Colors.YELLOW}{Colors.BOLD}{rule}{Colors.RESET}")
                self.ui.print(f"{Colors.YELLOW}{Colors.BOLD}{header}{Colors.RESET}")
                self.ui.print(f"{Colors.YELLOW}{Colors.BOLD}{rule}{Colors.RESET}")

                self.ui.print(t("playlist_analyzing"))

                for e in skipped:
                    idx = e.playlist_index
                    vid = e.id
                    title = e.title
                    vurl = e.watch_url
                    reason = probe_skip_reason(vurl, plan.js_args, run_capture)

                    self.ui.print(f"- #{idx:03d}  ({vid})")
                    self.ui.print(f"  {t('skip_item_title')} {title}")
                    self.ui.print(f"  {t('skip_item_reason')} {reason}\n")
            else:
                self.ui.print("\n" + t("playlist_all_archived"))
