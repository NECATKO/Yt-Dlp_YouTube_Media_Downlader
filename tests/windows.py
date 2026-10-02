"""Running the Windows scripts for real: on Windows, or from WSL through its interop.

The scripts run under the real Windows PowerShell 5.1 and cmd.exe, in a folder on the
Windows file system (under %TEMP%), so file locking, renames and batch parsing are
Windows' own. From WSL, paths are translated with wslpath and the environment variables a
test sets are forwarded with WSLENV. Without either, the tests that need this skip, unless
YTDLP_REQUIRE_WINDOWS_SCRIPTS=1 (set on the Windows CI runner), which makes a missing tool
a failure instead.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path, PureWindowsPath

import pytest

IS_WINDOWS = os.name == "nt"

POWERSHELL = shutil.which("powershell") if IS_WINDOWS else shutil.which("powershell.exe")
CMD = (os.environ.get("COMSPEC") or shutil.which("cmd")) if IS_WINDOWS else shutil.which("cmd.exe")

REQUIRED = os.environ.get("YTDLP_REQUIRE_WINDOWS_SCRIPTS") == "1"

requires_windows_scripts = pytest.mark.skipif(
    not (POWERSHELL and CMD) and not REQUIRED,
    reason="needs Windows PowerShell and cmd.exe (Windows, or WSL with interop)",
)


def win(path: Path) -> str:
    """The Windows form of a path."""
    if IS_WINDOWS:
        return str(path)
    out = subprocess.run(["wslpath", "-w", str(path)], capture_output=True, text=True, check=True)
    return out.stdout.strip()


def file_uri(path: Path) -> str:
    """A file:/// URL that Windows PowerShell can read."""
    return PureWindowsPath(win(path)).as_uri()


def windows_temp() -> Path:
    """The Windows temporary folder, as a path this Python can use."""
    if IS_WINDOWS:
        return Path(os.environ.get("TEMP", os.environ.get("TMP", ".")))
    assert CMD is not None
    raw = subprocess.run(
        [CMD, "/d", "/c", "echo %TEMP%"],
        capture_output=True,
        text=True,
        check=True,
        cwd="/mnt/c",
    ).stdout.strip()
    out = subprocess.run(["wslpath", "-u", raw], capture_output=True, text=True, check=True)
    return Path(out.stdout.strip())


def make_scratch() -> Path:
    """A fresh folder on the Windows file system (the ``windows_scratch`` fixture's)."""
    assert POWERSHELL and CMD, "Windows PowerShell and cmd.exe are required here"
    folder = windows_temp() / f"ytdlp-test-{uuid.uuid4().hex[:10]}"
    folder.mkdir()
    return folder


def _env(extra: dict[str, str] | None) -> dict[str, str]:
    env = {**os.environ, **(extra or {})}
    if not IS_WINDOWS and extra:
        names = [n for n in env.get("WSLENV", "").split(":") if n]
        env["WSLENV"] = ":".join([*names, *(k for k in extra if k not in names)])
    return env


def _finish(proc: subprocess.CompletedProcess[bytes]) -> subprocess.CompletedProcess[str]:
    def text(data: bytes) -> str:
        return data.decode("utf-8", errors="replace").replace("\r\n", "\n")

    return subprocess.CompletedProcess(
        proc.args, proc.returncode, text(proc.stdout or b""), text(proc.stderr or b"")
    )


def run_powershell(
    script: Path, *args: str, stdin: str = "", env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a .ps1 file with Windows PowerShell from its own folder."""
    assert POWERSHELL is not None
    proc = subprocess.run(
        [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", win(script), *args],
        input=stdin.encode(),
        capture_output=True,
        env=_env(env),
        cwd=script.parent,
        timeout=180,
        check=False,
    )
    return _finish(proc)


def run_batch(
    script: Path, *args: str, stdin: str = "", env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a .bat file with cmd.exe from its own folder, with ``args`` as written.

    The arguments go through a one-line wrapper file rather than the command line, so the
    quoting is cmd.exe's own and not what Python or WSL make of it.
    """
    assert CMD is not None
    wrapper = script.parent / f"_run-{uuid.uuid4().hex[:8]}.cmd"
    line = " ".join([f'call "{win(script)}"', *args])
    wrapper.write_bytes(f"@{line}\r\n@exit /b %ERRORLEVEL%\r\n".encode())
    proc = subprocess.run(
        [CMD, "/d", "/c", win(wrapper)],
        input=stdin.encode(),
        capture_output=True,
        env=_env(env),
        cwd=script.parent,
        timeout=180,
        check=False,
    )
    return _finish(proc)
