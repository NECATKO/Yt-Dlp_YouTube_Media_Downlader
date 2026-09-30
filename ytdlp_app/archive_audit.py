"""Check the download archives against the disk, and repair them without surprises.

A yt-dlp download archive is a list of ids: "this one is done". It says nothing about
where the file went, so a file that was deleted, moved, or never completed (older versions
recorded items whose post-processing had failed, or whose file name collided with another
video's) is still "done" and is skipped for ever.

Since the manifest (``<archive>.files.tsv``, written by the DownloadLedger plugin) records
the final path of every item finished from now on, the check can say for those items whether
the file is there. Older records have no path; for them the check looks for the id in a file
or folder name (``... [id]``), and when even that finds nothing it says *cannot be checked*,
never *missing*: a file called after its title cannot be matched to an id, and nothing is
repaired on a guess.

Everything here that changes a file is opt-in: reports and previews write nothing, applying
needs an explicit request, and the archive is copied to ``archives/backups/`` first.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from .atomic import atomic_write_text
from .exceptions import ValidationError
from .i18n import t
from .logging_utils import Colors, console_print, paint
from .outcome import read_manifest
from .planning import ensure_within

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

    from .models import AppPaths, UserConfig
    from .ui import UI

_BRACKET_ID = re.compile(r"\[([^\[\]/\\]+)\]")

#: Backups of archives changed by a repair live here, inside the archives folder.
BACKUP_DIR_NAME = "backups"

#: How many ids a line of the report lists.
_MAX_LISTED = 12


class FindingStatus(StrEnum):
    """What the check could establish about one archive record."""

    PRESENT = "present"
    MISSING = "missing"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class Finding:
    """One archive record and what is known about its file."""

    ident: str
    status: FindingStatus
    path: Path | None = None


@dataclass(frozen=True, slots=True)
class ArchiveReport:
    """The check of one archive file.

    Attributes:
        archive: The archive file.
        findings: One per record, in file order (duplicates counted once).
        unarchived: Ids with a manifest entry whose file exists but that the archive
            does not list (an interrupted run, or a hand-edited archive).
    """

    archive: Path
    findings: tuple[Finding, ...]
    unarchived: tuple[str, ...] = ()

    def _count(self, status: FindingStatus) -> int:
        return sum(1 for f in self.findings if f.status is status)

    @property
    def present(self) -> int:
        return self._count(FindingStatus.PRESENT)

    @property
    def missing(self) -> int:
        return self._count(FindingStatus.MISSING)

    @property
    def unverified(self) -> int:
        return self._count(FindingStatus.UNVERIFIED)

    @property
    def missing_ids(self) -> tuple[str, ...]:
        return tuple(f.ident for f in self.findings if f.status is FindingStatus.MISSING)


@dataclass(frozen=True, slots=True)
class RepairPlan:
    """A change to one archive file, not yet made.

    Attributes:
        archive: The archive file.
        remove: Record ids that would be removed (so the next run downloads them again).
        unknown: Requested ids the archive does not hold.
    """

    archive: Path
    remove: tuple[str, ...]
    unknown: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RepairResult:
    """A change that was made."""

    archive: Path
    removed: tuple[str, ...]
    backup: Path | None


class _IdIndex:
    """The ids that appear in file and folder names under the download folders (built lazily)."""

    def __init__(self, roots: Iterable[Path]) -> None:
        self._roots = [r for r in roots if r.is_dir()]
        self._ids: set[str] | None = None

    def _build(self) -> set[str]:
        found: set[str] = set()
        for root in self._roots:
            for _dir, dirs, files in os.walk(root):
                for name in (*dirs, *files):
                    found.update(_BRACKET_ID.findall(name))
        return found

    def __contains__(self, ident: str) -> bool:
        if self._ids is None:
            self._ids = self._build()
        return ident in self._ids


def _archive_lines(archive: Path) -> list[str]:
    return archive.read_text(encoding="utf-8", errors="replace").splitlines()


def _id_of(line: str) -> str | None:
    parts = line.split()
    return parts[-1] if parts and not line.lstrip().startswith("#") else None


def _manifest_of(archive: Path) -> Path:
    return archive.with_name(archive.stem + ".files.tsv")


def audit_archive(
    archive: Path, roots: Sequence[Path], *, index: _IdIndex | None = None
) -> ArchiveReport:
    """Check every record of one archive against the disk. Writes nothing."""
    ids = list(dict.fromkeys(i for i in map(_id_of, _archive_lines(archive)) if i))
    manifest = read_manifest(_manifest_of(archive))
    names = index if index is not None else _IdIndex(roots)

    findings: list[Finding] = []
    for ident in ids:
        path = manifest.get(ident)
        if (path is not None and path.exists()) or ident in names:
            findings.append(Finding(ident, FindingStatus.PRESENT, path))
        elif path is not None:
            findings.append(Finding(ident, FindingStatus.MISSING, path))
        else:
            findings.append(Finding(ident, FindingStatus.UNVERIFIED))

    known = set(ids)
    unarchived = tuple(i for i, p in manifest.items() if i not in known and p.exists())
    return ArchiveReport(archive, tuple(findings), unarchived)


def find_archives(archives_dir: Path) -> list[Path]:
    """The download archive files in a folder (not manifests, backups or other files)."""
    if not archives_dir.is_dir():
        return []
    return sorted(
        p
        for p in archives_dir.iterdir()
        if p.is_file() and p.suffix == ".txt" and not p.name.endswith(".files.tsv")
    )


def audit_all(archives_dir: Path, roots: Sequence[Path]) -> list[ArchiveReport]:
    """Check every archive in the folder, scanning the download folders at most once."""
    index = _IdIndex(roots)
    return [audit_archive(a, roots, index=index) for a in find_archives(archives_dir)]


def plan_repair(report: ArchiveReport) -> RepairPlan:
    """Plan removing the records whose file is proven to be gone.

    Records that merely cannot be checked are never included: they may well be fine.
    """
    return RepairPlan(report.archive, report.missing_ids)


def plan_forget(archive: Path, ids: Iterable[str]) -> RepairPlan:
    """Plan removing specific records, so that those items are downloaded again."""
    held = {i for i in map(_id_of, _archive_lines(archive)) if i}
    wanted = list(dict.fromkeys(ids))
    return RepairPlan(
        archive,
        tuple(i for i in wanted if i in held),
        tuple(i for i in wanted if i not in held),
    )


def plan_forget_all(archive: Path) -> RepairPlan:
    """Plan removing every record of an archive."""
    ids = [i for i in map(_id_of, _archive_lines(archive)) if i]
    return RepairPlan(archive, tuple(dict.fromkeys(ids)))


def _backup_path(archives_dir: Path, archive: Path) -> Path:
    folder = archives_dir / BACKUP_DIR_NAME
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = folder / f"{archive.name}.{stamp}.bak"
    counter = 1
    while candidate.exists():
        candidate = folder / f"{archive.name}.{stamp}-{counter}.bak"
        counter += 1
    return candidate


def apply_repair(plan: RepairPlan, archives_dir: Path) -> RepairResult:
    """Make the change a plan describes: back the archive up, then rewrite it.

    Nothing is written before the backup exists; the rewrite itself is atomic, so a failure
    leaves the archive as it was. Lines that are not records (comments, blank lines) are kept
    exactly.

    Raises:
        OSError: The backup or the rewrite failed; the archive is then unchanged.
    """
    if not plan.remove:
        return RepairResult(plan.archive, (), None)
    backup = _backup_path(archives_dir, plan.archive)
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(plan.archive, backup)

    doomed = set(plan.remove)
    text = plan.archive.read_text(encoding="utf-8", errors="replace")
    kept = [line for line in text.splitlines(keepends=True) if _id_of(line) not in doomed]
    atomic_write_text(plan.archive, "".join(kept))
    return RepairResult(plan.archive, plan.remove, backup)


# -- presentation ------------------------------------------------------------


def _listed(ids: Sequence[str]) -> str:
    shown = ", ".join(ids[:_MAX_LISTED])
    if len(ids) > _MAX_LISTED:
        shown += " " + t("outcome_more", count=len(ids) - _MAX_LISTED)
    return shown


def print_report(reports: Sequence[ArchiveReport], out: UI | None = None) -> None:
    """Show the result of a check."""
    say = out.print if out is not None else console_print
    say(paint(t("audit_title"), Colors.CYAN, Colors.BOLD))
    for report in reports:
        say(
            t(
                "audit_archive_line",
                name=report.archive.name,
                total=len(report.findings),
                present=report.present,
                missing=report.missing,
                unverified=report.unverified,
            )
        )
        if report.missing:
            say(paint(t("audit_missing_list", ids=_listed(report.missing_ids)), Colors.YELLOW))
        if report.unarchived:
            say(t("audit_unarchived", ids=_listed(report.unarchived)))
    if any(r.unverified for r in reports):
        say(paint(t("audit_unverified_note"), Colors.WHITE))
    if any(r.missing for r in reports):
        say(paint(t("audit_repair_hint"), Colors.CYAN))


def print_plan(plans: Sequence[RepairPlan], out: UI | None = None, *, preview: bool = True) -> None:
    """Show what a repair would do; ``preview`` says whether it is about to be made or not."""
    say = out.print if out is not None else console_print
    title = "audit_preview_title" if preview else "audit_plan_title"
    say(paint(t(title), Colors.CYAN, Colors.BOLD))
    active = [p for p in plans if p.remove or p.unknown]
    if not any(p.remove for p in plans):
        say(t("audit_nothing_to_repair"))
    for plan in active:
        if plan.remove:
            say(
                t(
                    "audit_would_remove",
                    name=plan.archive.name,
                    count=len(plan.remove),
                    ids=_listed(plan.remove),
                )
            )
        if plan.unknown:
            say(paint(t("audit_unknown_ids", ids=_listed(plan.unknown)), Colors.YELLOW))


# -- command line --------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="downloader.py audit",
        description=(
            "Check the download archives against the files on disk. Nothing is changed "
            "unless --apply is given, and a backup is made first."
        ),
    )
    parser.add_argument(
        "--repair", action="store_true", help="plan removing records whose file is gone"
    )
    parser.add_argument(
        "--forget",
        nargs="+",
        metavar="ID",
        help="plan removing these records (download them again)",
    )
    parser.add_argument(
        "--forget-all", action="store_true", help="plan removing every record of --archive"
    )
    parser.add_argument("--archive", metavar="NAME", help="the archive file to act on")
    parser.add_argument("--apply", action="store_true", help="make the planned change")
    return parser


def main(
    argv: Sequence[str],
    *,
    archives_dir: Path,
    roots: Sequence[Path],
) -> int:
    """Run the ``audit`` command line. Returns the process exit code."""
    args = _parser().parse_args(list(argv))
    acts = args.repair or args.forget or args.forget_all

    if args.apply and not acts:
        console_print(paint(t("audit_apply_needs_action"), Colors.RED))
        return 2
    if (args.forget or args.forget_all) and not args.archive:
        console_print(paint(t("audit_needs_archive"), Colors.RED))
        return 2

    reports: list[ArchiveReport]
    if args.archive:
        try:
            target = ensure_within(archives_dir, archives_dir / args.archive)
        except ValidationError:
            console_print(
                paint(
                    t("audit_unknown_archive", name=args.archive, folder=archives_dir), Colors.RED
                )
            )
            return 2
        if not target.is_file():
            console_print(
                paint(
                    t("audit_unknown_archive", name=args.archive, folder=archives_dir), Colors.RED
                )
            )
            return 2
        reports = [audit_archive(target, roots)]
    else:
        reports = audit_all(archives_dir, roots)

    if not acts:
        if not reports:
            console_print(t("audit_none", folder=archives_dir))
            return 0
        print_report(reports)
        return 0

    plans: list[RepairPlan] = []
    if args.repair:
        plans = [plan_repair(r) for r in reports]
    elif args.forget_all:
        plans = [plan_forget_all(reports[0].archive)]
    elif args.forget:
        plans = [plan_forget(reports[0].archive, args.forget)]

    print_plan(plans, preview=not args.apply)
    if not args.apply:
        if any(p.remove for p in plans):
            console_print(paint(t("audit_apply_hint"), Colors.CYAN))
        return 0

    try:
        for plan in plans:
            result = apply_repair(plan, archives_dir)
            if result.removed:
                console_print(
                    paint(
                        t(
                            "audit_applied",
                            name=result.archive.name,
                            count=len(result.removed),
                            backup=result.backup,
                        ),
                        Colors.GREEN,
                    )
                )
    except OSError as ex:
        console_print(paint(t("audit_failed", error=ex), Colors.RED))
        return 1
    if any(p.remove for p in plans):
        console_print(t("audit_restore_hint"))
    return 0


# -- in-app menu ---------------------------------------------------------------


def run_menu(ui: UI, paths: AppPaths, config: UserConfig) -> None:
    """The interactive archive tools: report, repair missing files, download again."""
    roots = [config.videos_dir, config.music_dir]
    while True:
        choice = ui.pick(
            t("audit_menu_title"),
            [
                t("audit_menu_report"),
                t("audit_menu_repair"),
                t("audit_menu_forget_all"),
                t("settings_back"),
            ],
        )
        if choice == 4:
            return
        reports = audit_all(paths.archives_dir, roots)
        if not reports:
            ui.print(t("audit_none", folder=paths.archives_dir))
            continue
        if choice == 1:
            print_report(reports, ui)
            continue
        if choice == 2:
            plans = [plan_repair(r) for r in reports]
        else:
            names = [r.archive.name for r in reports]
            picked = ui.pick(t("audit_pick_archive"), [*names, t("settings_back")])
            if picked == len(names) + 1:
                continue
            plans = [plan_forget_all(reports[picked - 1].archive)]
        print_plan(plans, ui)
        if not any(p.remove for p in plans):
            continue
        if ui.pick(t("audit_confirm"), [t("audit_confirm_yes"), t("audit_confirm_no")]) != 1:
            continue
        try:
            for plan in plans:
                result = apply_repair(plan, paths.archives_dir)
                if result.removed:
                    ui.print(
                        paint(
                            t(
                                "audit_applied",
                                name=result.archive.name,
                                count=len(result.removed),
                                backup=result.backup,
                            ),
                            Colors.GREEN,
                        )
                    )
        except OSError as ex:
            ui.print(paint(t("audit_failed", error=ex), Colors.RED))


def cli_entry(argv: Sequence[str], paths: AppPaths, config: UserConfig) -> int:
    """Entry point used by the application launcher for ``downloader.py audit ...``."""
    return main(argv, archives_dir=paths.archives_dir, roots=[config.videos_dir, config.music_dir])


__all__ = [
    "ArchiveReport",
    "Finding",
    "FindingStatus",
    "RepairPlan",
    "RepairResult",
    "apply_repair",
    "audit_all",
    "audit_archive",
    "cli_entry",
    "find_archives",
    "main",
    "plan_forget",
    "plan_forget_all",
    "plan_repair",
    "run_menu",
]
