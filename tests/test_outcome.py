"""Judging a run from what really happened: the archive, the manifest and the files."""

from pathlib import Path

import pytest

from ytdlp_app.i18n import set_language, t
from ytdlp_app.outcome import (
    RunOutcome,
    RunStatus,
    describe,
    evaluate,
    read_manifest,
)


@pytest.fixture(autouse=True)
def _english():
    set_language("en")
    yield
    set_language("en")


def make(tmp_path: Path, names: list[str]) -> dict[str, Path]:
    """Files that exist on disk, keyed by the id they belong to."""
    made = {}
    for name in names:
        path = tmp_path / f"{name}.mkv"
        path.write_bytes(b"x")
        made[name] = path
    return made


class TestEvaluate:
    def test_everything_new_and_on_disk_is_a_success(self, tmp_path: Path) -> None:
        files = make(tmp_path, ["a", "b"])

        outcome = evaluate(
            stage_codes=(0,),
            archive_before=set(),
            archive_after={"a", "b"},
            manifest=files,
            expected_ids=["a", "b"],
        )

        assert outcome.completed == 2
        assert outcome.status is RunStatus.SUCCESS

    def test_items_already_archived_are_counted_as_present(self, tmp_path: Path) -> None:
        files = make(tmp_path, ["a"])

        outcome = evaluate(
            stage_codes=(0,),
            archive_before={"a"},
            archive_after={"a"},
            manifest=files,
            expected_ids=["a"],
        )

        assert (outcome.completed, outcome.already_present) == (0, 1)
        assert outcome.status is RunStatus.SUCCESS

    def test_an_expected_item_that_was_not_archived_is_a_failure_even_at_exit_code_0(
        self, tmp_path: Path
    ) -> None:
        files = make(tmp_path, ["a"])

        outcome = evaluate(
            stage_codes=(0,),
            archive_before=set(),
            archive_after={"a"},
            manifest=files,
            expected_ids=["a", "b"],
        )

        assert outcome.failed == ("b",)
        assert outcome.status is RunStatus.PARTIAL

    def test_nothing_finished_and_something_failed_is_a_failure(self) -> None:
        outcome = evaluate(
            stage_codes=(1,),
            archive_before=set(),
            archive_after=set(),
            manifest={},
            expected_ids=["a"],
        )

        assert outcome.failed == ("a",)
        assert outcome.status is RunStatus.FAILED

    def test_an_archived_item_whose_file_is_gone_is_missing_not_completed(
        self, tmp_path: Path
    ) -> None:
        files = make(tmp_path, ["a"])
        files["b"] = tmp_path / "b-was-here.mkv"  # recorded, never on disk

        outcome = evaluate(
            stage_codes=(0,),
            archive_before=set(),
            archive_after={"a", "b"},
            manifest=files,
            expected_ids=["a", "b"],
        )

        assert outcome.missing == ("b",)
        assert outcome.completed == 1
        assert outcome.status is RunStatus.PARTIAL

    def test_an_old_record_whose_file_was_deleted_is_reported_missing(self, tmp_path: Path) -> None:
        manifest = {"a": tmp_path / "deleted.mkv"}

        outcome = evaluate(
            stage_codes=(0,),
            archive_before={"a"},
            archive_after={"a"},
            manifest=manifest,
            expected_ids=["a"],
        )

        assert outcome.missing == ("a",)
        assert outcome.already_present == 0
        assert outcome.status is RunStatus.FAILED

    def test_an_old_record_without_manifest_entry_cannot_be_checked_and_counts_as_present(
        self,
    ) -> None:
        outcome = evaluate(
            stage_codes=(0,),
            archive_before={"a"},
            archive_after={"a"},
            manifest={},
            expected_ids=["a"],
        )

        assert outcome.already_present == 1
        assert outcome.status is RunStatus.SUCCESS

    def test_a_single_video_that_finished_is_completed(self, tmp_path: Path) -> None:
        files = make(tmp_path, ["a"])

        outcome = evaluate(
            stage_codes=(0,),
            archive_before=set(),
            archive_after={"a"},
            manifest=files,
            expected_ids=None,
        )

        assert outcome.completed == 1
        assert outcome.status is RunStatus.SUCCESS

    def test_a_single_video_skipped_by_the_archive_is_already_present(self) -> None:
        outcome = evaluate(
            stage_codes=(0,),
            archive_before={"a"},
            archive_after={"a"},
            manifest={},
            expected_ids=None,
        )

        assert outcome.completed == 0
        assert outcome.already_present == 1
        assert outcome.status is RunStatus.SUCCESS

    def test_a_single_video_with_an_error_and_nothing_new_is_a_failure(self) -> None:
        outcome = evaluate(
            stage_codes=(1,),
            archive_before=set(),
            archive_after=set(),
            manifest={},
            expected_ids=None,
        )

        assert outcome.failed_unknown == 1
        assert outcome.status is RunStatus.FAILED

    def test_a_clean_second_stage_cannot_hide_an_unresolved_first_stage(self) -> None:
        """Stage 1 failed, stage 2 exited 0, yet nothing was archived: not a success."""
        outcome = evaluate(
            stage_codes=(1, 0),
            archive_before=set(),
            archive_after=set(),
            manifest={},
            expected_ids=None,
        )

        assert outcome.status is RunStatus.FAILED

    def test_a_second_stage_that_finished_the_item_resolves_the_first_stage_error(
        self, tmp_path: Path
    ) -> None:
        files = make(tmp_path, ["a"])

        outcome = evaluate(
            stage_codes=(1, 0),
            archive_before=set(),
            archive_after={"a"},
            manifest=files,
            expected_ids=["a"],
        )

        assert outcome.status is RunStatus.SUCCESS

    def test_an_error_code_with_no_identified_cause_is_never_a_silent_success(
        self, tmp_path: Path
    ) -> None:
        files = make(tmp_path, ["a"])

        outcome = evaluate(
            stage_codes=(1,),
            archive_before=set(),
            archive_after={"a"},
            manifest=files,
            expected_ids=["a"],
        )

        assert outcome.failed_unknown == 1
        assert outcome.status is RunStatus.PARTIAL

    def test_duplicate_expected_ids_count_once(self, tmp_path: Path) -> None:
        files = make(tmp_path, ["a"])

        outcome = evaluate(
            stage_codes=(0,),
            archive_before=set(),
            archive_after={"a"},
            manifest=files,
            expected_ids=["a", "a"],
        )

        assert outcome.completed == 1

    def test_a_ban_and_a_cancel_dominate_the_status(self) -> None:
        banned = evaluate(
            stage_codes=(75,),
            archive_before=set(),
            archive_after=set(),
            manifest={},
            expected_ids=["a"],
            banned=True,
        )
        cancelled = evaluate(
            stage_codes=(130,),
            archive_before=set(),
            archive_after=set(),
            manifest={},
            expected_ids=["a"],
            cancelled=True,
        )

        assert banned.status is RunStatus.BANNED
        assert cancelled.status is RunStatus.CANCELLED

    def test_completed_items_survive_a_ban_and_are_still_counted(self, tmp_path: Path) -> None:
        files = make(tmp_path, ["a"])

        outcome = evaluate(
            stage_codes=(75,),
            archive_before=set(),
            archive_after={"a"},
            manifest=files,
            expected_ids=["a", "b"],
            banned=True,
        )

        assert outcome.completed == 1
        assert outcome.status is RunStatus.BANNED


class TestManifest:
    def test_the_last_line_for_an_id_wins(self, tmp_path: Path) -> None:
        path = tmp_path / "a.files.tsv"
        path.write_text("x\t/one.mkv\ny\t/two.mkv\nx\t/three.mkv\n", encoding="utf-8")

        assert read_manifest(path) == {"x": Path("/three.mkv"), "y": Path("/two.mkv")}

    def test_a_missing_file_is_an_empty_manifest(self, tmp_path: Path) -> None:
        assert read_manifest(tmp_path / "none.tsv") == {}

    def test_malformed_lines_are_ignored(self, tmp_path: Path) -> None:
        path = tmp_path / "a.files.tsv"
        path.write_text("no tab here\n\t\nx\t/ok.mkv\n\n", encoding="utf-8")

        assert read_manifest(path) == {"x": Path("/ok.mkv")}


class TestDescribe:
    def lines(self, outcome: RunOutcome) -> str:
        return "\n".join(text for _kind, text in describe(outcome))

    def test_success_reports_what_was_downloaded_and_what_was_there(self) -> None:
        text = self.lines(RunOutcome(completed=3, already_present=2))

        assert "3 downloaded" in text
        assert "2 already in the archive" in text

    def test_partial_success_names_the_failures(self) -> None:
        text = self.lines(RunOutcome(completed=3, failed=("idA", "idB"), missing=("idC",)))

        assert t("outcome_partial") in text
        assert "idA" in text and "idC" in text

    def test_failure_says_nothing_was_downloaded(self) -> None:
        text = self.lines(RunOutcome(failed=("idA",)))

        assert t("outcome_failed") in text

    def test_a_long_list_of_failures_is_shortened(self) -> None:
        text = self.lines(RunOutcome(completed=1, failed=tuple(f"id{i:03d}" for i in range(40))))

        assert "id000" in text
        assert "id039" not in text
        assert "30 more" in text

    def test_cancelled_and_banned_have_their_own_headlines(self) -> None:
        assert t("outcome_cancelled") in self.lines(RunOutcome(cancelled=True, completed=1))
        assert t("outcome_banned") in self.lines(RunOutcome(banned=True))

    def test_unidentified_failures_are_counted(self) -> None:
        assert "1" in self.lines(RunOutcome(failed_unknown=1))
