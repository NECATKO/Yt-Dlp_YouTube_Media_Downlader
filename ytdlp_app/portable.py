"""Portable runtime: Python, ffmpeg and Deno living inside the app folder.

The launchers (Run.bat / run.sh) fetch a relocatable Python into runtime/python
and then run this module with it:

    runtime/python/python -s -m ytdlp_app.portable ensure

which installs yt-dlp into that Python and downloads ffmpeg and Deno into
runtime/, each checked against the sha256 pinned in runtime.lock. Nothing is
installed system-wide and no administrator rights are needed, so the whole
folder can be moved to another machine or a USB stick and keeps working.

At startup the app calls configure_environment(), which puts the bundled tools
first on PATH and keeps yt-dlp's and Deno's caches inside the folder too.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import platform
import re
import shutil
import ssl
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from .atomic import atomic_write_text

if TYPE_CHECKING:
    from collections.abc import Callable, MutableMapping, Sequence

RUNTIME_DIR_NAME = "runtime"
CACHE_DIR_NAME = "cache"
LOCK_FILE_NAME = "runtime.lock"

#: yt-dlp is upgraded at launch once its last install is older than this.
YTDLP_UPDATE_DAYS = 7

#: The pip requirement for yt-dlp. "default" adds the optional dependencies
#: yt-dlp recommends, including its JS challenge solver scripts. "curl-cffi"
#: adds browser impersonation: yt-dlp requests every YouTube subtitle with it,
#: and without it YouTube answers those requests with HTTP 429.
YTDLP_REQUIREMENT = "yt-dlp[default,curl-cffi]>=2025.11.12"

#: Components downloaded from runtime.lock by this module. Python is fetched by
#: the launcher scripts, since nothing can run this module before it exists.
DOWNLOADED_COMPONENTS = ("ffmpeg", "deno")

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CHUNK_SIZE = 1024 * 1024
_DOWNLOAD_TIMEOUT = 60

_ARCH_ALIASES = {
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "x64": "x86_64",
    "aarch64": "aarch64",
    "arm64": "aarch64",
}


class PortableError(Exception):
    """The portable runtime could not be set up."""


@dataclass(frozen=True, slots=True)
class LockEntry:
    """One pinned download from runtime.lock."""

    component: str
    platform: str
    sha256: str
    url: str

    @property
    def filename(self) -> str:
        return self.url.rsplit("/", 1)[-1]


def platform_key(system: str | None = None, machine: str | None = None) -> str | None:
    """Return the runtime.lock platform key for this machine, e.g. "windows-x86_64".

    Returns None for operating systems the portable runtime does not cover
    (macOS keeps using the system installation).
    """
    os_name = (system if system is not None else platform.system()).lower()
    arch = _ARCH_ALIASES.get((machine if machine is not None else platform.machine()).lower())
    if os_name not in ("windows", "linux") or arch is None:
        return None
    return f"{os_name}-{arch}"


def parse_lock(text: str) -> list[LockEntry]:
    """Parse runtime.lock, rejecting anything that is not a well-formed pin."""
    entries: list[LockEntry] = []
    for number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 4:
            raise PortableError(f"{LOCK_FILE_NAME}:{number}: expected 4 fields, got {len(fields)}")
        component, key, sha256, url = fields
        if not _SHA256_RE.match(sha256):
            raise PortableError(f"{LOCK_FILE_NAME}:{number}: invalid sha256")
        if not url.startswith("https://"):
            raise PortableError(f"{LOCK_FILE_NAME}:{number}: only https URLs are allowed")
        entries.append(LockEntry(component, key, sha256, url))
    return entries


def find_entry(entries: Sequence[LockEntry], component: str, key: str) -> LockEntry:
    """Return the pin for a component on a platform."""
    for entry in entries:
        if entry.component == component and entry.platform == key:
            return entry
    raise PortableError(f"{LOCK_FILE_NAME} has no {component} build for {key}")


@dataclass(frozen=True, slots=True)
class RuntimeLayout:
    """Where every portable piece lives inside the app folder."""

    app_dir: Path
    windows: bool = sys.platform == "win32"

    @property
    def runtime_dir(self) -> Path:
        return self.app_dir / RUNTIME_DIR_NAME

    @property
    def cache_dir(self) -> Path:
        return self.app_dir / CACHE_DIR_NAME

    @property
    def lock_file(self) -> Path:
        return self.app_dir / LOCK_FILE_NAME

    @property
    def state_file(self) -> Path:
        return self.runtime_dir / "state.json"

    @property
    def python_exe(self) -> Path:
        if self.windows:
            return self.runtime_dir / "python" / "python.exe"
        return self.runtime_dir / "python" / "bin" / "python3"

    def component_dir(self, component: str) -> Path:
        return self.runtime_dir / component

    def component_exe(self, component: str) -> Path:
        suffix = ".exe" if self.windows else ""
        return self.component_dir(component) / f"{component}{suffix}"


def configure_environment(
    app_dir: Path,
    environ: MutableMapping[str, str] | None = None,
    *,
    windows: bool = sys.platform == "win32",
) -> None:
    """Make every tool the app launches use the portable runtime and caches.

    Bundled ffmpeg and Deno go first on PATH, so both the app's own checks and
    yt-dlp find them before any system copy. yt-dlp keeps its cache (including
    the downloaded JS challenge solver) under $XDG_CACHE_HOME on every OS, and
    Deno under $DENO_DIR; both are pointed into the app folder so nothing is
    written to the user profile.
    """
    env = os.environ if environ is None else environ
    layout = RuntimeLayout(app_dir, windows=windows)

    bundled = [
        str(layout.component_dir(name))
        for name in DOWNLOADED_COMPONENTS
        if layout.component_exe(name).exists()
    ]
    if bundled:
        current = env.get("PATH", "")
        env["PATH"] = os.pathsep.join([*bundled, current] if current else bundled)

    env["XDG_CACHE_HOME"] = str(layout.cache_dir)
    env["DENO_DIR"] = str(layout.cache_dir / "deno")


# -- state ------------------------------------------------------------------


def load_state(layout: RuntimeLayout) -> dict[str, Any]:
    """Read runtime/state.json, treating a missing or corrupt file as empty."""
    try:
        data = json.loads(layout.state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(layout: RuntimeLayout, state: dict[str, Any]) -> None:
    """Write runtime/state.json atomically: an interruption keeps the previous file."""
    atomic_write_text(layout.state_file, json.dumps(state, indent=2))


# -- download and unpack ----------------------------------------------------


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ssl_context() -> ssl.SSLContext:
    """Build a TLS context that works with a relocatable Python.

    A relocated OpenSSL may not find the distribution's CA bundle, so prefer
    certifi (installed with yt-dlp), then pip's vendored copy, then the default.
    """
    for module in ("certifi", "pip._vendor.certifi"):
        try:
            where = __import__(module, fromlist=["where"]).where
        except ImportError:
            continue
        return ssl.create_default_context(cafile=where())
    return ssl.create_default_context()


def _print_progress(label: str, done: int, total: int) -> None:
    if total > 0:
        percent = done * 100 // total
        text = f"  {label}: {percent:3d}% ({done >> 20}/{total >> 20} MB)"
    else:
        text = f"  {label}: {done >> 20} MB"
    print(f"\r{text}", end="", flush=True)


def download(
    entry: LockEntry,
    dest: Path,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
    progress: Callable[[str, int, int], None] | None = _print_progress,
) -> Path:
    """Download a pinned file and verify its sha256.

    The file is written to a ".part" name and only renamed into place after the
    checksum matches, so a failed or tampered download never looks complete.

    Raises:
        PortableError: The download failed or the checksum did not match.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")
    digest = hashlib.sha256()
    label = f"{entry.component} ({entry.filename})"

    request = urllib.request.Request(entry.url, headers={"User-Agent": "ytdlp-downloader"})
    try:
        with (
            opener(request, timeout=_DOWNLOAD_TIMEOUT, context=_ssl_context()) as response,
            partial.open("wb") as out,
        ):
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            while chunk := response.read(_CHUNK_SIZE):
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress:
                    progress(label, done, total)
        if progress:
            print()
    except OSError as ex:
        partial.unlink(missing_ok=True)
        raise PortableError(f"Download failed: {entry.url}: {ex}") from ex

    if digest.hexdigest() != entry.sha256:
        partial.unlink(missing_ok=True)
        raise PortableError(
            f"Checksum mismatch for {entry.filename}: expected {entry.sha256}, "
            f"got {digest.hexdigest()}. The file was discarded."
        )
    partial.replace(dest)
    return dest


def _wanted_members(component: str, name: str) -> bool:
    """Decide which archive members a component needs.

    ffmpeg builds put the executables (and, for shared builds, their DLLs) in
    a bin/ folder; the Deno archive holds the bare executable. ffplay, a media
    player the app never uses, is skipped: it is a third of the static build.
    """
    path = PurePosixPath(name)
    if component == "ffmpeg":
        in_bin = len(path.parts) >= 2 and path.parts[-2] == "bin"
        return in_bin and not path.name.startswith("ffplay")
    if component == "deno":
        return path.name in ("deno", "deno.exe")
    raise PortableError(f"Unknown component: {component}")


def _safe_name(name: str) -> str | None:
    """Return the bare file name of a member, or None if it is unusable.

    Members are flattened into the target folder by file name, which rules
    out path traversal regardless of what the archive contains.
    """
    base = PurePosixPath(name.replace("\\", "/")).name
    if base in ("", ".", ".."):
        return None
    return base


def extract_component(component: str, archive: Path, target: Path, *, windows: bool) -> None:
    """Unpack a component into target, replacing any previous copy.

    Files are unpacked into a sibling folder first and swapped in at the end,
    so an interrupted extraction leaves the old copy working.
    """
    staging = target.with_name(target.name + ".new")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)

    extracted = 0
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                if info.is_dir() or not _wanted_members(component, info.filename):
                    continue
                base = _safe_name(info.filename)
                if base is None:
                    continue
                with zf.open(info) as src, (staging / base).open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                extracted += 1
    else:
        with tarfile.open(archive) as tf:
            for member in tf.getmembers():
                if not member.isfile() or not _wanted_members(component, member.name):
                    continue
                base = _safe_name(member.name)
                member_file = tf.extractfile(member)
                if base is None or member_file is None:
                    continue
                with member_file, (staging / base).open("wb") as dst:
                    shutil.copyfileobj(member_file, dst)
                extracted += 1

    exe = staging / f"{component}{'.exe' if windows else ''}"
    if extracted == 0 or not exe.exists():
        shutil.rmtree(staging, ignore_errors=True)
        raise PortableError(f"{archive.name} does not contain {exe.name}")

    if not windows:
        for path in staging.iterdir():
            path.chmod(0o755)

    swap_in(staging, target)


def _backup_of(target: Path) -> Path:
    return target.with_name(target.name + ".old")


def swap_in(staging: Path, target: Path) -> None:
    """Put a fully prepared folder in place of ``target`` without a gap.

    The old copy is not deleted first: it is renamed to ``<name>.old``, the new one is
    renamed into place, and only then is the old one removed. If the new rename fails the
    old copy is put back. A crash between the two renames leaves the old copy at
    ``.old``, which recover_component() restores on the next run, so at no point is
    there neither a working component nor a way back to one.
    """
    backup = _backup_of(target)
    shutil.rmtree(backup, ignore_errors=True)
    had_old = target.exists()
    if had_old:
        target.rename(backup)
    try:
        staging.rename(target)
    except BaseException:
        if had_old:
            shutil.rmtree(target, ignore_errors=True)
            backup.rename(target)
        shutil.rmtree(staging, ignore_errors=True)
        raise
    shutil.rmtree(backup, ignore_errors=True)


def recover_component(target: Path) -> None:
    """Undo a swap that was interrupted between its two renames.

    If ``<name>.old`` is left over and the component is missing, the old copy goes back;
    if the component is there, the leftover is stale and is removed.
    """
    backup = _backup_of(target)
    if not backup.exists():
        return
    if target.exists():
        shutil.rmtree(backup, ignore_errors=True)
    else:
        backup.rename(target)


def ensure_component(
    component: str,
    layout: RuntimeLayout,
    entries: Sequence[LockEntry],
    key: str,
    state: dict[str, Any],
    *,
    downloader: Callable[[LockEntry, Path], Path] = download,
) -> bool:
    """Install a component unless the pinned build is already in place.

    Returns:
        True if it was (re)installed, False if it was already current.
    """
    entry = find_entry(entries, component, key)
    recover_component(layout.component_dir(component))
    installed = state.setdefault("components", {}).get(component, {})
    if installed.get("sha256") == entry.sha256 and layout.component_exe(component).exists():
        return False

    print(f"Installing {component} into {layout.component_dir(component)}", flush=True)
    archive = downloader(entry, layout.runtime_dir / "downloads" / entry.filename)
    try:
        extract_component(
            component, archive, layout.component_dir(component), windows=layout.windows
        )
    finally:
        archive.unlink(missing_ok=True)

    state["components"][component] = {"sha256": entry.sha256, "url": entry.url}
    save_state(layout, state)
    return True


# -- yt-dlp -----------------------------------------------------------------


def _pip_install(python_exe: Path, runner: Callable[..., Any]) -> bool:
    cmd = [
        str(python_exe),
        "-s",
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--disable-pip-version-check",
        "--no-warn-script-location",
        "--no-cache-dir",
        YTDLP_REQUIREMENT,
    ]
    env = {**os.environ, "PYTHONNOUSERSITE": "1"}
    return bool(runner(cmd, env=env, check=False).returncode == 0)


def ytdlp_installed(python_exe: Path, runner: Callable[..., Any] = subprocess.run) -> bool:
    result = runner(
        [str(python_exe), "-s", "-c", "import yt_dlp"],
        check=False,
        capture_output=True,
    )
    return bool(result.returncode == 0)


def ensure_ytdlp(
    layout: RuntimeLayout,
    state: dict[str, Any],
    *,
    update_days: int = YTDLP_UPDATE_DAYS,
    now: datetime | None = None,
    runner: Callable[..., Any] = subprocess.run,
    force_update: bool = False,
) -> None:
    """Install yt-dlp into the portable Python, upgrading it when it is stale.

    An install made for a different YTDLP_REQUIREMENT (for example before an
    extra was added) counts as stale, so the missing extra arrives on the next
    launch rather than a week later.

    A failed first install is fatal: the app cannot work without yt-dlp. A
    failed scheduled upgrade is not, since the installed copy may still work (and
    the machine may simply be offline). A failed upgrade the user asked for
    (``force_update``) is an error, so "update yt-dlp now" never reports success
    when nothing was updated.

    Raises:
        PortableError: The first install, or a forced upgrade, failed.
    """
    current = now or datetime.now()
    python_exe = layout.python_exe

    if not ytdlp_installed(python_exe, runner):
        print("Installing yt-dlp...", flush=True)
        if not _pip_install(python_exe, runner):
            raise PortableError("pip could not install yt-dlp; check the internet connection")
    else:
        last = state.get("ytdlp_updated_at")
        try:
            stale = current - datetime.fromisoformat(str(last)) >= timedelta(days=update_days)
        except ValueError:
            # Never recorded ("None") or unreadable: update to be safe.
            stale = True
        if state.get("ytdlp_requirement") != YTDLP_REQUIREMENT:
            stale = True
        if not (force_update or stale):
            return
        print("Updating yt-dlp...", flush=True)
        if not _pip_install(python_exe, runner):
            if force_update:
                raise PortableError(
                    "yt-dlp could not be updated; the installed version is unchanged"
                )
            print("WARNING: yt-dlp could not be updated; using the installed version.", flush=True)
            return

    state["ytdlp_updated_at"] = current.isoformat(timespec="seconds")
    state["ytdlp_requirement"] = YTDLP_REQUIREMENT
    save_state(layout, state)


# -- entry point ------------------------------------------------------------


def ensure(layout: RuntimeLayout, *, update_days: int, force_ytdlp_update: bool = False) -> None:
    """Bring the portable runtime up to runtime.lock."""
    key = platform_key()
    if key is None:
        raise PortableError(
            f"The portable runtime supports Windows and Linux on x86_64/aarch64, "
            f"not {platform.system()} {platform.machine()}"
        )
    if not layout.python_exe.exists():
        raise PortableError(
            f"{layout.python_exe} is missing; run install.ps1 / install.sh to set it up"
        )

    entries = parse_lock(layout.lock_file.read_text(encoding="utf-8"))
    state = load_state(layout)

    # yt-dlp first: it brings certifi, which the downloads below use for TLS.
    # This process already runs the portable Python, so a fresh import finds it.
    ensure_ytdlp(layout, state, update_days=update_days, force_update=force_ytdlp_update)
    importlib.invalidate_caches()
    for component in DOWNLOADED_COMPONENTS:
        ensure_component(component, layout, entries, key, state)


def _status(layout: RuntimeLayout) -> None:
    state = load_state(layout)
    print(f"App folder : {layout.app_dir}")
    print(f"Platform   : {platform_key() or 'unsupported'}")
    python_ok = "ok" if layout.python_exe.exists() else "missing"
    print(f"Python     : {layout.python_exe} ({python_ok})")
    for component in DOWNLOADED_COMPONENTS:
        exe = layout.component_exe(component)
        print(f"{component:<11}: {exe} ({'ok' if exe.exists() else 'missing'})")
    print(f"yt-dlp     : last updated {state.get('ytdlp_updated_at', 'never')}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ytdlp_app.portable",
        description="Set up or update the portable runtime next to downloader.py.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    ensure_parser = sub.add_parser("ensure", help="install whatever is missing or outdated")
    ensure_parser.add_argument(
        "--update-days",
        type=int,
        default=YTDLP_UPDATE_DAYS,
        help="upgrade yt-dlp when it was last updated this many days ago (default: %(default)s)",
    )
    sub.add_parser("update-ytdlp", help="upgrade yt-dlp now")
    sub.add_parser("status", help="show what is installed")
    args = parser.parse_args(argv)

    layout = RuntimeLayout(Path(__file__).resolve().parent.parent)
    try:
        if args.command == "status":
            _status(layout)
        elif args.command == "update-ytdlp":
            ensure(layout, update_days=YTDLP_UPDATE_DAYS, force_ytdlp_update=True)
        else:
            ensure(layout, update_days=args.update_days)
    except (PortableError, OSError) as ex:
        print(f"\nERROR: {ex}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
