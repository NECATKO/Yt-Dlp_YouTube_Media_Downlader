"""The single source of truth for the application version.

Kept in a leaf module that imports nothing, so any module can read it without
creating an import cycle and so setuptools can parse it statically.

app_version.txt carries the same version in git-tag form ("v" prefix), because
the updaters compare it against the GitHub release tag_name. CI runs
scripts/check_version.py to enforce that the two agree with the release tag.
"""

from __future__ import annotations

__version__ = "0.3.1"
