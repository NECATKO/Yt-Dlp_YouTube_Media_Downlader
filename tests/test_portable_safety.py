"""Replacing a runtime component or the state file must never leave the app without one."""

import os
import zipfile
from pathlib import Path
from typing import Any

import pytest

import ytdlp_app.portable as portable
from ytdlp_app.portable import (
    PortableError,
    RuntimeLayout,
    extract_component,
    load_state,
    recover_component,
    save_state,
)


def deno_zip(path: Path, marker: bytes) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("deno", marker)
    return path


@pytest.fixture
def target(tmp_path: Path) -> Path:
    old = tmp_path / "runtime" / "deno"
    old.mkdir(parents=True)
    (old / "deno").write_bytes(b"OLD")
    return old


class TestStateFile:
    def test_a_failed_save_leaves_the_previous_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        layout = RuntimeLayout(tmp_path, windows=False)
        save_state(layout, {"ytdlp_updated_at": "2026-01-01T00:00:00"})
        monkeypatch.setattr(os, "replace", lambda *_a, **_k: (_ for _ in ()).throw(OSError("full")))

        with pytest.raises(OSError, match="full"):
            save_state(layout, {"ytdlp_updated_at": "never"})

        monkeypatch.undo()
        assert load_state(layout) == {"ytdlp_updated_at": "2026-01-01T00:00:00"}
        assert [p.name for p in layout.runtime_dir.iterdir()] == ["state.json"]


class TestComponentSwap:
    def test_a_normal_replacement_swaps_and_leaves_no_backup(
        self, tmp_path: Path, target: Path
    ) -> None:
        archive = deno_zip(tmp_path / "d.zip", b"NEW")

        extract_component("deno", archive, target, windows=False)

        assert (target / "deno").read_bytes() == b"NEW"
        assert sorted(p.name for p in target.parent.iterdir()) == ["deno"]

    def test_the_old_copy_is_still_there_when_the_final_rename_fails(
        self, tmp_path: Path, target: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        archive = deno_zip(tmp_path / "d.zip", b"NEW")
        real_rename = Path.rename

        def failing(self: Path, dest: Any) -> Any:
            if self.name == "deno.new":
                raise OSError("rename failed")
            return real_rename(self, dest)

        monkeypatch.setattr(Path, "rename", failing)

        with pytest.raises(OSError, match="rename failed"):
            extract_component("deno", archive, target, windows=False)

        monkeypatch.undo()
        assert (target / "deno").read_bytes() == b"OLD"

    def test_a_bad_archive_leaves_the_old_copy_alone(self, tmp_path: Path, target: Path) -> None:
        bad = tmp_path / "bad.zip"
        with zipfile.ZipFile(bad, "w") as z:
            z.writestr("readme.txt", b"no deno in here")

        with pytest.raises(PortableError):
            extract_component("deno", bad, target, windows=False)

        assert (target / "deno").read_bytes() == b"OLD"

    def test_an_interrupted_swap_is_recovered_on_the_next_run(self, tmp_path: Path) -> None:
        """Killed between "old -> .old" and "new -> place": only the .old copy exists."""
        runtime = tmp_path / "runtime"
        backup = runtime / "deno.old"
        backup.mkdir(parents=True)
        (backup / "deno").write_bytes(b"OLD")
        target = runtime / "deno"

        recover_component(target)

        assert (target / "deno").read_bytes() == b"OLD"
        assert not backup.exists()

    def test_recovery_leaves_a_healthy_component_alone(self, target: Path) -> None:
        backup = target.with_name("deno.old")
        backup.mkdir()
        (backup / "deno").write_bytes(b"STALE")

        recover_component(target)

        assert (target / "deno").read_bytes() == b"OLD"
        assert not backup.exists()

    def test_recovery_does_nothing_when_there_is_nothing_to_recover(self, tmp_path: Path) -> None:
        recover_component(tmp_path / "runtime" / "deno")

        assert not (tmp_path / "runtime" / "deno").exists()

    def test_ensure_component_recovers_before_deciding_what_to_install(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        layout = RuntimeLayout(tmp_path, windows=False)
        backup = layout.runtime_dir / "deno.old"
        backup.mkdir(parents=True)
        (backup / "deno").write_bytes(b"OLD")
        entry = portable.LockEntry("deno", "linux-x86_64", "a" * 64, "https://x/deno.zip")
        state: dict[str, Any] = {"components": {"deno": {"sha256": "a" * 64}}}

        def no_download(*_a: Any, **_k: Any) -> Path:
            raise AssertionError("the pinned build is already there once recovered")

        changed = portable.ensure_component(
            "deno", layout, [entry], "linux-x86_64", state, downloader=no_download
        )

        assert changed is False
        assert layout.component_exe("deno").read_bytes() == b"OLD"
