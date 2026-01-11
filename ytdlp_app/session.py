"""Interactive session management for ytdlp_app.

This module handles the main application loop, user interaction, and
download process coordination.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .exec import run_capture, run_cmd_tee
from .i18n import t
from .logging_utils import Colors, append_log, log_error, now_stamp
from .models import (
    ActionChoice,
    AppPaths,
    ContainerChoice,
    DownloadMode,
    DownloadPlan,
    ModeChoice,
    PlaylistChoice,
    ProfileChoice,
    UserConfig,
)
from .playlist import (
    fetch_playlist_entries,
    get_playlist_id,
    is_playlist_url,
    read_archive_ids,
)
from .skip_probe import probe_skip_reason
from .system import deno_available, ffmpeg_available, yt_dlp_available
from .ui import ConsoleUI
from .yt_dlp import CommandBuilder


class InteractiveSession:
    """Manages an interactive download session."""

    def __init__(self, ui: ConsoleUI, config: UserConfig, paths: AppPaths):
        """Initialize the session.

        Args:
            ui: The UI interface.
            config: User configuration.
            paths: Application paths.
        """
        self.ui = ui
        self.config = config
        self.paths = paths
        self.log_path: Path | None = None

    def analyze_log_for_error(self, log_path: Path) -> str:
        """Read the last few lines of the log to find a user-friendly error cause."""
        if not log_path.exists():
            return "Unknown error (Log file not found)."

        try:
            # Read last 20 lines
            with log_path.open("r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()[-20:]

            content = "".join(lines)

            if "is not a valid URL" in content:
                return "The provided input is not a valid URL supported by this tool."
            if "Video unavailable" in content:
                return "The media is unavailable (it might be private, deleted, or region-locked)."
            if "HTTP Error 403" in content:
                return "Access denied (HTTP 403). The site might be blocking the downloader."
            if "Sign in to confirm your age" in content:
                return "Age-restricted content. Cookies might be required."
            if "Unsupported URL" in content:
                return "This URL format is not supported."
            if (
                "Name or service not known" in content
                or "Temporary failure in name resolution" in content
            ):
                return "Network error. Please check your internet connection."

            # Fallback: try to find a line starting with "ERROR:"
            for line in reversed(lines):
                if "ERROR:" in line:
                    # detailed error from yt-dlp
                    return f"Error details: {line.strip().split('ERROR:', 1)[1].strip()}"

            return "An unexpected error occurred during the download."
        except Exception:
            return "Could not analyze error log."

    def handle_error(self, log_path: Path | None) -> bool:
        """Display a friendly error message and ask to continue.

        Returns:
            True if user wants to exit, False if they want to continue/retry.
        """
        if log_path:
            friendly_msg = self.analyze_log_for_error(log_path)
        else:
            friendly_msg = "An unexpected system error occurred."

        self.ui.print(f"\n{Colors.RED}{Colors.BOLD}Download Failed{Colors.RESET}")
        self.ui.print(f"{Colors.YELLOW}Reason: {friendly_msg}{Colors.RESET}")
        if log_path:
            self.ui.print(
                f"\n{Colors.WHITE}For technical details, check the log file:{Colors.RESET}"
            )
            self.ui.print(f"{Colors.WHITE}{log_path}{Colors.RESET}")

        return self.ui.prompt_exit_on_failure()

    def run_loop(self) -> int:
        """Run the main interactive loop.

        Returns:
            Exit code (0 for success).
        """
        try:
            while True:
                if not self._process_one_cycle():
                    return 0
        except KeyboardInterrupt:
            self.ui.print(f"\n>>> {t('status_cancelled')} (Ctrl+C).")
            return 0
        except Exception as ex:
            log_error(None, t("error_unexpected"), ex)
            self.ui.print(t("error_check_logs"))
            if self.handle_error(self.log_path):
                return 0
            return 0

    def _process_one_cycle(self) -> bool:
        """Process one download cycle.

        Returns:
            True to continue loop, False to exit.
        """
        self.log_path = None

        # 1) URL
        url = self.ui.ask_text("\n" + t("prompt_url"))
        if not url:
            self.ui.print(t("error_no_url"))
            return False

        # 2) Mode selection
        mode_choice = self.ui.pick(t("prompt_mode"), [t("mode_video"), t("mode_audio")])
        mode = DownloadMode.VIDEO if mode_choice == ModeChoice.VIDEO else DownloadMode.AUDIO

        # 3) Pre-flight checks
        deno_ok = deno_available()

        if not yt_dlp_available():
            self.ui.print(
                f"{Colors.RED}{Colors.BOLD}ERROR:{Colors.RESET} {Colors.RED}{t('error_ytdlp_not_found')}{Colors.RESET}"
            )
            return False

        if not ffmpeg_available():
            self.ui.print(
                f"\n{Colors.YELLOW}{Colors.BOLD}WARNING:{Colors.RESET} {Colors.YELLOW}{t('error_ffmpeg_not_found')}{Colors.RESET}\n"
                f"{Colors.WHITE}- MP3 mode may fail to convert audio.{Colors.RESET}\n"
                f"{Colors.WHITE}- MP4 mode may fail to merge/recode and attach thumbnails.{Colors.RESET}\n"
                f"{Colors.CYAN}Fix: run install.ps1 or install ffmpeg and add it to PATH.{Colors.RESET}\n"
            )

        if not deno_ok:
            self.ui.print(
                f"\n{Colors.YELLOW}{Colors.BOLD}WARNING:{Colors.RESET} {Colors.YELLOW}Deno runtime not found.{Colors.RESET}\n"
                f"{Colors.WHITE}- Some videos may fail if yt-dlp cannot solve JS challenges.{Colors.RESET}\n"
                f"{Colors.CYAN}- Install Deno (https://deno.com) or rerun install.ps1.{Colors.RESET}\n"
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
        mp4_profile = None
        remux_container = None
        if mode == DownloadMode.VIDEO:
            mp4_profile = self.ui.pick(
                t("prompt_mp4_profile"),
                [
                    t("profile_compatibility"),
                    t("profile_quality"),
                ],
            )
            if mp4_profile == ProfileChoice.QUALITY:
                remux_container = self.ui.pick(
                    t("prompt_container"),
                    [
                        t("container_mkv"),
                        t("container_mp4"),
                    ],
                )

        # 6) Directories and templates
        self.paths.archives_dir.mkdir(parents=True, exist_ok=True)
        self.paths.logs_dir.mkdir(parents=True, exist_ok=True)

        if mode == DownloadMode.VIDEO:
            if is_playlist:
                base_dir = self.config.videos_dir / "yt-dlp"
                output_template = str(
                    base_dir / "%(playlist_title)s" / "%(playlist_index)03d - %(title)s.%(ext)s"
                )
                archive_path = self.paths.archives_dir / f"playlist_{playlist_id}_mp4.txt"
            else:
                base_dir = self.config.videos_dir / "Downloaded Videos"
                output_template = str(base_dir / "%(title)s.%(ext)s")
                archive_path = self.paths.archives_dir / "single_videos_mp4.txt"
        else:
            if is_playlist:
                base_dir = self.config.music_dir / "yt-dlp"
                output_template = str(
                    base_dir / "%(playlist_title)s" / "%(playlist_index)03d - %(title)s.%(ext)s"
                )
                archive_path = self.paths.archives_dir / f"playlist_{playlist_id}_mp3.txt"
            else:
                base_dir = self.config.music_dir / "Downloaded Music"
                output_template = str(base_dir / "%(title)s.%(ext)s")
                archive_path = self.paths.archives_dir / "single_audios_mp3.txt"

        base_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = (
            self.paths.logs_dir
            / f"yt-dlp_{mode}_{'playlist' if is_playlist else 'single'}_{now_stamp()}.log"
        )

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
            self.log_path,
            (
                "\n" + "=" * 80 + "\n"
                f"[{datetime.now().isoformat(timespec='seconds')}] START\n"
                f"mode={mode} is_playlist={is_playlist} url={url}\n"
                f"base_dir={base_dir}\n"
                f"output_template={output_template}\n"
                f"archive_path={archive_path}\n"
                f"ffmpeg_available={ffmpeg_available()} yt_dlp_available={yt_dlp_available()} deno_available={deno_ok}\n"
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
            log_path=self.log_path,
            playlist_flag="--yes-playlist" if is_playlist else "--no-playlist",
            js_args=cmd_builder.js_args,
            stability_args=cmd_builder.stability_args,
            post_args=cmd_builder.build_post_args(mode),
            common_args=cmd_builder.common_args,
        )

        # 8) Playlist mapping
        entries = []
        if plan.is_playlist:
            try:
                entries = fetch_playlist_entries(plan.url, plan.js_args, run_capture)
            except Exception as ex:
                log_error(
                    self.log_path,
                    "Failed to fetch playlist entries (skip report may be partial)",
                    ex,
                )
                self.ui.print(
                    f"Could not fetch playlist entries; skip report may be incomplete.\n{ex}\n"
                )
                if self.ui.prompt_exit_on_failure():
                    return False

        # 9) DOWNLOAD
        final_rc = self._execute_download(plan, cmd_builder)
        if final_rc is None:  # Exited early
            return False

        append_log(
            self.log_path,
            f"\n[INFO {datetime.now().isoformat(timespec='seconds')}] DOWNLOAD_FINISHED returncode={final_rc}\n",
        )

        # 10) Skip report
        self._show_skip_report(plan, entries)

        self.ui.print("\n" + t("tasks_completed"))
        self.ui.print(f"{t('info_log')} {self.log_path}")
        self.ui.print(f"{t('info_config')} {self.paths.config_file}")

        next_action = self.ui.pick(
            t("prompt_next"),
            [
                t("action_download"),
                t("action_exit"),
            ],
        )
        return next_action == ActionChoice.DOWNLOAD_ANOTHER

    def _print_summary_panel(
        self,
        mode: DownloadMode,
        is_playlist: bool,
        base_dir: Path,
        output_template: str,
        archive_path: Path,
        deno_ok: bool,
        mp4_profile: int | None,
    ):
        """Print session summary before download using a panel."""
        lines = []
        lines.append(
            f"{Colors.YELLOW}{t('info_mode')} {Colors.RESET}{Colors.GREEN}{mode}{Colors.RESET}"
        )
        lines.append(
            f"{Colors.YELLOW}{t('info_is_playlist')} {Colors.RESET}{Colors.CYAN}{is_playlist}{Colors.RESET}"
        )
        lines.append(
            f"{Colors.YELLOW}{t('info_output_folder')} {Colors.RESET}{Colors.WHITE}{base_dir}{Colors.RESET}"
        )
        lines.append(
            f"{Colors.YELLOW}{t('info_output_template')} {Colors.RESET}{Colors.WHITE}{output_template}{Colors.RESET}"
        )
        lines.append(
            f"{Colors.YELLOW}{t('info_archive_file')} {Colors.RESET}{Colors.WHITE}{archive_path}{Colors.RESET}"
        )
        lines.append(
            f"{Colors.YELLOW}{t('info_log_file')} {Colors.RESET}{Colors.WHITE}{self.log_path}{Colors.RESET}"
        )

        deno_status = (
            f"{Colors.GREEN}Yes{Colors.RESET}" if deno_ok else f"{Colors.RED}No{Colors.RESET}"
        )
        lines.append(f"{Colors.YELLOW}{t('info_deno')} {Colors.RESET}{deno_status}")

        if mode == DownloadMode.VIDEO:
            profile_name = (
                "Compatibility" if mp4_profile == ProfileChoice.COMPATIBILITY else "Quality"
            )
            lines.append(
                f"{Colors.YELLOW}{t('info_profile')} {Colors.RESET}{Colors.MAGENTA}{profile_name}{Colors.RESET}"
            )

        self.ui.print_panel("\n".join(lines), title="Download Summary", color=Colors.BLUE)

    def _execute_download(self, plan: DownloadPlan, cmd_builder: CommandBuilder) -> int | None:
        """Execute the download commands.

        Returns:
            Final return code, or None if cancelled/failed.
        """
        final_rc: int | None = None

        log_path = self.log_path
        if not log_path:
            self.ui.print("Error: Log path not initialized.")
            return None

        if plan.mode == DownloadMode.VIDEO:
            if plan.mp4_profile == ProfileChoice.COMPATIBILITY:
                cmd_stage1 = cmd_builder.build_mp4_compatibility_stage1()
                self.ui.print(
                    f"{Colors.BLUE}{Colors.BOLD}### {t('stage1_title')}{Colors.RESET} {Colors.CYAN}{t('stage1_desc')}{Colors.RESET}"
                )
                rc1 = run_cmd_tee(cmd_stage1, log_path)
                final_rc = rc1

                if rc1 == 130:
                    return None
                if rc1 != 0 and self.handle_error(log_path):
                    return None

                cmd_stage2 = cmd_builder.build_mp4_compatibility_stage2()
                self.ui.print(
                    f"{Colors.BLUE}{Colors.BOLD}### {t('stage2_title')}{Colors.RESET} {Colors.CYAN}{t('stage2_desc')}{Colors.RESET}"
                )
                rc2 = run_cmd_tee(cmd_stage2, log_path)
                final_rc = rc2

                if rc2 == 130:
                    return None
                if rc2 != 0 and self.handle_error(log_path):
                    return None

            else:
                if plan.remux_container == ContainerChoice.MKV:
                    cmd_quality = cmd_builder.build_mp4_quality_mkv()
                    self.ui.print(
                        f"{Colors.MAGENTA}{Colors.BOLD}### {t('quality_title')}{Colors.RESET} {Colors.GREEN}{t('quality_mkv_desc')}{Colors.RESET}"
                    )
                    rc = run_cmd_tee(cmd_quality, log_path)
                    final_rc = rc
                else:
                    cmd_quality_mp4 = cmd_builder.build_mp4_quality_remux()
                    self.ui.print(
                        f"{Colors.MAGENTA}{Colors.BOLD}### {t('quality_title')}{Colors.RESET} {Colors.GREEN}{t('quality_mp4_desc')}{Colors.RESET}"
                    )
                    rc = run_cmd_tee(cmd_quality_mp4, log_path)
                    final_rc = rc

                if final_rc == 130:
                    return None
                if final_rc != 0 and self.handle_error(log_path):
                    return None
        else:
            cmd_audio = cmd_builder.build_mp3()
            self.ui.print(
                f"{Colors.GREEN}{Colors.BOLD}### {t('mp3_title')}{Colors.RESET} {Colors.CYAN}{t('mp3_desc')}{Colors.RESET}"
            )
            rc = run_cmd_tee(cmd_audio, log_path)
            final_rc = rc

            if rc == 130:
                return None
            if rc != 0 and self.handle_error(log_path):
                return None

        return final_rc

    def _show_skip_report(self, plan: DownloadPlan, entries: list):
        """Show skipped items report."""
        if plan.is_playlist and entries:
            downloaded_ids = read_archive_ids(Path(plan.archive_path))
            skipped = [e for e in entries if e.id and e.id not in downloaded_ids]

            if skipped:
                self.ui.print(
                    f"\n{Colors.YELLOW}{Colors.BOLD}=============================={Colors.RESET}"
                )
                self.ui.print(
                    f"{Colors.YELLOW}{Colors.BOLD}SKIPPED ITEMS (not downloaded){Colors.RESET}"
                )
                self.ui.print(
                    f"{Colors.YELLOW}{Colors.BOLD}=============================={Colors.RESET}"
                )

                for e in skipped:
                    idx = e.playlist_index
                    vid = e.id
                    title = e.title
                    vurl = e.watch_url
                    reason = probe_skip_reason(vurl, plan.js_args, run_capture)

                    self.ui.print(f"- #{idx:03d}  ({vid})")
                    self.ui.print(f"  Title : {title}")
                    self.ui.print(f"  Reason: {reason}\n")
            else:
                self.ui.print("\n" + t("playlist_all_archived"))
