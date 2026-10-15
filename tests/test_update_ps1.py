"""update.ps1 under the real Windows PowerShell 5.1, against a disposable install.

The "release" is served from local files (file:/// URLs, which Windows PowerShell's web
cmdlets read). The install lives on the Windows file system; see tests/windows.py.
"""

import json
import shutil
from pathlib import Path

import pytest

from tests.test_update_sh import write_package, zip_dir
from tests.windows import file_uri, requires_windows_scripts, run_powershell, win

ROOT = Path(__file__).resolve().parent.parent

pytestmark = requires_windows_scripts


#: A swap that fails after ytdlp_app was replaced, then a rollback that cannot put it back.
RESTORE_FAILS = {"YTDLP_UPDATE_FAULT_AT": "update.sh", "YTDLP_UPDATE_RESTORE_FAULT_AT": "ytdlp_app"}


class Site:
    """The fake "GitHub" plus the Windows install under test."""

    def __init__(self, folder: Path, current: str = "0.3.1") -> None:
        self.tmp = folder
        self.install = folder / "install"
        self.install.mkdir()
        write_package(self.install, current, marker="old")
        shutil.copy(ROOT / "update.ps1", self.install / "update.ps1")
        (self.install / "config.json").write_text('{"language": "tr"}', encoding="utf-8")
        (self.install / "archives").mkdir()
        (self.install / "archives" / "a.txt").write_text("youtube abc\n", encoding="utf-8")
        (self.install / "downloads").mkdir()
        (self.install / "downloads" / "video.mp4").write_bytes(b"precious")
        self.release_dir = folder / "release"
        self.release_dir.mkdir()

    def publish(self, tag: str, package: Path | None = None) -> None:
        if package is None:
            package = self.tmp / f"pkg-{tag}"
            write_package(package, tag.lstrip("v"), marker="new")
        zip_path = self.release_dir / "YtDlpDownloader-Portable.zip"
        zip_dir(package, zip_path, top="P")
        assets = [
            {"name": "YtDlpDownloader-Portable.zip", "browser_download_url": file_uri(zip_path)}
        ]
        (self.release_dir / "latest.json").write_text(
            json.dumps({"tag_name": tag, "assets": assets}), encoding="utf-8"
        )

    def run(self, *args: str, stdin: str = "", env: dict[str, str] | None = None):
        api = file_uri(self.release_dir / "latest.json")
        return run_powershell(
            self.install / "update.ps1", "-ApiUrl", api, *args, stdin=stdin, env=env
        )

    def version(self) -> str:
        return (self.install / "app_version.txt").read_text(encoding="utf-8-sig").strip()

    def marker(self) -> str:
        text = (self.install / "ytdlp_app" / "app.py").read_text(encoding="utf-8")
        return "new" if "'new'" in text else "old" if "'old'" in text else "?"

    def journal(self) -> Path:
        return self.install / ".update-in-progress"

    def user_data_untouched(self) -> bool:
        return (
            (self.install / "config.json").read_text(encoding="utf-8") == '{"language": "tr"}'
            and (self.install / "archives" / "a.txt").read_text(encoding="utf-8") == "youtube abc\n"
            and (self.install / "downloads" / "video.mp4").read_bytes() == b"precious"
        )

    def leftovers(self) -> list[str]:
        return sorted(
            p.name
            for p in self.install.iterdir()
            if p.name.startswith((".update-work", ".update-new", ".update-backup", ".update.lock"))
            or p.name == ".update-in-progress"
        )


@pytest.fixture
def site(windows_scratch: Path) -> Site:
    return Site(windows_scratch)


def output(result) -> str:
    return result.stdout + result.stderr


class TestUpdating:
    def test_quiet_installs_a_newer_release_and_keeps_the_users_files(self, site: Site) -> None:
        site.publish("v0.4.0")

        result = site.run("-Quiet")

        assert result.returncode == 0, output(result)
        assert site.version() == "v0.4.0"
        assert site.marker() == "new"
        assert site.user_data_untouched()
        assert site.leftovers() == []

    def test_check_only_changes_nothing(self, site: Site) -> None:
        site.publish("v0.4.0")

        result = site.run("-CheckOnly")

        assert result.returncode == 0, output(result)
        assert "Update available: v0.3.1 -> v0.4.0" in output(result)
        assert site.marker() == "old"


class TestConfirmation:
    """A run started by hand asks first (B12); Run.bat's -Quiet run does not."""

    def test_a_manual_run_asks_and_no_keeps_the_installed_version(self, site: Site) -> None:
        site.publish("v0.4.0")

        result = site.run(stdin="n\n")

        assert result.returncode == 0, output(result)
        assert "Download and install update?" in output(result)
        assert site.marker() == "old"
        assert site.version() == "v0.3.1"
        assert site.leftovers() == []

    def test_no_answer_at_all_counts_as_no(self, site: Site) -> None:
        site.publish("v0.4.0")

        result = site.run(stdin="")

        assert result.returncode == 0, output(result)
        assert site.marker() == "old"

    def test_yes_installs_it(self, site: Site) -> None:
        site.publish("v0.4.0")

        result = site.run(stdin="y\n")

        assert result.returncode == 0, output(result)
        assert site.marker() == "new"
        assert site.version() == "v0.4.0"


class TestRollback:
    def test_a_failure_part_way_through_the_swap_restores_everything(self, site: Site) -> None:
        site.publish("v0.4.0")

        result = site.run(stdin="y\n", env={"YTDLP_UPDATE_FAULT_AT": "update.sh"})

        assert result.returncode != 0
        assert site.marker() == "old"
        assert site.version() == "v0.3.1"
        assert site.user_data_untouched()
        assert site.leftovers() == []

    def test_a_failed_restore_keeps_the_journal_and_the_backup(self, site: Site) -> None:
        site.publish("v0.4.0")

        result = site.run(
            stdin="y\n",
            env={
                "YTDLP_UPDATE_FAULT_AT": "update.sh",
                "YTDLP_UPDATE_RESTORE_FAULT_AT": "ytdlp_app",
            },
        )

        assert result.returncode != 0
        assert site.journal().exists()
        # The backup is named relative to the app folder, so it is still found after a move.
        recorded = site.journal().read_text(encoding="utf-8-sig").splitlines()[0]
        assert recorded.startswith(".update-backup-") and "\\" not in recorded
        assert (site.install / recorded / "ytdlp_app").exists()
        assert "update.ps1 again" in output(result)
        assert site.user_data_untouched()

    def test_the_next_run_finishes_a_restore_that_failed(self, site: Site) -> None:
        site.publish("v0.4.0")
        site.run(
            stdin="y\n",
            env={
                "YTDLP_UPDATE_FAULT_AT": "update.sh",
                "YTDLP_UPDATE_RESTORE_FAULT_AT": "ytdlp_app",
            },
        )

        result = site.run("-CheckOnly")

        assert result.returncode == 0, output(result)
        assert site.marker() == "old"
        assert site.version() == "v0.3.1"
        assert site.leftovers() == []
        assert site.user_data_untouched()

    def test_a_file_the_update_added_is_removed_by_the_rollback(self, site: Site) -> None:
        package = site.tmp / "pkg-added"
        write_package(package, "0.4.0", marker="new")
        (package / "README.md").write_text("new readme\n", encoding="utf-8")
        (package / "LICENSE").write_text("new license\n", encoding="utf-8")
        site.publish("v0.4.0", package)

        result = site.run(stdin="y\n", env={"YTDLP_UPDATE_FAULT_AT": "LICENSE"})

        assert result.returncode != 0
        assert not (site.install / "README.md").exists()
        assert site.marker() == "old"
        assert site.leftovers() == []

    def test_a_journal_written_by_0_4_0_is_still_recovered(self, site: Site) -> None:
        backup = site.install / ".update-backup-old"
        backup.mkdir()
        shutil.move(str(site.install / "ytdlp_app"), str(backup / "ytdlp_app"))
        # 0.4.0 wrote the backup path alone, with no line end.
        site.journal().write_text(win(backup), encoding="utf-8")
        site.publish("v0.3.1")

        result = site.run("-CheckOnly")

        assert result.returncode == 0, output(result)
        assert site.marker() == "old"
        assert site.leftovers() == []


def half_updated(site: Site, recorded: str) -> None:
    """What a crash in the middle of the swap leaves: the new app in place, the journal
    naming the backup as `recorded`."""
    (site.install / "ytdlp_app" / "app.py").write_text("MARKER = 'new'\n", encoding="utf-8")
    site.journal().write_bytes(recorded.encode("utf-8"))
    site.publish("v0.3.1")  # nothing newer: a run only recovers


class TestRecoveryWithoutItsBackup:
    """D03: a journal whose backup is not here is a recovery that cannot be done; it must
    not be reported as done, and the journal (which keeps Run.bat from starting a
    half-updated app) must stay."""

    @pytest.mark.parametrize("args", [("-CheckOnly",), ("-Quiet",), ()])
    def test_a_missing_backup_keeps_the_journal_and_is_not_called_a_restore(
        self, site: Site, args: tuple[str, ...]
    ) -> None:
        half_updated(site, ".update-backup-gone\r\n")

        result = site.run(*args, stdin="n\n")

        assert site.journal().read_bytes() == b".update-backup-gone\r\n"
        assert "previous version was restored" not in output(result)
        assert ".update-backup-gone" in output(result)
        # -Quiet (Run.bat) never fails; Run.bat itself then refuses to start.
        assert result.returncode == (0 if args == ("-Quiet",) else 1)
        assert site.marker() == "new"
        assert site.user_data_untouched()

    def test_a_backup_outside_the_app_folder_is_never_used(self, site: Site) -> None:
        outside = site.tmp / "elsewhere" / ".update-backup-x"
        (outside / "ytdlp_app").mkdir(parents=True)
        (outside / "ytdlp_app" / "app.py").write_text("MARKER = 'stranger'\n", encoding="utf-8")
        half_updated(site, win(outside))

        result = site.run("-CheckOnly")

        assert result.returncode == 1
        assert site.journal().exists()
        assert site.marker() == "new"
        assert (outside / "ytdlp_app" / "app.py").exists()

    def test_an_absolute_journal_from_before_a_folder_move_finds_its_backup_here(
        self, site: Site
    ) -> None:
        backup = site.install / ".update-backup-moved"
        backup.mkdir()
        shutil.move(str(site.install / "ytdlp_app"), str(backup / "ytdlp_app"))
        site.journal().write_text(r"D:\where\the\app\used\to\be\.update-backup-moved", "utf-8")
        site.publish("v0.3.1")

        result = site.run("-CheckOnly")

        assert result.returncode == 0, output(result)
        assert site.marker() == "old"
        assert site.leftovers() == []


class TestKeepingThePreviousVersion:
    """D19: the update is done; only keeping the replaced version as .previous-version
    fails. The update stands, and the replaced version must not be thrown away."""

    def test_the_backup_stays_where_it_is_and_its_place_is_named(self, site: Site) -> None:
        older = site.install / ".previous-version"
        (older / "ytdlp_app").mkdir(parents=True)
        (older / "ytdlp_app" / "app.py").write_text("MARKER = 'older'\n", encoding="utf-8")
        site.publish("v0.4.0")

        result = site.run("-Quiet", env={"YTDLP_UPDATE_FAULT_AT": ".previous-version"})

        assert result.returncode == 0, output(result)
        assert site.version() == "v0.4.0"
        assert site.marker() == "new"
        assert not site.journal().exists()
        assert "'older'" in (older / "ytdlp_app" / "app.py").read_text(encoding="utf-8")
        (backup,) = site.install.glob(".update-backup-*")
        assert "'old'" in (backup / "ytdlp_app" / "app.py").read_text(encoding="utf-8")
        assert backup.name in output(result)
        assert not list(site.install.glob(".previous-version-*"))

    def test_a_successful_update_replaces_the_version_kept_before(self, site: Site) -> None:
        older = site.install / ".previous-version"
        (older / "ytdlp_app").mkdir(parents=True)
        (older / "ytdlp_app" / "app.py").write_text("MARKER = 'older'\n", encoding="utf-8")
        site.publish("v0.4.0")

        result = site.run(stdin="y\n")

        assert result.returncode == 0, output(result)
        assert "'old'" in (older / "ytdlp_app" / "app.py").read_text(encoding="utf-8")
        assert "kept in .previous-version" in output(result)
        assert site.leftovers() == []
        assert not list(site.install.glob(".previous-version-*"))
