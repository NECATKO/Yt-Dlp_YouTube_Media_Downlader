"""install.sh on "macOS": which Python the .venv is made with.

uname, brew and every Python are stand-ins on a PATH that holds nothing else, so the real
interpreters of the machine running the tests are never found. This checks install.sh's
decisions against Homebrew's documented layout (a versioned ``python3.12`` in
``$(brew --prefix python@3.12)/bin``, the unversioned ``python3`` not linked onto the
PATH); it is not a run on a real Mac.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    os.name != "posix" or not shutil.which("bash"), reason="install.sh needs bash"
)

#: The few real tools the script and the stand-ins use.
TOOLS = ("dirname", "mkdir", "cat", "chmod", "cp", "cut")


def script(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/bash\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def fake_python(path: Path, version: tuple[int, int], log: Path) -> Path:
    """A Python that answers the version check and makes a stand-in .venv."""
    ok = 0 if version >= (3, 11) else 1
    return script(
        path,
        f'echo "${{0##*/}} $*" >> "{log}"\n'
        'if [[ "$1" == "-c" ]]; then\n'
        f'    [[ "$2" == *version_info* ]] && exit {ok}\n'
        f'    echo "{version[0]}.{version[1]}"; exit 0\n'
        "fi\n"
        'if [[ "$1" == "-m" && "$2" == "venv" ]]; then\n'
        '    mkdir -p "$3/bin"\n'
        f'    printf \'#!/bin/bash\\necho "pip $*" >> "{log}"\\n\' > "$3/bin/pip"\n'
        '    chmod +x "$3/bin/pip"\n'
        "fi\n",
    )


class Mac:
    def __init__(self, tmp_path: Path) -> None:
        self.folder = tmp_path / "app"
        self.folder.mkdir()
        shutil.copy(ROOT / "install.sh", self.folder / "install.sh")
        self.bin = tmp_path / "bin"
        self.log = tmp_path / "calls.log"
        self.prefix = tmp_path / "homebrew" / "opt" / "python@3.12"
        script(self.bin / "uname", "echo Darwin\n")
        script(self.bin / "ffmpeg", "exit 0\n")
        script(self.bin / "deno", "exit 0\n")
        for tool in TOOLS:
            real = shutil.which(tool)
            assert real is not None
            (self.bin / tool).symlink_to(real)

    def python(self, name: str, version: tuple[int, int]) -> None:
        fake_python(self.bin / name, version, self.log)

    def brew(self, installs: tuple[int, int] | None = (3, 12)) -> None:
        """A brew whose ``install python@3.12`` puts python3.12 under its prefix only."""
        make = ":\n"
        if installs is not None:
            make = (
                f'mkdir -p "{self.prefix}/bin"\n'
                f'cp "{self.bin}/.python-template" "{self.prefix}/bin/python3.12"\n'
            )
            fake_python(self.bin / ".python-template", installs, self.log)
        script(
            self.bin / "brew",
            f'echo "brew $*" >> "{self.log}"\n'
            'if [[ "$1" == "--prefix" ]]; then echo "' + str(self.prefix) + '"; exit 0; fi\n'
            'if [[ "$1" == "install" && "$2" == "python@3.12" ]]; then\n' + make + "fi\n"
            "exit 0\n",
        )

    def run(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["/bin/bash", str(self.folder / "install.sh")],
            capture_output=True,
            text=True,
            env={"PATH": str(self.bin), "HOME": str(self.folder)},
            cwd=self.folder,
            timeout=30,
            check=False,
        )

    def calls(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []


@pytest.fixture
def mac(tmp_path: Path) -> Mac:
    return Mac(tmp_path)


def venv_made_by(mac: Mac) -> list[str]:
    return [c.split()[0] for c in mac.calls() if " -m venv " in c]


def test_the_python_brew_installed_makes_the_venv_not_the_old_one(mac: Mac) -> None:
    mac.python("python3", (3, 9))
    mac.brew()

    result = mac.run()

    assert result.returncode == 0, result.stdout + result.stderr
    assert "brew install python@3.12" in mac.calls()
    assert venv_made_by(mac) == ["python3.12"]
    assert (mac.folder / ".venv" / "bin" / "pip").exists()


def test_a_versioned_python_on_the_path_is_used_without_brew(mac: Mac) -> None:
    mac.python("python3", (3, 9))
    mac.python("python3.12", (3, 12))
    mac.brew(installs=None)

    result = mac.run()

    assert result.returncode == 0, result.stdout + result.stderr
    assert not any(c.startswith("brew install python") for c in mac.calls())
    assert venv_made_by(mac) == ["python3.12"]


def test_a_python_4_counts_as_new_enough(mac: Mac) -> None:
    mac.python("python3", (4, 0))
    mac.brew(installs=None)

    result = mac.run()

    assert result.returncode == 0, result.stdout + result.stderr
    assert venv_made_by(mac) == ["python3"]


def test_it_stops_when_brew_did_not_bring_a_usable_python(mac: Mac) -> None:
    mac.python("python3", (3, 9))
    mac.brew(installs=(3, 9))

    result = mac.run()

    assert result.returncode == 1
    assert "Failed to install Python 3.11+" in result.stderr
    assert venv_made_by(mac) == []
