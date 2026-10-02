"""Run.bat under the real cmd.exe, with stand-ins for the runtime and the installer.

The "portable Python" is a copy of Windows' Robocopy.exe: started as
``python.exe -s <downloader.py> ...`` it finds no source folder called "-s", copies nothing
and exits with 16, a code Run.bat itself never uses, so the test can tell the app's exit
code from the launcher's own. See tests/windows.py for how cmd.exe is reached.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.windows import IS_WINDOWS, requires_windows_scripts, run_batch, win

ROOT = Path(__file__).resolve().parent.parent

pytestmark = requires_windows_scripts

NO_UPDATE = {"YTDLP_NO_AUTO_UPDATE": "1"}


def robocopy() -> Path:
    system = Path(r"C:\Windows\System32") if IS_WINDOWS else Path("/mnt/c/Windows/System32")
    return system / "Robocopy.exe"


@pytest.fixture
def folder(windows_scratch: Path) -> Path:
    shutil.copy(ROOT / "Run.bat", windows_scratch / "Run.bat")
    (windows_scratch / "install.ps1").write_text("exit 0\r\n", encoding="utf-8")
    (windows_scratch / "update.ps1").write_text("exit 0\r\n", encoding="utf-8")
    (windows_scratch / "downloader.py").write_text("print('app')\n", encoding="utf-8")
    python = windows_scratch / "runtime" / "python" / "python.exe"
    python.parent.mkdir(parents=True)
    shutil.copy(robocopy(), python)
    return windows_scratch


def app_code(folder: Path, *args: str) -> int:
    """The exit code the stand-in app gives for these arguments, started directly."""
    python = folder / "runtime" / "python" / "python.exe"
    command = [str(python), "-s", win(folder / "downloader.py")]
    code = subprocess.run(
        [*command, *args], capture_output=True, cwd=folder, timeout=60, check=False
    ).returncode
    assert code not in (0, 1)
    return code


def test_a_command_line_run_returns_the_apps_exit_code_without_waiting(folder: Path) -> None:
    result = run_batch(folder / "Run.bat", "audit", env=NO_UPDATE)

    assert result.returncode == app_code(folder, "audit"), result.stdout + result.stderr
    assert "Press any key" not in result.stdout


def test_a_double_click_run_waits_and_still_returns_the_code(folder: Path) -> None:
    result = run_batch(folder / "Run.bat", env=NO_UPDATE)

    assert result.returncode == app_code(folder), result.stdout + result.stderr
    assert "Press any key" in result.stdout


def test_quoted_arguments_with_spaces_reach_the_app(folder: Path) -> None:
    result = run_batch(folder / "Run.bat", "audit", "--archive", '"a b.txt"', env=NO_UPDATE)

    assert result.returncode == app_code(folder, "audit", "--archive", "a b.txt")
    assert "Press any key" not in result.stdout


def test_a_half_restored_update_stops_the_launch(folder: Path) -> None:
    backup = folder / ".update-backup-x"
    backup.mkdir()
    (folder / ".update-in-progress").write_text(win(backup) + "\r\n", encoding="utf-8")

    result = run_batch(folder / "Run.bat", "audit", env=NO_UPDATE)

    assert result.returncode == 1
    assert "Starting app" not in result.stdout
    assert win(backup) in result.stdout
    assert "update.ps1" in result.stdout
