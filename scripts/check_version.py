#!/usr/bin/env python3
"""Verify that the version is consistent across every place that records it.

``ytdlp_app.__version__`` is the single source of truth. ``app_version.txt``
mirrors it in git-tag form ("v" prefix) because the updaters compare that file
against the GitHub release ``tag_name``. When run on a tag build, the tag itself
is checked too -- a release whose tag disagrees with the shipped version makes
the updater loop forever.

Usage:
    python scripts/check_version.py            # check package vs app_version.txt
    python scripts/check_version.py v1.2.3     # also check against a release tag
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT_FILE = ROOT / "ytdlp_app" / "__init__.py"
VERSION_FILE = ROOT / "app_version.txt"


def read_package_version() -> str:
    """Parse __version__ out of the package without importing it."""
    match = re.search(
        r"^__version__\s*=\s*[\"']([^\"']+)[\"']",
        INIT_FILE.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if not match:
        sys.exit(f"ERROR: no __version__ assignment found in {INIT_FILE}")
    return match.group(1)


def main() -> int:
    package_version = read_package_version()
    expected_tag = f"v{package_version}"

    if not VERSION_FILE.exists():
        sys.exit(f"ERROR: {VERSION_FILE} is missing")
    file_version = VERSION_FILE.read_text(encoding="utf-8").strip()

    errors = []
    if file_version != expected_tag:
        errors.append(
            f"app_version.txt is {file_version!r} but ytdlp_app.__version__ "
            f"implies {expected_tag!r}"
        )

    # Empty when this is not a tag build; nothing to compare against then.
    release_tag = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if release_tag and release_tag != expected_tag:
        errors.append(f"release tag is {release_tag!r} but the package is {expected_tag!r}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    checked = f"{expected_tag} (tag build)" if release_tag else expected_tag
    print(f"Version consistent: {checked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
