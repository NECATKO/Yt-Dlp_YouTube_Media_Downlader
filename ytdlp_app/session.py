"""Interactive session management for ytdlp_app.

This module handles the main application loop, user interaction, and
download process coordination.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from .archive_audit import run_menu as run_archive_tools
from .config import save_settings
from .exceptions import ValidationError
from .exec import BAN_RETURN_CODE, run_capture, run_cmd_tee
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
from .netctx import LISTING_TIMEOUT_SECONDS, PROBE_TIMEOUT_SECONDS, NetworkContext
from .outcome import RunOutcome, RunStatus, StageReport, describe, evaluate, read_manifest
from .planning import plan_targets
from .playlist import (
    PlaylistListing,
    channel_id_from_url,
    fetch_listing,
    get_playlist_id,
    is_channel_url,
    is_playlist_url,
    is_youtube_host,
    read_archive_ids,
)
from .preflight import (
    ListingStatus,
    PreflightAction,
    PreflightRequest,
    free_bytes,
    guarded_listing,
    run_preflight,
)
from .redact import redact_secrets, register_proxy
from .settings import AppSettings
from .settings_menu import run_settings_menu
from .skip_probe import ProbeStatus, probe_item
from .speedtest import measure_speed
from .system import (
    deno_available,
    ffmpeg_available,
    impersonation_available,
    refresh_tool_cache,
    yt_dlp_available,
)
from .validators import validate_url
from .yt_dlp import CommandBuilder

if TYPE_CHECKING:
    from collections.abc import Callable

    from .preflight import GuardedListing
    from .ui import UI

_T = TypeVar("_T")

#: Typed at the URL prompt to open the settings menu instead of downloading.
SETTINGS_SHORTCUT = "s"

#: Typed at the URL prompt to open the archive tools (check, repair, download again).
ARCHIVE_TOOLS_SHORTCUT = "a"

#: The mode menu, in the order its options are shown.
_MODE_BY_CHOICE = {
    ModeChoice.VIDEO: DownloadMode.VIDEO,
    ModeChoice.AUDIO: DownloadMode.AUDIO,
    ModeChoice.ARCHIVE: DownloadMode.ARCHIVE,
}


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
        ui: UI,
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
        # Anything logged or shown must not reveal the proxy password.
        register_proxy(self.settings.download.proxy)

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

    def report_ban(self) -> None:
        """Tell the user YouTube is blocking us and how to resume."""
        self.ui.print(f"\n{Colors.RED}{Colors.BOLD}{t('ban_detected_title')}{Colors.RESET}")
        self.ui.print(f"{Colors.YELLOW}{t('ban_detected_detail')}{Colors.RESET}")
        self.ui.print(f"{Colors.CYAN}{t('ban_retry_hint')}{Colors.RESET}")
        if self.log_path:
            self.ui.print(f"\n{Colors.WHITE}{t('error_log_hint')}{Colors.RESET}")
            self.ui.print(f"{Colors.WHITE}{self.log_path}{Colors.RESET}")

    def _stop_after_ban(self) -> CycleOutcome:
        """Report a ban and let the user choose between exiting and a new URL."""
        self.report_ban()
        if self.ui.prompt_exit_on_failure():
            return CycleOutcome.EXIT_FAILURE
        return CycleOutcome.CONTINUE

    def _list_playlist(self, fetch: Callable[[], _T], *, archive_mode: bool) -> GuardedListing[_T]:
        """Warn that reading a big listing is slow, then run the request."""
        warning = t("preflight_listing_warning")
        if archive_mode:
            wait = f"{self.settings.archive.sleep_requests:g}"
            warning += t("preflight_listing_warning_wait", seconds=wait)
        self.ui.print(paint(warning, Colors.CYAN))
        return guarded_listing(fetch, self.log_path)

    def _persist_default_height(self, mode: DownloadMode, height: int | None) -> None:
        """Save a resolution cap as the default for its mode.

        Raises:
            OSError: It could not be saved; the default in memory is then the old one.
        """
        previous = (self.settings.archive.max_height, self.settings.video.max_height)
        if mode == DownloadMode.ARCHIVE:
            self.settings.archive.max_height = height
        else:
            self.settings.video.max_height = height
        try:
            save_settings(self.paths.config_file, self.cfg, self.settings)
        except OSError:
            self.settings.archive.max_height, self.settings.video.max_height = previous
            raise

    def _audio_label(self) -> str:
        """How the chosen audio format is named to the user ("MP3", "OPUS", "source format")."""
        fmt = self.settings.audio.audio_format
        return t("audio_format_best") if fmt == "best" else fmt.upper()

    def _channel_key(self, url: str, listing: PlaylistListing | None) -> str:
        """The identifier a channel's archive is keyed by: its real channel id.

        A channel is keyed by its channel id, so the handle URL, the /channel/ URL and any
        tab URL of one channel all resume one archive. The id comes from the URL when it
        carries one, otherwise from the listing that also feeds the size estimate.
        """
        channel_id = channel_id_from_url(url) or (listing.channel_id if listing else None)
        if channel_id is None:
            # Not fatal: fall back to the identifier in the URL, which still
            # resumes correctly as long as the same URL is used again.
            channel_id = get_playlist_id(url)
            self.ui.print(
                f"{paint(t('label_warning'), Colors.YELLOW, Colors.BOLD)} "
                f"{paint(t('archive_channel_id_fallback', id=channel_id), Colors.YELLOW)}"
            )
        return channel_id

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
            if raw.strip().lower() == ARCHIVE_TOOLS_SHORTCUT:
                run_archive_tools(self.ui, self.paths, self.config)
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
        mode_choice = self.ui.pick(
            t("prompt_mode"),
            [t("mode_video"), t("mode_audio", format=self._audio_label()), t("mode_archive")],
        )
        mode = _MODE_BY_CHOICE[ModeChoice(mode_choice)]
        archive_mode = mode == DownloadMode.ARCHIVE

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

        if archive_mode and impersonation_available() is False:
            # Without it every subtitle request fails with HTTP 429, which the
            # ban guard cannot tell apart from a real block.
            self.ui.print(
                f"\n{paint(t('label_warning'), Colors.YELLOW, Colors.BOLD)} "
                f"{paint(t('warn_impersonation_missing'), Colors.YELLOW)}\n"
                f"{paint('- ' + t('warn_impersonation_detail'), Colors.WHITE)}\n"
                f"{paint('- ' + t('warn_impersonation_fix'), Colors.CYAN)}\n"
            )

        # 4) Playlist vs single video
        youtube = is_youtube_host(url)
        if not youtube:
            self.ui.print(paint(t("notice_non_youtube"), Colors.YELLOW))
        # Another site's URL is never a playlist here: the listing, the estimate and the
        # archive naming rest on YouTube's URL forms (see playlist.is_playlist_url).
        playlist_like = is_playlist_url(url)
        # Archiving a channel always means the whole channel: there is no
        # "this video" in a channel URL to fall back to.
        channel_archive = archive_mode and is_channel_url(url)
        force_single = False
        if playlist_like and not channel_archive:
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
        is_channel = is_playlist and is_channel_url(url)
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

        # 6) Directories, and the playlist listing that names the archive
        self.paths.archives_dir.mkdir(parents=True, exist_ok=True)
        self.paths.logs_dir.mkdir(parents=True, exist_ok=True)

        log_path = (
            self.paths.logs_dir
            / f"yt-dlp_{mode}_{'playlist' if is_playlist else 'single'}_{now_stamp()}.log"
        )
        self.log_path = log_path

        network = NetworkContext(self.settings, deno_ok)

        # One flat listing feeds the size estimate, the skip report and, for a channel, the
        # archive file name (its real channel id), so there is no separate channel request.
        # A single item sends none.
        listing: PlaylistListing | None = None
        if is_playlist:
            guarded = self._list_playlist(
                lambda: fetch_listing(
                    url,
                    network.listing_args(archive=archive_mode),
                    lambda cmd: run_capture(cmd, timeout=LISTING_TIMEOUT_SECONDS),
                ),
                archive_mode=archive_mode,
            )
            if guarded.status is ListingStatus.INTERRUPTED:
                return CycleOutcome.INTERRUPTED
            if guarded.status is ListingStatus.BAN:
                # YouTube is already blocking us; the guard has logged it.
                return self._stop_after_ban()
            if guarded.status is ListingStatus.FAILED and not archive_mode:
                self.ui.print(f"{t('playlist_fetch_failed')}\n{redact_secrets(guarded.error)}\n")
                if self.ui.prompt_exit_on_failure():
                    return CycleOutcome.EXIT_FAILURE
            listing = guarded.value

        key = playlist_id
        if is_channel:
            key = self._channel_key(url, listing)
        try:
            targets = plan_targets(
                mode=mode,
                is_playlist=is_playlist,
                is_channel=is_channel,
                key=key,
                config=self.config,
                settings=self.settings,
                archives_dir=self.paths.archives_dir,
                legacy_key=get_playlist_id(url) if is_channel else None,
            )
        except ValidationError as ex:
            self.ui.print(f"{paint(t('label_error'), Colors.RED, Colors.BOLD)} {ex}")
            return CycleOutcome.CONTINUE
        base_dir, output_template, archive_path = (
            targets.base_dir,
            targets.output_template,
            targets.archive_path,
        )
        base_dir.mkdir(parents=True, exist_ok=True)

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
            probe_args=network.probe_args(),
        )

        # 8) The entries. Archive mode never runs the skip report, whose per-item probes
        # are exactly the kind of extra traffic archive mode avoids.
        entries: list[PlaylistEntry] = listing.entries if listing is not None else []
        estimate_entries: list[PlaylistEntry] | None = (
            listing.entries if listing is not None else None
        )

        # 8b) Size estimate, resolution cap and free-space check.
        preflight = run_preflight(
            PreflightRequest(
                mode=mode,
                is_playlist=plan.is_playlist,
                entries=estimate_entries,
                archived_ids=(
                    frozenset(read_archive_ids(archive_path)) if plan.is_playlist else frozenset()
                ),
                mp4_profile=mp4_profile,
                base_dir=base_dir,
                log_path=log_path,
            ),
            ui=self.ui,
            settings=self.settings,
            persist_default=lambda height: self._persist_default_height(mode, height),
            measure=measure_speed,
            disk_free=free_bytes,
        )
        if preflight.action is PreflightAction.CANCEL:
            return CycleOutcome.CONTINUE
        cmd_builder.set_max_height(preflight.max_height)

        # 9) DOWNLOAD, judged by what it left behind rather than by an exit code
        archive_before = read_archive_ids(archive_path)
        report = self._execute_download(plan, cmd_builder)
        outcome = evaluate(
            stage_codes=report.codes,
            archive_before=archive_before,
            archive_after=read_archive_ids(archive_path),
            manifest=read_manifest(cmd_builder.manifest_path),
            expected_ids=[e.id for e in entries if e.id] if plan.is_playlist and listing else None,
            banned=report.banned,
            cancelled=report.cancelled,
        )
        append_log(
            log_path,
            f"\n[INFO {datetime.now().isoformat(timespec='seconds')}] "
            f"DOWNLOAD_FINISHED status={outcome.status} stage_codes={list(report.codes)} "
            f"completed={outcome.completed} already_present={outcome.already_present} "
            f"failed={list(outcome.failed)} missing={list(outcome.missing)} "
            f"failed_unknown={outcome.failed_unknown}\n",
        )

        status = outcome.status
        if status is RunStatus.CANCELLED:
            return CycleOutcome.INTERRUPTED
        if status is RunStatus.BANNED:
            return self._stop_after_ban()
        if status is RunStatus.FAILED:
            self._print_outcome(outcome)
            if self.handle_error(log_path):
                return CycleOutcome.EXIT_FAILURE
            return CycleOutcome.CONTINUE

        # 10) Report, then the skip report (never in archive mode, see step 8)
        self._print_outcome(outcome)
        if not archive_mode:
            skip_stop = self._show_skip_report(plan, entries)
            if skip_stop is ProbeStatus.CANCELLED:
                return CycleOutcome.INTERRUPTED

        self.ui.print(f"{t('info_log')} {log_path}")
        self.ui.print(f"{t('info_config')} {self.paths.config_file}")

        # What "already in the archive" means when the target changes.
        if outcome.already_present:
            self.ui.print(paint(t("archive_records_note"), Colors.CYAN))

        partial = status is RunStatus.PARTIAL
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
        # Leaving after a run that left items undone must not look like a clean exit.
        return CycleOutcome.EXIT_FAILURE if partial else CycleOutcome.EXIT_SUCCESS

    def _print_outcome(self, outcome: RunOutcome) -> None:
        """Show the success, partial-success or failure lines of a run."""
        colors = {
            "ok": (Colors.GREEN, Colors.BOLD),
            "warn": (Colors.YELLOW, Colors.BOLD),
            "error": (Colors.RED, Colors.BOLD),
            "info": (Colors.WHITE,),
        }
        self.ui.print("")
        for kind, text in describe(outcome):
            self.ui.print(paint(text, *colors[kind]))

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
        elif mode == DownloadMode.ARCHIVE:
            pacing = self.settings.archive
            waits = t(
                "info_archive_waits_value",
                requests=f"{pacing.sleep_requests:g}",
                low=f"{pacing.sleep_interval:g}",
                high=f"{max(pacing.max_sleep_interval, pacing.sleep_interval):g}",
                subtitles=f"{pacing.sleep_subtitles:g}",
            )
            lines.append(
                f"{paint(t('info_archive_waits'), Colors.YELLOW)} {paint(waits, Colors.MAGENTA)}"
            )

        self.ui.print_panel("\n".join(lines), title=t("summary_title"), color=Colors.BLUE)

    def _execute_download(self, plan: DownloadPlan, cmd_builder: CommandBuilder) -> StageReport:
        """Run the download command(s) and report how each stage ended.

        Whether the items are done is judged afterwards from the archive and the files
        (see outcome.evaluate); this only says what ran, and whether it was cut short.
        """
        log_path = self.log_path
        if not log_path:
            self.ui.print(t("error_log_uninitialized"))
            return StageReport((1,))

        codes: list[int] = []

        def run(cmd: list[str], *, stop_on_ban: bool = False) -> int:
            rc = run_cmd_tee(cmd, log_path, stop_on_ban=stop_on_ban)
            codes.append(rc)
            return rc

        def report() -> StageReport:
            return StageReport(
                tuple(codes),
                banned=BAN_RETURN_CODE in codes,
                cancelled=130 in codes,
            )

        if plan.mode == DownloadMode.ARCHIVE:
            self.ui.print(
                f"{paint('### ' + t('archive_title'), Colors.MAGENTA, Colors.BOLD)} "
                f"{paint(t('archive_desc'), Colors.CYAN)}"
            )
            run(cmd_builder.build_archive(), stop_on_ban=True)
            return report()

        if plan.mode == DownloadMode.VIDEO:
            if plan.mp4_profile == ProfileChoice.COMPATIBILITY:
                self.ui.print(
                    f"{paint('### ' + t('stage1_title'), Colors.BLUE, Colors.BOLD)} "
                    f"{paint(t('stage1_desc'), Colors.CYAN)}"
                )
                rc1 = run(cmd_builder.build_mp4_compatibility_stage1())
                if rc1 == 130:
                    return report()
                if rc1 != 0:
                    # Expected whenever an item has no avc1+mp4a rendition --
                    # that is exactly what Stage 2 is for. Not a failure yet: an item
                    # that stage 1 could not finish is not in the archive, so stage 2
                    # picks it up, and evaluate() judges the result, not this code.
                    self.ui.print(f"{Colors.YELLOW}{t('stage1_partial')}{Colors.RESET}")

                self.ui.print(
                    f"{paint('### ' + t('stage2_title'), Colors.BLUE, Colors.BOLD)} "
                    f"{paint(t('stage2_desc'), Colors.CYAN)}"
                )
                run(cmd_builder.build_mp4_compatibility_stage2())
            elif plan.remux_container == ContainerChoice.MKV:
                self.ui.print(
                    f"{paint('### ' + t('quality_title'), Colors.MAGENTA, Colors.BOLD)} "
                    f"{paint(t('quality_mkv_desc'), Colors.GREEN)}"
                )
                run(cmd_builder.build_mp4_quality_mkv())
            else:
                self.ui.print(
                    f"{paint('### ' + t('quality_title'), Colors.MAGENTA, Colors.BOLD)} "
                    f"{paint(t('quality_mp4_desc'), Colors.GREEN)}"
                )
                run(cmd_builder.build_mp4_quality_remux())
            return report()

        label = self._audio_label()
        self.ui.print(
            f"{paint('### ' + t('audio_title', format=label), Colors.GREEN, Colors.BOLD)} "
            f"{paint(t('audio_desc', format=label), Colors.CYAN)}"
        )
        run(cmd_builder.build_mp3())
        return report()

    def _show_skip_report(
        self, plan: DownloadPlan, entries: list[PlaylistEntry]
    ) -> ProbeStatus | None:
        """Show skipped items report.

        Returns:
            CANCELLED when the user cancelled, BANNED when YouTube started blocking the
            probes (both end the report at once: going on would either start the requests
            just cancelled or extend the block), None when it ran to the end.
        """
        if not (plan.is_playlist and entries):
            return None
        downloaded_ids = read_archive_ids(Path(plan.archive_path))
        skipped = [e for e in entries if e.id and e.id not in downloaded_ids]

        if not skipped:
            self.ui.print("\n" + t("playlist_all_archived"))
            return None

        header = t("skip_report_title")
        rule = "=" * len(header)
        self.ui.print(f"\n{Colors.YELLOW}{Colors.BOLD}{rule}{Colors.RESET}")
        self.ui.print(f"{Colors.YELLOW}{Colors.BOLD}{header}{Colors.RESET}")
        self.ui.print(f"{Colors.YELLOW}{Colors.BOLD}{rule}{Colors.RESET}")

        self.ui.print(t("playlist_analyzing"))

        def bounded(cmd: list[str]) -> tuple[int, str, str]:
            return run_capture(cmd, timeout=PROBE_TIMEOUT_SECONDS)

        for e in skipped:
            result = probe_item(e.watch_url, plan.probe_args, bounded)
            if result.status is ProbeStatus.CANCELLED:
                self.ui.print(f"\n>>> {t('status_cancelled')} (Ctrl+C).")
                return ProbeStatus.CANCELLED
            if result.status is ProbeStatus.BANNED:
                self.report_ban()
                return ProbeStatus.BANNED

            self.ui.print(f"- #{e.playlist_index:03d}  ({e.id})")
            self.ui.print(f"  {t('skip_item_title')} {e.title}")
            self.ui.print(f"  {t('skip_item_reason')} {redact_secrets(result.text)}\n")
        return None
