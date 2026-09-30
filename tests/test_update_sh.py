"""update.sh against a disposable install, with the "release" served from local files.

The real script runs under real bash and real curl; only the network is replaced (the
release JSON and ZIP are file:// URLs). Nothing here touches the developer's own install.
"""

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
UPDATE_SH = ROOT / "update.sh"

pytestmark = pytest.mark.skipif(
    os.name != "posix" or not shutil.which("bash") or not shutil.which("curl"),
    reason="update.sh needs bash and curl",
)

GOOD_INIT = "from . import app\n"
GOOD_APP = "def run():\n    return 0\n"


def version_module(version: str) -> str:
    return f'__version__ = "{version}"\n'


def write_package(
    root: Path,
    version: str,
    *,
    init: str = GOOD_INIT,
    tag: str | None = None,
    skip: tuple[str, ...] = (),
    marker: str = "",
) -> None:
    """A minimal app: the files a release must have, importable."""
    files = {
        "ytdlp_app/__init__.py": init,
        "ytdlp_app/app.py": GOOD_APP + (f"MARKER = {marker!r}\n" if marker else ""),
        "ytdlp_app/_version.py": version_module(version),
        "downloader.py": "print('downloader')\n",
        "pyproject.toml": "[project]\n",
        "runtime.lock": "# lock\n",
        "run.sh": "#!/bin/bash\necho run\n",
        "install.sh": "#!/bin/bash\necho install\n",
        "update.sh": "#!/bin/bash\necho update\n",
        "app_version.txt": (tag or f"v{version}") + "\n",
    }
    for name, content in files.items():
        if name in skip:
            continue
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def zip_dir(source: Path, zip_path: Path, *, top: str | None = "YtDlpDownloader-Portable") -> None:
    with zipfile.ZipFile(zip_path, "w") as z:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                arc = path.relative_to(source).as_posix()
                z.write(path, f"{top}/{arc}" if top else arc)


class Site:
    """The fake "GitHub" plus the install under test."""

    def __init__(self, tmp_path: Path, current: str = "0.3.1") -> None:
        self.tmp = tmp_path
        self.install = tmp_path / "install"
        self.install.mkdir()
        write_package(self.install, current, marker="old")
        shutil.copy(UPDATE_SH, self.install / "update.sh")
        (self.install / "update.sh").chmod(0o755)
        # The interpreter the script uses to test packages with.
        venv = self.install / ".venv" / "bin"
        venv.mkdir(parents=True)
        (venv / "python").symlink_to(sys.executable)
        # The user's own data: an update must never touch any of it.
        (self.install / "config.json").write_text('{"language": "tr"}', encoding="utf-8")
        (self.install / "archives").mkdir()
        (self.install / "archives" / "a.txt").write_text("youtube abc\n", encoding="utf-8")
        (self.install / "downloads").mkdir()
        (self.install / "downloads" / "video.mp4").write_bytes(b"precious")
        (self.install / "logs").mkdir()
        (self.install / "runtime").mkdir()
        (self.install / "runtime" / "state.json").write_text("{}", encoding="utf-8")
        self.release_dir = tmp_path / "release"
        self.release_dir.mkdir()

    def publish(
        self,
        tag: str,
        package: Path | None = None,
        *,
        top: str | None = "P",
        sha: str | bool = False,
    ) -> None:
        """Serve a release: the ZIP of ``package`` (a good one by default) and its JSON."""
        if package is None:
            package = self.tmp / f"pkg-{tag}"
            write_package(package, tag.lstrip("v"), marker="new")
        zip_path = self.release_dir / "YtDlpDownloader-Portable.zip"
        zip_dir(package, zip_path, top=top)
        assets = [
            {
                "name": "YtDlpDownloader-Portable.zip",
                "browser_download_url": zip_path.as_uri(),
            }
        ]
        if sha:
            digest = hashlib.sha256(zip_path.read_bytes()).hexdigest() if sha is True else sha
            sha_file = self.release_dir / "YtDlpDownloader-Portable.zip.sha256"
            sha_file.write_text(f"{digest}  YtDlpDownloader-Portable.zip\n", encoding="utf-8")
            assets.append(
                {
                    "name": "YtDlpDownloader-Portable.zip.sha256",
                    "browser_download_url": sha_file.as_uri(),
                }
            )
        (self.release_dir / "latest.json").write_text(
            json.dumps({"tag_name": tag, "assets": assets}, indent=2), encoding="utf-8"
        )

    def run(self, *args: str, stdin: str = "", env: dict[str, str] | None = None):
        base = {
            **os.environ,
            "YTDLP_UPDATE_API": (self.release_dir / "latest.json").as_uri(),
        }
        return subprocess.run(
            ["bash", str(self.install / "update.sh"), *args],
            input=stdin,
            capture_output=True,
            text=True,
            env={**base, **(env or {})},
            cwd=self.tmp,
            timeout=120,
            check=False,
        )

    def version(self) -> str:
        return (self.install / "app_version.txt").read_text(encoding="utf-8").strip()

    def marker(self) -> str:
        text = (self.install / "ytdlp_app" / "app.py").read_text(encoding="utf-8")
        return "new" if "'new'" in text else "old" if "'old'" in text else "?"

    def user_data_untouched(self) -> bool:
        return (
            (self.install / "config.json").read_text(encoding="utf-8") == '{"language": "tr"}'
            and (self.install / "archives" / "a.txt").read_text(encoding="utf-8") == "youtube abc\n"
            and (self.install / "downloads" / "video.mp4").read_bytes() == b"precious"
            and (self.install / "runtime" / "state.json").exists()
        )

    def leftovers(self) -> list[str]:
        return sorted(
            p.name
            for p in self.install.iterdir()
            if p.name.startswith((".update-work", ".update-new", ".update-backup", ".update.lock"))
            or p.name == ".update-in-progress"
        )


@pytest.fixture
def site(tmp_path: Path) -> Site:
    return Site(tmp_path)


class TestSuccessfulUpdate:
    def test_the_new_version_is_installed_and_everything_of_the_users_survives(
        self, site: Site
    ) -> None:
        site.publish("v0.4.0")

        result = site.run(stdin="y\nn\n")

        assert result.returncode == 0, result.stdout + result.stderr
        assert site.version() == "v0.4.0"
        assert site.marker() == "new"
        assert site.user_data_untouched()
        assert site.leftovers() == []

    def test_the_previous_version_is_kept_for_a_manual_way_back(self, site: Site) -> None:
        site.publish("v0.4.0")

        site.run(stdin="y\nn\n")

        previous = site.install / ".previous-version"
        assert "'old'" in (previous / "ytdlp_app" / "app.py").read_text(encoding="utf-8")
        assert (previous / "app_version.txt").read_text(encoding="utf-8").strip() == "v0.3.1"

    def test_the_scripts_are_executable_afterwards(self, site: Site) -> None:
        site.publish("v0.4.0")

        site.run(stdin="y\nn\n")

        for name in ("run.sh", "install.sh", "update.sh"):
            assert os.access(site.install / name, os.X_OK), name

    def test_declining_changes_nothing(self, site: Site) -> None:
        site.publish("v0.4.0")

        result = site.run(stdin="n\nn\n")

        assert result.returncode == 0
        assert site.version() == "v0.3.1"
        assert site.marker() == "old"

    def test_a_zip_without_a_top_folder_works_too(self, site: Site) -> None:
        package = site.tmp / "flat"
        write_package(package, "0.4.0", marker="new")
        site.publish("v0.4.0", package, top=None)

        assert site.run(stdin="y\nn\n").returncode == 0
        assert site.version() == "v0.4.0"

    def test_the_real_current_package_installs_and_starts(self, site: Site) -> None:
        """The actual repository files, as a release, over an older install."""
        real_version = (ROOT / "app_version.txt").read_text(encoding="utf-8").strip()
        package = site.tmp / "real"
        package.mkdir()
        shutil.copytree(
            ROOT / "ytdlp_app",
            package / "ytdlp_app",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        for name in (
            "downloader.py",
            "pyproject.toml",
            "runtime.lock",
            "run.sh",
            "install.sh",
            "update.sh",
            "app_version.txt",
            "README.md",
            "LICENSE",
        ):
            shutil.copy(ROOT / name, package / name)
        (site.install / "app_version.txt").write_text("v0.0.1\n", encoding="utf-8")
        site.publish(real_version, package)

        result = site.run(stdin="y\nn\n")

        assert result.returncode == 0, result.stdout + result.stderr
        assert site.version() == real_version
        started = subprocess.run(
            [sys.executable, "-c", "import ytdlp_app, ytdlp_app.app"],
            cwd=site.install,
            capture_output=True,
            text=True,
            check=False,
        )
        assert started.returncode == 0, started.stderr


class TestRefusedPackages:
    """Each of these must leave the working install exactly as it was."""

    def assert_untouched(self, site: Site, result) -> None:
        assert result.returncode != 0, result.stdout
        assert site.version() == "v0.3.1"
        assert site.marker() == "old"
        assert site.user_data_untouched()
        assert site.leftovers() == []

    def test_a_valid_zip_with_an_unexpected_layout_does_not_cost_the_old_package(
        self, site: Site
    ) -> None:
        """The case that used to delete ytdlp_app and then fail to copy the new one."""
        other = site.tmp / "elsewhere"
        other.mkdir()
        (other / "README.md").write_text("no app in here", encoding="utf-8")
        site.publish("v0.4.0", other)

        result = site.run(stdin="y\nn\n")

        self.assert_untouched(site, result)
        assert "unexpected layout" in result.stderr

    @pytest.mark.parametrize(
        "missing",
        ["ytdlp_app/__init__.py", "ytdlp_app/_version.py", "downloader.py", "pyproject.toml"],
    )
    def test_an_incomplete_package_is_refused(self, site: Site, missing: str) -> None:
        package = site.tmp / "partial"
        write_package(package, "0.4.0", skip=(missing,))
        site.publish("v0.4.0", package)

        result = site.run(stdin="y\nn\n")

        self.assert_untouched(site, result)

    def test_a_package_whose_version_disagrees_with_its_release_is_refused(
        self, site: Site
    ) -> None:
        package = site.tmp / "liar"
        write_package(package, "0.3.9")
        site.publish("v0.4.0", package)

        result = site.run(stdin="y\nn\n")

        self.assert_untouched(site, result)
        assert "0.3.9" in result.stderr

    def test_a_package_that_cannot_start_is_refused_before_anything_changes(
        self, site: Site
    ) -> None:
        package = site.tmp / "broken"
        write_package(package, "0.4.0", init="this is not python (\n")
        site.publish("v0.4.0", package)

        result = site.run(stdin="y\nn\n")

        self.assert_untouched(site, result)
        assert "does not start" in result.stderr

    def test_a_corrupt_zip_is_refused(self, site: Site) -> None:
        site.publish("v0.4.0")
        (site.release_dir / "YtDlpDownloader-Portable.zip").write_bytes(b"not a zip at all")

        result = site.run(stdin="y\nn\n")

        self.assert_untouched(site, result)

    def test_a_release_without_the_asset_is_refused(self, site: Site) -> None:
        site.publish("v0.4.0")
        (site.release_dir / "latest.json").write_text('{"tag_name": "v0.4.0", "assets": []}')

        result = site.run(stdin="y\nn\n")

        self.assert_untouched(site, result)
        assert "asset" in result.stderr

    def test_an_unreadable_file_in_the_package_stops_the_copy_before_the_swap(
        self, site: Site
    ) -> None:
        package = site.tmp / "locked"
        write_package(package, "0.4.0", marker="new")
        site.publish("v0.4.0", package)
        # Unreadable once unpacked: cp fails part way through staging.
        real_run = subprocess.run

        result = None
        try:
            # Unpack, then break a file, by unpacking ourselves via a wrapper tool.
            wrapper = site.tmp / "bin"
            wrapper.mkdir()
            unzip = wrapper / "unzip"
            unzip.write_text(
                "#!/bin/bash\n"
                f'{sys.executable} -m zipfile -e "$2" "$4"\n'
                'chmod 000 "$4"/*/runtime.lock\n',
                encoding="utf-8",
            )
            unzip.chmod(0o755)
            result = site.run(
                stdin="y\nn\n",
                env={
                    "PATH": f"{wrapper}{os.pathsep}{os.environ['PATH']}",
                    "YTDLP_UPDATE_ZIP_TOOLS": "unzip",
                },
            )
        finally:
            for locked in site.install.rglob("runtime.lock"):
                locked.chmod(0o644)
            for locked in site.tmp.rglob("runtime.lock"):
                locked.chmod(0o644)
            _ = real_run

        assert result is not None
        if os.geteuid() == 0:
            pytest.skip("root can read anything")
        self.assert_untouched(site, result)

    def test_a_checksum_mismatch_discards_the_download(self, site: Site) -> None:
        site.publish("v0.4.0", sha="0" * 64)

        result = site.run(stdin="y\nn\n")

        self.assert_untouched(site, result)
        assert "checksum" in result.stderr.lower()

    def test_a_matching_checksum_is_accepted(self, site: Site) -> None:
        site.publish("v0.4.0", sha=True)

        result = site.run(stdin="y\nn\n")

        assert result.returncode == 0, result.stdout + result.stderr
        assert site.version() == "v0.4.0"
        assert "Checksum verified" in result.stdout


class TestRollback:
    @pytest.mark.parametrize("fault", ["ytdlp_app", "downloader.py", "update.sh"])
    def test_a_failure_part_way_through_the_swap_restores_everything(
        self, site: Site, fault: str
    ) -> None:
        site.publish("v0.4.0")

        result = site.run(stdin="y\nn\n", env={"YTDLP_UPDATE_FAULT_AT": fault})

        assert result.returncode != 0
        assert site.version() == "v0.3.1"
        assert site.marker() == "old"
        assert (site.install / "downloader.py").read_text(
            encoding="utf-8"
        ) == "print('downloader')\n"
        assert site.user_data_untouched()
        assert site.leftovers() == []
        assert "Rolling back" in result.stderr

    def test_the_version_is_not_recorded_when_the_update_fails(self, site: Site) -> None:
        site.publish("v0.4.0")

        site.run(stdin="y\nn\n", env={"YTDLP_UPDATE_FAULT_AT": "update.sh"})

        assert site.version() == "v0.3.1"

    def test_an_update_that_was_killed_half_way_is_undone_at_the_next_start(
        self, site: Site
    ) -> None:
        # What a kill between "old moved aside" and "new moved in" leaves behind.
        backup = site.install / ".update-backup-crashed"
        backup.mkdir()
        shutil.move(str(site.install / "ytdlp_app"), str(backup / "ytdlp_app"))
        (site.install / "downloader.py").write_text("half-written", encoding="utf-8")
        shutil.copy(site.install / "downloader.py", backup / "downloader.py")
        (backup / "downloader.py").write_text("print('downloader')\n", encoding="utf-8")
        (site.install / ".update-in-progress").write_text(str(backup), encoding="utf-8")
        site.publish("v0.3.1")  # nothing newer: this run only recovers

        result = site.run("--auto")

        assert result.returncode == 0
        assert (site.install / "ytdlp_app" / "app.py").exists()
        assert (site.install / "downloader.py").read_text(
            encoding="utf-8"
        ) == "print('downloader')\n"
        assert site.leftovers() == []
        assert "restored" in (result.stdout + result.stderr).lower() or site.marker() == "old"

    def test_a_crash_after_the_version_was_written_but_before_the_commit_is_undone_whole(
        self, site: Site
    ) -> None:
        backup = site.install / ".update-backup-late"
        backup.mkdir()
        # New files are in place and the version says v0.4.0, but the journal is still there.
        shutil.copytree(site.install / "ytdlp_app", backup / "ytdlp_app")
        (backup / "ytdlp_app" / "app.py").write_text("MARKER = 'old'\n", encoding="utf-8")
        (backup / "app_version.txt").write_text("v0.3.1\n", encoding="utf-8")
        (site.install / "app_version.txt").write_text("v0.4.0\n", encoding="utf-8")
        (site.install / ".update-in-progress").write_text(str(backup), encoding="utf-8")
        site.publish("v0.3.1")

        site.run("--auto")

        assert site.version() == "v0.3.1"
        assert site.marker() == "old"


class TestVersionOrdering:
    @pytest.mark.parametrize(
        ("current", "latest", "expected_update"),
        [
            ("0.3.1", "v0.3.2", True),
            ("0.3.1", "v0.3.10", True),  # numbers, not text
            ("0.10.0", "v0.9.0", False),  # the string comparison would "update" downwards
            ("1.0.0", "v0.99.99", False),
            ("1.0.0-rc1", "v1.0.0", True),
            ("1.0.0", "v1.0.0-rc1", False),
            ("1.0.0-rc1", "v1.0.0-rc2", True),
            ("1.0.0-rc.2", "v1.0.0-rc.10", True),  # dotted numeric identifiers are numbers
            ("1.0.0-alpha", "v1.0.0-beta", True),
            ("1.2.3", "v1.2.3", False),
            ("1.2", "v1.2.0", False),
            ("2.0.0", "v10.0.0", True),
        ],
    )
    def test_only_a_newer_release_is_offered(
        self, tmp_path: Path, current: str, latest: str, expected_update: bool
    ) -> None:
        site = Site(tmp_path, current)
        site.publish(latest)

        result = site.run("--check-only")

        assert result.returncode == 0
        assert ("Update available" in result.stdout) is expected_update

    def test_an_older_release_is_never_installed_even_when_asked(self, tmp_path: Path) -> None:
        site = Site(tmp_path, "0.10.0")
        site.publish("v0.9.0")

        result = site.run(stdin="y\nn\n")

        assert site.version() == "v0.10.0"
        assert "latest version" in result.stdout.lower()

    def test_an_unparseable_release_tag_is_not_installed(self, tmp_path: Path) -> None:
        site = Site(tmp_path)
        site.publish("nightly")

        result = site.run(stdin="y\nn\n")

        assert site.version() == "v0.3.1"
        assert "Update available" not in result.stdout


class TestConcurrencyAndLeftovers:
    def test_a_live_lock_stops_a_second_run_without_touching_anything(self, site: Site) -> None:
        site.publish("v0.4.0")
        holder = subprocess.Popen(["sleep", "30"])
        try:
            lock = site.install / ".update.lock"
            lock.mkdir()
            (lock / "pid").write_text(str(holder.pid), encoding="utf-8")

            result = site.run(stdin="y\nn\n")

            assert result.returncode != 0
            assert "already running" in result.stderr
            assert site.version() == "v0.3.1"
            assert lock.exists(), "a lock that is not ours is left alone"
        finally:
            holder.kill()
            holder.wait()

    def test_a_stale_lock_is_cleared(self, site: Site) -> None:
        site.publish("v0.4.0")
        lock = site.install / ".update.lock"
        lock.mkdir()
        dead = subprocess.Popen(["true"])
        dead.wait()
        (lock / "pid").write_text(str(dead.pid), encoding="utf-8")

        result = site.run(stdin="y\nn\n")

        assert result.returncode == 0, result.stderr
        assert site.version() == "v0.4.0"
        assert site.leftovers() == []

    def test_the_lock_is_released_when_the_run_ends(self, site: Site) -> None:
        site.publish("v0.3.1")

        site.run("--check-only")

        assert not (site.install / ".update.lock").exists()

    def test_leftover_work_folders_from_an_old_crash_do_not_get_in_the_way(
        self, site: Site
    ) -> None:
        (site.install / ".update-work-AAAAAA").mkdir()
        (site.install / ".update-new-old").mkdir()
        site.publish("v0.4.0")

        result = site.run(stdin="y\nn\n")

        assert result.returncode == 0, result.stderr
        assert site.version() == "v0.4.0"

    def test_two_runs_at_once_do_not_corrupt_the_install(self, site: Site) -> None:
        site.publish("v0.4.0")
        first = subprocess.Popen(
            ["bash", str(site.install / "update.sh"), "--auto"],
            env={**os.environ, "YTDLP_UPDATE_API": (site.release_dir / "latest.json").as_uri()},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        second = site.run("--auto")
        first.communicate(timeout=60)

        assert second.returncode == 0
        assert site.version() in ("v0.3.1", "v0.4.0")
        # Whatever ran, the install is one consistent version.
        assert site.marker() == ("new" if site.version() == "v0.4.0" else "old")
        assert site.leftovers() == []


class TestAutoMode:
    """What run.sh does at every launch: never in the way, quiet unless it acts."""

    def test_offline_is_silent_and_successful(self, site: Site) -> None:
        result = site.run("--auto", env={"YTDLP_UPDATE_API": "file:///no/such/file.json"})

        assert result.returncode == 0
        assert result.stdout.strip() == ""
        assert site.version() == "v0.3.1"

    def test_up_to_date_is_silent(self, site: Site) -> None:
        site.publish("v0.3.1")

        result = site.run("--auto")

        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_a_newer_release_is_installed_without_asking(self, site: Site) -> None:
        site.publish("v0.4.0")

        result = site.run("--auto")

        assert result.returncode == 0, result.stderr
        assert site.version() == "v0.4.0"
        assert site.user_data_untouched()

    def test_a_failed_update_never_blocks_the_launch(self, site: Site) -> None:
        site.publish("v0.4.0")

        result = site.run("--auto", env={"YTDLP_UPDATE_FAULT_AT": "ytdlp_app"})

        assert result.returncode == 0
        assert site.version() == "v0.3.1"
        assert site.marker() == "old"
        assert "continuing with" in result.stderr


class TestUnpacking:
    def test_a_missing_zip_tool_is_reported_before_anything_is_downloaded_or_changed(
        self, site: Site
    ) -> None:
        site.publish("v0.4.0")

        result = site.run(stdin="y\nn\n", env={"YTDLP_UPDATE_ZIP_TOOLS": "no-such-tool"})

        assert result.returncode != 0
        assert "unpack" in result.stderr.lower()
        assert site.version() == "v0.3.1"
        assert site.leftovers() == []

    def test_python_can_unpack_when_unzip_is_missing(self, site: Site) -> None:
        site.publish("v0.4.0")

        result = site.run(stdin="y\nn\n", env={"YTDLP_UPDATE_ZIP_TOOLS": "python3"})

        assert result.returncode == 0, result.stdout + result.stderr
        assert site.version() == "v0.4.0"

    @pytest.mark.skipif(not shutil.which("unzip"), reason="unzip is not installed")
    def test_unzip_is_used_when_present(self, site: Site) -> None:
        site.publish("v0.4.0")

        result = site.run(stdin="y\nn\n", env={"YTDLP_UPDATE_ZIP_TOOLS": "unzip"})

        assert result.returncode == 0, result.stdout + result.stderr


def test_the_script_is_valid_bash() -> None:
    result = subprocess.run(
        ["bash", "-n", str(UPDATE_SH)], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr


def test_the_launcher_scripts_are_executable_in_the_working_tree() -> None:
    for name in ("run.sh", "install.sh", "update.sh"):
        mode = (ROOT / name).stat().st_mode
        assert mode & stat.S_IXUSR, f"{name} must be executable (chmod +x, and commit the mode)"
