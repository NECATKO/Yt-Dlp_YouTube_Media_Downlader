"""Checking the download archives against the disk, and repairing them safely."""

import json
from pathlib import Path

import pytest

from ytdlp_app.archive_audit import (
    FindingStatus,
    apply_repair,
    audit_all,
    audit_archive,
    main,
    plan_forget,
    plan_repair,
)
from ytdlp_app.i18n import set_language


@pytest.fixture(autouse=True)
def _english():
    set_language("en")
    yield
    set_language("en")


@pytest.fixture
def world(tmp_path: Path) -> dict[str, Path]:
    archives = tmp_path / "archives"
    archives.mkdir()
    videos = tmp_path / "Videos"
    music = tmp_path / "Music"
    videos.mkdir()
    music.mkdir()
    return {"archives": archives, "videos": videos, "music": music, "root": tmp_path}


def write_archive(world: dict[str, Path], name: str, ids: list[str], extra: str = "") -> Path:
    path = world["archives"] / name
    path.write_text("".join(f"youtube {i}\n" for i in ids) + extra, encoding="utf-8")
    return path


def write_manifest(archive: Path, entries: dict[str, Path]) -> None:
    manifest = archive.with_name(archive.stem + ".files.tsv")
    manifest.write_text("".join(f"{i}\t{p}\n" for i, p in entries.items()), encoding="utf-8")


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    return path


def statuses(report) -> dict[str, FindingStatus]:
    return {f.ident: f.status for f in report.findings}


class TestAudit:
    def test_a_recorded_file_that_exists_is_ok(self, world: dict[str, Path]) -> None:
        archive = write_archive(world, "single_videos_mp4.txt", ["aaa"])
        write_manifest(archive, {"aaa": touch(world["videos"] / "a.mp4")})

        report = audit_archive(archive, [world["videos"], world["music"]])

        assert statuses(report) == {"aaa": FindingStatus.PRESENT}

    def test_a_recorded_file_that_is_gone_is_missing(self, world: dict[str, Path]) -> None:
        archive = write_archive(world, "single_videos_mp4.txt", ["aaa"])
        write_manifest(archive, {"aaa": world["videos"] / "deleted.mp4"})

        report = audit_archive(archive, [world["videos"], world["music"]])

        assert statuses(report) == {"aaa": FindingStatus.MISSING}

    def test_a_moved_file_is_found_by_its_id(self, world: dict[str, Path]) -> None:
        archive = write_archive(world, "single_videos_mp4.txt", ["dQw4w9WgXcQ"])
        write_manifest(archive, {"dQw4w9WgXcQ": world["videos"] / "old place.mp4"})
        touch(world["videos"] / "elsewhere" / "Song [dQw4w9WgXcQ].mp4")

        report = audit_archive(archive, [world["videos"]])

        assert statuses(report) == {"dQw4w9WgXcQ": FindingStatus.PRESENT}

    def test_an_id_in_a_folder_name_counts_as_present(self, world: dict[str, Path]) -> None:
        """Archive mode keeps every video in a folder named "... [id]"."""
        archive = write_archive(world, "channel_UC1_archive.txt", ["dQw4w9WgXcQ"])
        touch(world["videos"] / "yt-dlp" / "Chan" / "20260101 - T [dQw4w9WgXcQ]" / "T.mkv")

        report = audit_archive(archive, [world["videos"]])

        assert statuses(report) == {"dQw4w9WgXcQ": FindingStatus.PRESENT}

    def test_a_folder_and_side_files_without_media_do_not_prove_a_record(
        self, world: dict[str, Path]
    ) -> None:
        """The video was deleted; its folder and info JSON were left behind."""
        folder = world["videos"] / "yt-dlp" / "Chan" / "20260101 - T [dQw4w9WgXcQ]"
        archive = write_archive(world, "channel_UC1_archive.txt", ["dQw4w9WgXcQ"])
        write_manifest(archive, {"dQw4w9WgXcQ": folder / "T.mkv"})
        touch(folder / "T.info.json")
        touch(folder / "T.jpg")

        report = audit_archive(archive, [world["videos"], world["music"]])

        assert statuses(report) == {"dQw4w9WgXcQ": FindingStatus.MISSING}

    def test_an_old_record_with_only_a_folder_left_is_unverified(
        self, world: dict[str, Path]
    ) -> None:
        archive = write_archive(world, "channel_UC1_archive.txt", ["dQw4w9WgXcQ"])
        touch(world["videos"] / "yt-dlp" / "Chan" / "20260101 - T [dQw4w9WgXcQ]" / "T.info.json")

        report = audit_archive(archive, [world["videos"]])

        assert statuses(report) == {"dQw4w9WgXcQ": FindingStatus.UNVERIFIED}

    def test_an_mp3_of_the_same_video_does_not_hide_a_missing_mp4(
        self, world: dict[str, Path]
    ) -> None:
        archive = write_archive(world, "single_videos_mp4.txt", ["dQw4w9WgXcQ"])
        write_manifest(archive, {"dQw4w9WgXcQ": world["videos"] / "T [dQw4w9WgXcQ].mp4"})
        touch(world["music"] / "T [dQw4w9WgXcQ].mp3")

        report = audit_archive(archive, [world["videos"], world["music"]])

        assert statuses(report) == {"dQw4w9WgXcQ": FindingStatus.MISSING}

    def test_a_part_file_is_not_the_download(self, world: dict[str, Path]) -> None:
        archive = write_archive(world, "single_videos_mp4.txt", ["dQw4w9WgXcQ"])
        write_manifest(archive, {"dQw4w9WgXcQ": world["videos"] / "T [dQw4w9WgXcQ].mp4"})
        touch(world["videos"] / "T [dQw4w9WgXcQ].mp4.part")

        report = audit_archive(archive, [world["videos"]])

        assert statuses(report) == {"dQw4w9WgXcQ": FindingStatus.MISSING}

    def test_a_manifest_path_that_is_a_folder_is_missing(self, world: dict[str, Path]) -> None:
        archive = write_archive(world, "single_videos_mp4.txt", ["aaa"])
        folder = world["videos"] / "a.mp4"
        folder.mkdir()
        write_manifest(archive, {"aaa": folder})

        report = audit_archive(archive, [world["videos"]])

        assert statuses(report) == {"aaa": FindingStatus.MISSING}

    def test_a_manifest_file_that_is_not_media_is_not_reported_unarchived(
        self, world: dict[str, Path]
    ) -> None:
        archive = write_archive(world, "single_videos_mp4.txt", ["aaa"])
        write_manifest(
            archive,
            {
                "aaa": touch(world["videos"] / "a.mp4"),
                "zzz": touch(world["videos"] / "z.info.json"),
            },
        )

        report = audit_archive(archive, [world["videos"]])

        assert report.unarchived == ()

    def test_repair_plans_only_proven_missing_records(self, world: dict[str, Path]) -> None:
        archive = write_archive(world, "channel_UC1_archive.txt", ["gone1", "old1"])
        write_manifest(archive, {"gone1": world["videos"] / "x [gone1]" / "x.mkv"})
        touch(world["videos"] / "y [old1]" / "y.info.json")

        plan = plan_repair(audit_archive(archive, [world["videos"]]))

        assert plan.remove == ("gone1",)

    def test_an_old_record_with_no_evidence_is_unverified_not_missing(
        self, world: dict[str, Path]
    ) -> None:
        """Files downloaded before ids went into names cannot be matched to the archive."""
        archive = write_archive(world, "single_videos_mp4.txt", ["aaa"])
        touch(world["videos"] / "Some old title.mp4")

        report = audit_archive(archive, [world["videos"]])

        assert statuses(report) == {"aaa": FindingStatus.UNVERIFIED}

    def test_files_the_manifest_knows_but_the_archive_does_not_are_reported(
        self, world: dict[str, Path]
    ) -> None:
        archive = write_archive(world, "single_videos_mp4.txt", ["aaa"])
        write_manifest(
            archive,
            {"aaa": touch(world["videos"] / "a.mp4"), "zzz": touch(world["videos"] / "z.mp4")},
        )

        report = audit_archive(archive, [world["videos"]])

        assert report.unarchived == ("zzz",)

    def test_counts_and_ordering(self, world: dict[str, Path]) -> None:
        archive = write_archive(world, "a.txt", ["b", "a", "c"])
        write_manifest(
            archive,
            {"a": touch(world["videos"] / "a.mp4"), "b": world["videos"] / "gone.mp4"},
        )

        report = audit_archive(archive, [world["videos"]])

        assert [f.ident for f in report.findings] == ["b", "a", "c"]
        assert (report.present, report.missing, report.unverified) == (1, 1, 1)

    def test_manifests_and_backups_are_not_treated_as_archives(
        self, world: dict[str, Path]
    ) -> None:
        archive = write_archive(world, "single_videos_mp4.txt", ["aaa"])
        write_manifest(archive, {"aaa": world["videos"] / "gone.mp4"})
        (world["archives"] / "backups").mkdir()
        (world["archives"] / "backups" / "x.txt.bak").write_text("youtube zzz\n")
        (world["archives"] / "notes.md").write_text("hello")

        reports = audit_all(world["archives"], [world["videos"]])

        assert [r.archive.name for r in reports] == ["single_videos_mp4.txt"]

    def test_the_audit_never_writes_anything(self, world: dict[str, Path]) -> None:
        archive = write_archive(world, "a.txt", ["aaa"])
        write_manifest(archive, {"aaa": world["videos"] / "gone.mp4"})
        before = sorted(
            (p.name, p.read_bytes()) for p in world["archives"].iterdir() if p.is_file()
        )

        audit_all(world["archives"], [world["videos"]])

        after = sorted((p.name, p.read_bytes()) for p in world["archives"].iterdir() if p.is_file())
        assert before == after


class TestRepairPlan:
    def test_only_proven_missing_records_are_planned(self, world: dict[str, Path]) -> None:
        archive = write_archive(world, "a.txt", ["gone", "here", "unknown"])
        write_manifest(
            archive,
            {"gone": world["videos"] / "gone.mp4", "here": touch(world["videos"] / "here.mp4")},
        )

        plan = plan_repair(audit_archive(archive, [world["videos"]]))

        assert plan.remove == ("gone",)

    def test_a_plan_changes_nothing(self, world: dict[str, Path]) -> None:
        archive = write_archive(world, "a.txt", ["gone"])
        write_manifest(archive, {"gone": world["videos"] / "gone.mp4"})
        before = archive.read_text(encoding="utf-8")

        plan_repair(audit_archive(archive, [world["videos"]]))

        assert archive.read_text(encoding="utf-8") == before
        assert not (world["archives"] / "backups").exists()

    def test_forgetting_named_ids_needs_them_to_be_in_the_archive(
        self, world: dict[str, Path]
    ) -> None:
        archive = write_archive(world, "a.txt", ["a", "b"])

        plan = plan_forget(archive, ["b", "nope"])

        assert plan.remove == ("b",)
        assert plan.unknown == ("nope",)


class TestApply:
    def test_a_backup_is_made_before_anything_changes(self, world: dict[str, Path]) -> None:
        archive = write_archive(world, "a.txt", ["gone", "keep"])
        write_manifest(archive, {"gone": world["videos"] / "gone.mp4"})
        original = archive.read_text(encoding="utf-8")
        plan = plan_repair(audit_archive(archive, [world["videos"]]))

        result = apply_repair(plan, world["archives"])

        assert result.backup.read_text(encoding="utf-8") == original
        assert result.backup.parent == world["archives"] / "backups"
        assert archive.read_text(encoding="utf-8") == "youtube keep\n"
        assert result.removed == ("gone",)

    def test_other_lines_are_left_exactly_as_they_were(self, world: dict[str, Path]) -> None:
        archive = write_archive(world, "a.txt", ["gone", "keep"], extra="# my note\n\n")
        write_manifest(archive, {"gone": world["videos"] / "gone.mp4"})

        apply_repair(plan_repair(audit_archive(archive, [world["videos"]])), world["archives"])

        assert archive.read_text(encoding="utf-8") == "youtube keep\n# my note\n\n"

    def test_a_failed_backup_stops_before_the_archive_is_touched(
        self, world: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ytdlp_app.archive_audit as module  # noqa: PLC0415

        archive = write_archive(world, "a.txt", ["gone"])
        write_manifest(archive, {"gone": world["videos"] / "gone.mp4"})
        before = archive.read_text(encoding="utf-8")
        monkeypatch.setattr(
            module.shutil, "copy2", lambda *_a, **_k: (_ for _ in ()).throw(OSError("no space"))
        )

        with pytest.raises(OSError, match="no space"):
            apply_repair(plan_repair(audit_archive(archive, [world["videos"]])), world["archives"])

        assert archive.read_text(encoding="utf-8") == before

    def test_an_empty_plan_makes_no_backup_and_no_change(self, world: dict[str, Path]) -> None:
        archive = write_archive(world, "a.txt", ["keep"])
        write_manifest(archive, {"keep": touch(world["videos"] / "k.mp4")})

        result = apply_repair(
            plan_repair(audit_archive(archive, [world["videos"]])), world["archives"]
        )

        assert result.removed == ()
        assert result.backup is None
        assert not (world["archives"] / "backups").exists()

    def test_two_repairs_never_overwrite_each_others_backup(self, world: dict[str, Path]) -> None:
        archive = write_archive(world, "a.txt", ["g1", "g2", "keep"])
        write_manifest(archive, {"g1": world["videos"] / "1.mp4", "g2": world["videos"] / "2.mp4"})
        first = apply_repair(plan_forget(archive, ["g1"]), world["archives"])
        second = apply_repair(plan_forget(archive, ["g2"]), world["archives"])

        assert first.backup != second.backup
        assert first.backup.read_text().count("youtube") == 3
        assert second.backup.read_text().count("youtube") == 2


class TestCommandLine:
    def run(self, world: dict[str, Path], *args: str, capsys) -> tuple[int, str]:
        config = world["root"] / "config.json"
        config.write_text(
            json.dumps({"videos_dir": str(world["videos"]), "music_dir": str(world["music"])}),
            encoding="utf-8",
        )
        code = main(
            list(args),
            archives_dir=world["archives"],
            roots=[world["videos"], world["music"]],
        )
        return code, capsys.readouterr().out

    def test_the_default_is_a_report(self, world: dict[str, Path], capsys) -> None:
        archive = write_archive(world, "a.txt", ["gone", "old"])
        write_manifest(archive, {"gone": world["videos"] / "gone.mp4"})

        code, out = self.run(world, capsys=capsys)

        assert code == 0
        assert "a.txt" in out
        assert "gone" in out
        assert "1 missing" in out and "1 cannot be checked" in out

    def test_repair_previews_by_default_and_changes_nothing(
        self, world: dict[str, Path], capsys
    ) -> None:
        archive = write_archive(world, "a.txt", ["gone", "keep"])
        write_manifest(archive, {"gone": world["videos"] / "gone.mp4"})
        before = archive.read_text(encoding="utf-8")

        code, out = self.run(world, "--repair", capsys=capsys)

        assert code == 0
        assert "preview" in out.lower()
        assert "--apply" in out
        assert archive.read_text(encoding="utf-8") == before
        assert not (world["archives"] / "backups").exists()

    def test_apply_makes_a_backup_then_changes_the_archive(
        self, world: dict[str, Path], capsys
    ) -> None:
        archive = write_archive(world, "a.txt", ["gone", "keep"])
        write_manifest(archive, {"gone": world["videos"] / "gone.mp4"})

        code, out = self.run(world, "--repair", "--apply", capsys=capsys)

        assert code == 0
        assert archive.read_text(encoding="utf-8") == "youtube keep\n"
        assert len(list((world["archives"] / "backups").glob("a.txt.*.bak"))) == 1
        assert "backup" in out.lower()
        # It is being made now, so it is not called a preview.
        assert "nothing was changed" not in out

    def test_apply_without_a_repair_action_does_nothing(
        self, world: dict[str, Path], capsys
    ) -> None:
        archive = write_archive(world, "a.txt", ["gone"])
        write_manifest(archive, {"gone": world["videos"] / "gone.mp4"})

        code, _ = self.run(world, "--apply", capsys=capsys)

        assert code != 0
        assert archive.read_text(encoding="utf-8") == "youtube gone\n"

    def test_forgetting_ids_is_also_a_preview_first(self, world: dict[str, Path], capsys) -> None:
        archive = write_archive(world, "a.txt", ["x1", "x2"])

        code, out = self.run(world, "--forget", "x1", "--archive", "a.txt", capsys=capsys)

        assert code == 0
        assert archive.read_text(encoding="utf-8") == "youtube x1\nyoutube x2\n"
        assert "x1" in out

    def test_forgetting_needs_a_named_archive(self, world: dict[str, Path], capsys) -> None:
        write_archive(world, "a.txt", ["x1"])

        code, out = self.run(world, "--forget", "x1", capsys=capsys)

        assert code != 0
        assert "--archive" in out

    def test_forgetting_ids_applies_with_a_backup(self, world: dict[str, Path], capsys) -> None:
        archive = write_archive(world, "a.txt", ["x1", "x2"])

        code, _ = self.run(world, "--forget", "x1", "--archive", "a.txt", "--apply", capsys=capsys)

        assert code == 0
        assert archive.read_text(encoding="utf-8") == "youtube x2\n"
        assert list((world["archives"] / "backups").glob("a.txt.*.bak"))

    def test_an_unknown_archive_name_is_an_error_not_a_crash(
        self, world: dict[str, Path], capsys
    ) -> None:
        code, out = self.run(world, "--forget", "x", "--archive", "nope.txt", capsys=capsys)

        assert code != 0
        assert "nope.txt" in out

    def test_an_archive_name_cannot_point_outside_the_archives_folder(
        self, world: dict[str, Path], capsys
    ) -> None:
        outside = world["root"] / "outside.txt"
        outside.write_text("youtube x1\n", encoding="utf-8")

        code, _ = self.run(
            world, "--forget", "x1", "--archive", "../outside.txt", "--apply", capsys=capsys
        )

        assert code != 0
        assert outside.read_text(encoding="utf-8") == "youtube x1\n"


class TestMenu:
    """The in-app tools: everything that changes an archive asks first."""

    def make(self, world: dict[str, Path], picks: list[int]):
        from ytdlp_app.archive_audit import run_menu  # noqa: PLC0415
        from ytdlp_app.models import AppPaths, UserConfig  # noqa: PLC0415

        class UI:
            def __init__(self) -> None:
                self.picks = list(picks)
                self.printed: list[str] = []

            def print(self, text: object = "") -> None:
                self.printed.append(str(text))

            def pick(self, _prompt: str, options: list[str]) -> int:
                return self.picks.pop(0)

        ui = UI()
        paths = AppPaths(
            world["root"], world["root"] / "config.json", world["root"] / "l", world["archives"]
        )
        config = UserConfig("a", world["videos"], world["music"])
        run_menu(ui, paths, config)  # type: ignore[arg-type]
        return ui

    def test_declining_the_confirmation_changes_nothing(self, world: dict[str, Path]) -> None:
        archive = write_archive(world, "a.txt", ["gone"])
        write_manifest(archive, {"gone": world["videos"] / "gone.mp4"})

        # Repair, then "No", then back.
        self.make(world, [2, 2, 4])

        assert archive.read_text(encoding="utf-8") == "youtube gone\n"
        assert not (world["archives"] / "backups").exists()

    def test_confirming_repairs_with_a_backup(self, world: dict[str, Path]) -> None:
        archive = write_archive(world, "a.txt", ["gone", "keep"])
        write_manifest(archive, {"gone": world["videos"] / "gone.mp4"})

        ui = self.make(world, [2, 1, 4])

        assert archive.read_text(encoding="utf-8") == "youtube keep\n"
        assert list((world["archives"] / "backups").glob("a.txt.*.bak"))
        assert any("Backup" in line for line in ui.printed)

    def test_the_report_option_never_writes(self, world: dict[str, Path]) -> None:
        archive = write_archive(world, "a.txt", ["gone"])
        write_manifest(archive, {"gone": world["videos"] / "gone.mp4"})

        ui = self.make(world, [1, 4])

        assert archive.read_text(encoding="utf-8") == "youtube gone\n"
        assert any("1 missing" in line for line in ui.printed)

    def test_download_everything_again_asks_which_archive_and_then_confirms(
        self, world: dict[str, Path]
    ) -> None:
        first = write_archive(world, "a.txt", ["x1", "x2"])
        second = write_archive(world, "b.txt", ["y1"])

        # "download an archive again", pick the second, confirm, back.
        self.make(world, [3, 2, 1, 4])

        assert first.read_text(encoding="utf-8") == "youtube x1\nyoutube x2\n"
        assert second.read_text(encoding="utf-8") == ""
        assert list((world["archives"] / "backups").glob("b.txt.*.bak"))

    def test_no_archives_is_said_plainly(self, world: dict[str, Path]) -> None:
        ui = self.make(world, [1, 4])

        assert any("No download archives" in line for line in ui.printed)
