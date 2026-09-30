"""What a run achieved, judged from the archive, the manifest and the disk.

yt-dlp's exit code is a poor witness. It says whether *an* error was reported, not
which items are done, and the compatibility profile runs yt-dlp twice, so "the last
exit code" is whichever stage happened to run last. The evidence that does not lie is
the download archive (yt-dlp records an item there only after every step succeeded),
the manifest that says where each item's file went, and the file itself.

evaluate() turns that evidence into a RunOutcome, and describe() turns the outcome into
the lines the user reads, so the success, partial-success and failure messages all come
from one model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from .i18n import t

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable, Mapping

#: How many item ids a message lists before summarising the rest.
_MAX_LISTED = 10


class RunStatus(StrEnum):
    """The overall verdict of a run."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    BANNED = "banned"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class RunOutcome:
    """The result of one download run.

    Attributes:
        completed: Items finished in this run: recorded in the archive and on disk.
        already_present: Items the archive already held before the run (skipped).
        failed: Ids of items that were expected but not archived.
        missing: Ids recorded as done whose file is not on disk.
        failed_unknown: Failures that cannot be tied to an id (a single video whose id
            was never learned, or an error code nothing else explains).
        not_attempted: Items left undone because the run was stopped (ban or cancel).
        banned: The run was stopped because YouTube started blocking.
        cancelled: The user cancelled.
    """

    completed: int = 0
    already_present: int = 0
    failed: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    failed_unknown: int = 0
    not_attempted: int = 0
    banned: bool = False
    cancelled: bool = False

    @property
    def failures(self) -> int:
        """Items that did not end well."""
        return len(self.failed) + len(self.missing) + self.failed_unknown

    @property
    def status(self) -> RunStatus:
        if self.cancelled:
            return RunStatus.CANCELLED
        if self.banned:
            return RunStatus.BANNED
        if self.failures == 0:
            return RunStatus.SUCCESS
        return RunStatus.PARTIAL if self.completed > 0 else RunStatus.FAILED


@dataclass(frozen=True, slots=True)
class StageReport:
    """What running the yt-dlp stage(s) of a download produced.

    Attributes:
        codes: The exit code of each stage that ran, in order (the compatibility profile
            has two, every other download one).
        banned: The ban guard stopped a stage.
        cancelled: The user cancelled during a stage.
    """

    codes: tuple[int, ...]
    banned: bool = False
    cancelled: bool = False


def read_manifest(path: Path) -> dict[str, Path]:
    """Read a download manifest: ``<id><TAB><final path>`` lines, the last per id wins."""
    entries: dict[str, Path] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entries
    for line in text.splitlines():
        ident, sep, file = line.partition("\t")
        if sep and ident.strip() and file.strip():
            entries[ident.strip()] = Path(file.strip())
    return entries


def evaluate(
    *,
    stage_codes: tuple[int, ...],
    archive_before: Collection[str],
    archive_after: Collection[str],
    manifest: Mapping[str, Path],
    expected_ids: Iterable[str] | None,
    banned: bool = False,
    cancelled: bool = False,
    path_exists: Callable[[Path], bool] = Path.exists,
) -> RunOutcome:
    """Judge a run.

    Args:
        stage_codes: The exit code of each yt-dlp stage that ran, in order.
        archive_before: Ids in the download archive before the run.
        archive_after: Ids in it after the run.
        manifest: Where each finished item's file was written (see read_manifest).
        expected_ids: The ids the run was meant to cover (the listing), or None when
            they are not known (a single video).
        banned: The run was stopped by the ban guard.
        cancelled: The user cancelled.
        path_exists: Whether a file is on disk; replaced in tests.
    """
    before, after = set(archive_before), set(archive_after)
    new = sorted(after - before)
    expected = list(dict.fromkeys(expected_ids)) if expected_ids is not None else None

    completed = 0
    missing: list[str] = []
    for ident in new:
        path = manifest.get(ident)
        # A new record with no manifest line cannot be checked; it is taken as finished.
        if path is not None and not path_exists(path):
            missing.append(ident)
        else:
            completed += 1

    already_present = 0
    failed: list[str] = []
    not_attempted = 0
    if expected is not None:
        for ident in expected:
            if ident in before:
                path = manifest.get(ident)
                if path is not None and not path_exists(path):
                    missing.append(ident)
                else:
                    already_present += 1
            elif ident not in after:
                failed.append(ident)
        if banned or cancelled:
            not_attempted, failed = len(failed), []
    elif not new and not banned and not cancelled and stage_codes and stage_codes[-1] == 0:
        # A single video that yt-dlp skipped because the archive already holds it.
        if all(code == 0 for code in stage_codes):
            already_present = 1

    failed_unknown = 0
    if not banned and not cancelled:
        last = stage_codes[-1] if stage_codes else 0
        if last != 0 and not failed and not missing:
            failed_unknown = 1
        elif expected is None and not new and any(code != 0 for code in stage_codes):
            # An earlier stage failed and the last one produced nothing either: the
            # clean exit code of the last stage does not make the item done.
            failed_unknown = 1
            already_present = 0

    return RunOutcome(
        completed=completed,
        already_present=already_present,
        failed=tuple(failed),
        missing=tuple(missing),
        failed_unknown=failed_unknown,
        not_attempted=not_attempted,
        banned=banned,
        cancelled=cancelled,
    )


def _listed(ids: tuple[str, ...]) -> str:
    shown = ", ".join(ids[:_MAX_LISTED])
    if len(ids) > _MAX_LISTED:
        shown += " " + t("outcome_more", count=len(ids) - _MAX_LISTED)
    return shown


def describe(outcome: RunOutcome) -> list[tuple[str, str]]:
    """The lines to show for an outcome, as (kind, text) with kind ok/warn/error/info."""
    status = outcome.status
    lines: list[tuple[str, str]] = []
    headline = {
        RunStatus.SUCCESS: ("ok", t("tasks_completed")),
        RunStatus.PARTIAL: ("warn", t("outcome_partial")),
        RunStatus.FAILED: ("error", t("outcome_failed")),
        RunStatus.BANNED: ("error", t("outcome_banned")),
        RunStatus.CANCELLED: ("warn", t("outcome_cancelled")),
    }[status]
    lines.append(headline)

    if outcome.completed:
        lines.append(("info", t("outcome_completed", count=outcome.completed)))
    if outcome.already_present:
        lines.append(("info", t("outcome_already", count=outcome.already_present)))
    if outcome.failed:
        lines.append(
            (
                "warn",
                t("outcome_failed_items", count=len(outcome.failed), ids=_listed(outcome.failed)),
            )
        )
    if outcome.missing:
        lines.append(
            (
                "warn",
                t(
                    "outcome_missing_items",
                    count=len(outcome.missing),
                    ids=_listed(outcome.missing),
                ),
            )
        )
    if outcome.failed_unknown:
        lines.append(("warn", t("outcome_failed_unknown", count=outcome.failed_unknown)))
    if outcome.not_attempted:
        lines.append(("info", t("outcome_not_attempted", count=outcome.not_attempted)))
    return lines
