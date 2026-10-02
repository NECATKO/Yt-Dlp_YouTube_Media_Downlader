"""run.sh and install.sh, in a disposable folder with stand-ins for Python and the installer."""

import os
import platform
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    os.name != "posix" or platform.system() != "Linux" or not shutil.which("bash"),
    reason="the Linux launchers",
)


def script(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/bash\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    for name in ("run.sh", "install.sh"):
        shutil.copy(ROOT / name, tmp_path / name)
    (tmp_path / "downloader.py").write_text("print('app')\n", encoding="utf-8")
    return tmp_path


def fake_python(folder: Path) -> Path:
    """A "portable Python" that records how it was started."""
    return script(
        folder / "runtime" / "python" / "bin" / "python3",
        f'echo "$@" >> "{folder}/python.calls"\n'
        f'echo "PYTHONUTF8=$PYTHONUTF8" >> "{folder}/python.env"\n',
    )


class TestRunSh:
    def run(self, folder: Path, *args: str, env: dict[str, str] | None = None):
        return subprocess.run(
            ["bash", str(folder / "run.sh"), *args],
            capture_output=True,
            text=True,
            env={**os.environ, **(env or {})},
            cwd=folder,
            timeout=60,
            check=False,
        )

    def test_it_does_not_check_for_updates_at_launch(self, folder: Path) -> None:
        """On Linux/macOS updating is on request (bash update.sh), never at launch."""
        fake_python(folder)
        script(folder / "install.sh", "exit 0\n")
        script(folder / "update.sh", f'echo ran >> "{folder}/update.calls"\n')

        result = self.run(folder)

        assert result.returncode == 0, result.stderr
        assert not (folder / "update.calls").exists()
        assert "-s downloader.py" in (folder / "python.calls").read_text()

    def test_a_half_restored_update_stops_the_launch(self, folder: Path) -> None:
        """Running a package an update left half replaced could do anything."""
        fake_python(folder)
        script(folder / "install.sh", "exit 0\n")
        script(folder / "update.sh", f'echo ran >> "{folder}/update.calls"\n')
        backup = folder / ".update-backup-x"
        backup.mkdir()
        (folder / ".update-in-progress").write_text(f"{backup}\n", encoding="utf-8")

        result = self.run(folder)

        assert result.returncode == 1
        assert not (folder / "python.calls").exists()
        assert not (folder / "update.calls").exists()
        assert str(backup) in result.stderr
        assert "bash update.sh" in result.stderr

    def test_python_is_told_to_use_utf8(self, folder: Path) -> None:
        fake_python(folder)
        script(folder / "install.sh", "exit 0\n")
        script(folder / "update.sh", "exit 0\n")

        self.run(folder)

        assert "PYTHONUTF8=1" in (folder / "python.env").read_text()

    def test_arguments_reach_the_app(self, folder: Path) -> None:
        fake_python(folder)
        script(folder / "install.sh", "exit 0\n")
        script(folder / "update.sh", "exit 0\n")

        self.run(folder, "audit", "--repair")

        assert "downloader.py audit --repair" in (folder / "python.calls").read_text()

    def test_an_offline_launch_with_a_working_runtime_carries_on(self, folder: Path) -> None:
        fake_python(folder)
        script(folder / "install.sh", "exit 1\n")  # the runtime check cannot finish
        script(folder / "update.sh", "exit 0\n")

        result = self.run(folder)

        assert result.returncode == 0
        assert "did not finish" in (result.stdout + result.stderr)
        assert (folder / "python.calls").exists()


class TestInstallShRecovery:
    """A run killed while swapping Python must not leave the app without one."""

    LOCK = "python linux-{arch} {sha} https://example.invalid/python.tar.gz\n"

    def machine(self) -> str:
        arch = platform.machine()
        return {
            "x86_64": "x86_64",
            "AMD64": "x86_64",
            "aarch64": "aarch64",
            "arm64": "aarch64",
        }.get(arch, "")

    def prepare(self, folder: Path, *, with_current: bool) -> str:
        sha = "a" * 64
        arch = self.machine()
        if not arch:
            pytest.skip("unsupported architecture for the portable runtime")
        (folder / "runtime.lock").write_text(self.LOCK.format(arch=arch, sha=sha), encoding="utf-8")
        old = folder / "runtime" / "python.old"
        script(old / "bin" / "python3", "exit 0\n")
        (old / ".lock-sha256").write_text(sha, encoding="utf-8")
        if with_current:
            script(folder / "runtime" / "python" / "bin" / "python3", "exit 0\n")
            (folder / "runtime" / "python" / ".lock-sha256").write_text(sha, encoding="utf-8")
        return sha

    def run_install(self, folder: Path):
        return subprocess.run(
            ["bash", str(folder / "install.sh"), "--quiet"],
            capture_output=True,
            text=True,
            cwd=folder,
            timeout=60,
            check=False,
        )

    def test_the_old_python_is_put_back_when_the_new_one_never_arrived(self, folder: Path) -> None:
        self.prepare(folder, with_current=False)

        result = self.run_install(folder)

        assert result.returncode == 0, result.stdout + result.stderr
        assert (folder / "runtime" / "python" / "bin" / "python3").exists()
        assert not (folder / "runtime" / "python.old").exists()

    def test_a_stale_backup_is_dropped_when_python_is_in_place(self, folder: Path) -> None:
        self.prepare(folder, with_current=True)

        result = self.run_install(folder)

        assert result.returncode == 0, result.stdout + result.stderr
        assert not (folder / "runtime" / "python.old").exists()
        assert (folder / "runtime" / "python" / "bin" / "python3").exists()
