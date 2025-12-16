from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from .config import ensure_dirs_interactive, load_config, save_config
from .exceptions import InvalidURLError, PlaylistFetchError
from .exec import run_capture, run_cmd_tee
from .locales import get_language, set_language, t
from .logging_utils import append_log, log_error, now_stamp
from .models import AppPaths, DownloadPlan, UserConfig
from .playlist import (
    fetch_playlist_entries,
    get_playlist_id,
    is_playlist_url,
    read_archive_ids,
)
from .skip_probe import probe_skip_reason
from .system import deno_available, ffmpeg_available, yt_dlp_available
from .ui import ConsoleUI
from .validators import validate_url
from .yt_dlp import (
    build_common_args,
    build_js_args,
    build_mp3_cmd,
    build_mp4_compatibility_stage1_cmd,
    build_mp4_compatibility_stage2_cmd,
    build_mp4_quality_mkv_cmd,
    build_mp4_quality_mp4_remux_cmd,
    build_post_args,
    build_stability_args,
)


def _resolve_app_dir() -> Path:
    # Portable behavior: prefer the script location (downloader.py).
    try:
        argv0 = Path(sys.argv[0]) if sys.argv else None
        if argv0 and argv0.suffix.lower() == ".py":
            return argv0.resolve().parent
    except Exception:
        pass
    # Fallback: repository layout (package sits under app root).
    return Path(__file__).resolve().parent.parent


def run() -> int:
    app_name = "yt-dlp-downloader"
    app_dir = _resolve_app_dir()
    paths = AppPaths(
        app_dir=app_dir,
        config_file=app_dir / "config.json",
        logs_dir=app_dir / "logs",
        archives_dir=app_dir / "archives",
    )

    ui = ConsoleUI()

    try:
        # 0) config: load or create paths (once)
        cfg = load_config(paths.config_file)
        
        # Language setup
        saved_lang = cfg.get("language", "")
        if saved_lang in ("en", "tr"):
            set_language(saved_lang)
        else:
            # First run: ask for language
            lang_choice = ui.pick(
                t("prompt_language"),
                [t("opt_english"), t("opt_turkish")],
            )
            selected_lang = "en" if lang_choice == 1 else "tr"
            set_language(selected_lang)
            cfg["language"] = selected_lang
            save_config(paths.config_file, cfg)
        
        videos_base, music_base, _cfg = ensure_dirs_interactive(
            ui, cfg, config_file=paths.config_file, app_name=app_name
        )
        user_config = UserConfig(
            app=str((_cfg.get("app") or app_name)),
            videos_dir=videos_base,
            music_dir=music_base,
            saved_at=(_cfg.get("saved_at") or None),
        )

        while True:
            log_path: Path | None = None

            # 1) URL with validation
            url = ui.ask_text("\n" + t("prompt_url"))
            if not url:
                ui.print(t("no_url_provided"))
                return 0

            # Validate URL
            try:
                url = validate_url(url)
            except InvalidURLError as e:
                ui.print(f"\n{t('error_invalid_url')}")
                ui.print(f"  {e.reason}\n")
                continue

            # 2) Mode selection
            mode_choice = ui.pick(
                t("prompt_download_type"), 
                [t("opt_video_mp4"), t("opt_audio_mp3")]
            )
            mode = "mp4" if mode_choice == 1 else "mp3"

            # 3) Pre-flight checks (install.ps1 should handle, but check anyway)
            deno_ok = deno_available()

            if not yt_dlp_available():
                ui.print(t("error_yt_dlp_not_found"))
                return 0

            if not ffmpeg_available():
                ui.print("\n" + t("warn_ffmpeg_not_found") + "\n")

            if not deno_ok:
                ui.print("\n" + t("warn_deno_not_found") + "\n")

            # 4) Playlist vs single video
            playlist_like = is_playlist_url(url)
            force_single = False
            if playlist_like:
                what = ui.pick(
                    t("prompt_playlist_action"),
                    [
                        t("opt_download_playlist"),
                        t("opt_download_single"),
                    ],
                )
                if what == 2:
                    force_single = True

            is_playlist = playlist_like and (not force_single)
            playlist_id = get_playlist_id(url) if is_playlist else None

            # 5) MP4 profile
            mp4_profile = None
            remux_container = None
            if mode == "mp4":
                mp4_profile = ui.pick(
                    t("prompt_mp4_profile"),
                    [
                        t("opt_mp4_compatibility"),
                        t("opt_mp4_quality"),
                    ],
                )
                if mp4_profile == 2:
                    remux_container = ui.pick(
                        t("prompt_container"),
                        [
                            t("opt_container_mkv"),
                            t("opt_container_mp4"),
                        ],
                    )

            # 6) Directories and templates
            paths.archives_dir.mkdir(parents=True, exist_ok=True)
            paths.logs_dir.mkdir(parents=True, exist_ok=True)

            if mode == "mp4":
                if is_playlist:
                    base_dir = user_config.videos_dir / "yt-dlp"
                    output_template = str(
                        base_dir
                        / "%(playlist_title)s"
                        / "%(playlist_index)03d - %(title)s.%(ext)s"
                    )
                    archive_path = (
                        paths.archives_dir / f"playlist_{playlist_id}_mp4.txt"
                    )
                else:
                    base_dir = user_config.videos_dir / "Downloaded Videos"
                    output_template = str(base_dir / "%(title)s.%(ext)s")
                    archive_path = paths.archives_dir / "single_videos_mp4.txt"
            else:
                if is_playlist:
                    base_dir = user_config.music_dir / "yt-dlp"
                    output_template = str(
                        base_dir
                        / "%(playlist_title)s"
                        / "%(playlist_index)03d - %(title)s.%(ext)s"
                    )
                    archive_path = (
                        paths.archives_dir / f"playlist_{playlist_id}_mp3.txt"
                    )
                else:
                    base_dir = user_config.music_dir / "Downloaded Music"
                    output_template = str(base_dir / "%(title)s.%(ext)s")
                    archive_path = paths.archives_dir / "single_audios_mp3.txt"

            base_dir.mkdir(parents=True, exist_ok=True)
            log_path = (
                paths.logs_dir
                / f"yt-dlp_{mode}_{'playlist' if is_playlist else 'single'}_{now_stamp()}.log"
            )

            yes_no = lambda b: t("info_yes") if b else t("info_no")
            ui.print("\n------------------------------")
            ui.print(f"{t('info_mode')}: {mode}")
            ui.print(f"{t('info_is_playlist')}: {yes_no(is_playlist)}")
            ui.print(f"{t('info_output_folder')}: {base_dir}")
            ui.print(f"{t('info_output_template')}: {output_template}")
            ui.print(f"{t('info_archive_file')}: {archive_path}")
            ui.print(f"{t('info_log_file')}: {log_path}")
            ui.print(f"{t('info_deno_available')}: {yes_no(deno_ok)}")
            if mode == "mp4":
                profile_name = t('info_compatibility') if mp4_profile == 1 else t('info_quality')
                ui.print(f"{t('info_mp4_profile')}: {profile_name}")
            ui.print("------------------------------\n")

            append_log(
                log_path,
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

            # 7) yt-dlp arguments
            playlist_flag = "--yes-playlist" if is_playlist else "--no-playlist"
            js_args = build_js_args(use_deno=deno_ok)
            stability_args = build_stability_args()
            common_args = build_common_args(
                output_template=output_template,
                archive_path=archive_path,
                playlist_flag=playlist_flag,
                url=url,
            )
            post_args = build_post_args(mode)

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
                playlist_flag=playlist_flag,
                js_args=js_args,
                stability_args=stability_args,
                post_args=post_args,
                common_args=common_args,
            )

            # 8) Playlist mapping (skip report)
            entries = []
            if plan.is_playlist:
                try:
                    entries = fetch_playlist_entries(
                        plan.url, plan.js_args, run_capture
                    )
                except PlaylistFetchError as ex:
                    log_error(
                        log_path,
                        f"Failed to fetch playlist entries (returncode={ex.returncode})",
                        ex,
                    )
                    ui.print(f"\n{t('error_playlist_fetch')}")
                    ui.print(f"  returncode={ex.returncode}\n")
                    if ui.prompt_exit_on_failure():
                        return 0
                except Exception as ex:
                    log_error(
                        log_path,
                        "Failed to fetch playlist entries (skip report may be partial)",
                        ex,
                    )
                    ui.print(f"\n{t('error_playlist_fetch')}\n  {ex}\n")
                    if ui.prompt_exit_on_failure():
                        return 0

            # 9) DOWNLOAD
            final_rc: int | None = None

            if mode == "mp4":
                if mp4_profile == 1:
                    cmd_stage1 = build_mp4_compatibility_stage1_cmd(
                        stability_args=plan.stability_args,
                        js_args=plan.js_args,
                        post_args=plan.post_args,
                        common_args=plan.common_args,
                    )
                    ui.print(t("stage_compat_1"))
                    rc1 = run_cmd_tee(cmd_stage1, log_path)
                    final_rc = rc1
                    if rc1 == 130:
                        return 0
                    if rc1 != 0 and ui.prompt_exit_on_failure():
                        return 0

                    cmd_stage2 = build_mp4_compatibility_stage2_cmd(
                        stability_args=plan.stability_args,
                        js_args=plan.js_args,
                        post_args=plan.post_args,
                        common_args=plan.common_args,
                    )
                    ui.print(t("stage_compat_2"))
                    rc2 = run_cmd_tee(cmd_stage2, log_path)
                    final_rc = rc2
                    if rc2 == 130:
                        return 0
                    if rc2 != 0 and ui.prompt_exit_on_failure():
                        return 0

                else:
                    if remux_container == 1:
                        cmd_quality = build_mp4_quality_mkv_cmd(
                            stability_args=plan.stability_args,
                            js_args=plan.js_args,
                            post_args=plan.post_args,
                            common_args=plan.common_args,
                        )
                        ui.print(t("stage_quality_mkv"))
                        rc = run_cmd_tee(cmd_quality, log_path)
                        final_rc = rc
                        if rc == 130:
                            return 0
                        if rc != 0 and ui.prompt_exit_on_failure():
                            return 0
                    else:
                        cmd_quality_mp4 = build_mp4_quality_mp4_remux_cmd(
                            stability_args=plan.stability_args,
                            js_args=plan.js_args,
                            post_args=plan.post_args,
                            common_args=plan.common_args,
                        )
                        ui.print(t("stage_quality_mp4"))
                        rc = run_cmd_tee(cmd_quality_mp4, log_path)
                        final_rc = rc
                        if rc == 130:
                            return 0
                        if rc != 0 and ui.prompt_exit_on_failure():
                            return 0
            else:
                cmd_audio = build_mp3_cmd(
                    stability_args=plan.stability_args,
                    js_args=plan.js_args,
                    post_args=plan.post_args,
                    common_args=plan.common_args,
                )
                ui.print(t("stage_mp3"))
                rc = run_cmd_tee(cmd_audio, log_path)
                final_rc = rc
                if rc == 130:
                    return 0
                if rc != 0 and ui.prompt_exit_on_failure():
                    return 0

            append_log(
                log_path,
                f"\n[INFO {datetime.now().isoformat(timespec='seconds')}] DOWNLOAD_FINISHED returncode={final_rc}\n",
            )

            # 10) Skip report
            if plan.is_playlist and entries:
                downloaded_ids = read_archive_ids(Path(plan.archive_path))
                skipped = [e for e in entries if e.id and e.id not in downloaded_ids]

                if skipped:
                    ui.print("\n==============================")
                    ui.print(t("skip_report_header"))
                    ui.print("==============================")

                    for e in skipped:
                        idx = e.playlist_index
                        vid = e.id
                        title = e.title
                        vurl = e.watch_url
                        reason = probe_skip_reason(vurl, plan.js_args, run_capture)

                        ui.print(f"- #{idx:03d}  ({vid})")
                        ui.print(f"  {t('skip_report_title')} : {title}")
                        ui.print(f"  {t('skip_report_reason')}: {reason}\n")
                else:
                    ui.print("\n" + t("skip_report_none"))

            ui.print("\n" + t("all_tasks_completed"))
            ui.print(f"{t('info_log')}: {log_path}")
            ui.print(f"{t('info_config')}: {paths.config_file}")

            next_action = ui.pick(
                t("prompt_what_next"),
                [
                    t("opt_download_another"),
                    t("opt_exit"),
                ],
            )
            if next_action != 1:
                return 0

    except KeyboardInterrupt:
        ui.print("\n>>> " + t("operation_cancelled"))
        return 0
    except Exception as ex:
        log_error(None, "Unexpected error (top-level)", ex)
        ui.print(t("error_unexpected"))
        if ui.prompt_exit_on_failure():
            return 0
        return 0
