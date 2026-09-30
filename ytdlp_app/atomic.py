"""Write files so that a crash, a full disk or a power cut never leaves half a file.

config.json and runtime/state.json hold what the user chose and what was installed;
a plain ``write_text`` truncates the file first, so an interruption anywhere in the
write turns a valid file into an empty or cut-off one. Here the new content goes to a
temporary file in the same folder, is flushed to the disk, and only then replaces the
target with a single rename. Until that rename the old file is exactly as it was, and if
anything fails the temporary file is removed.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from pathlib import Path


def _default_mode() -> int:
    umask = os.umask(0)
    os.umask(umask)
    return 0o666 & ~umask


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Replace ``path`` with ``text`` atomically.

    Args:
        path: The file to write. Its folder is created when missing.
        text: The new content.
        encoding: Text encoding.

    Raises:
        OSError: The content could not be written; ``path`` is then untouched.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temp = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding=encoding, newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        # mkstemp creates the file private (0600); keep the mode the target had.
        if path.exists():
            shutil.copymode(path, temp)
        else:
            temp.chmod(_default_mode())
        temp.replace(path)
    except BaseException:
        with contextlib.suppress(OSError):
            temp.unlink(missing_ok=True)
        raise
    # Make the rename itself durable; not every platform lets a folder be opened.
    with contextlib.suppress(OSError):
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
