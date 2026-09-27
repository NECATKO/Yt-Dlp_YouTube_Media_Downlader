"""Tests for the portable runtime (ytdlp_app.portable). No network access."""

import hashlib
import io
import json
import os
import stat
import sys
import tarfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ytdlp_app import portable
from ytdlp_app.portable import (
    LockEntry,
    PortableError,
    RuntimeLayout,
    configure_environment,
    download,
    ensure_component,
    ensure_ytdlp,
    extract_component,
    find_entry,
    load_state,
    parse_lock,
    platform_key,
)

REPO_LOCK = Path(__file__).resolve().parent.parent / "runtime.lock"
SHA = "a" * 64


class TestPlatformKey:
    @pytest.mark.parametrize(
        ("system", "machine", "expected"),
        [
            ("Windows", "AMD64", "windows-x86_64"),
            ("Linux", "x86_64", "linux-x86_64"),
            ("Linux", "aarch64", "linux-aarch64"),
            ("Linux", "arm64", "linux-aarch64"),
            ("Darwin", "arm64", None),
            ("Linux", "armv7l", None),
        ],
    )
    def test_maps_machines(self, system: str, machine: str, expected: str | None) -> None:
        assert platform_key(system, machine) == expected


class TestLockFile:
    def test_shipped_lock_covers_every_supported_platform(self) -> None:
        entries = parse_lock(REPO_LOCK.read_text(encoding="utf-8"))
        for component in ("python", "ffmpeg", "deno"):
            for key in ("windows-x86_64", "linux-x86_64", "linux-aarch64"):
                entry = find_entry(entries, component, key)
                assert entry.url.startswith("https://github.com/")

    def test_ignores_comments_and_blank_lines(self) -> None:
        text = f"# comment\n\nffmpeg linux-x86_64 {SHA} https://example.com/f.tar.xz\n"
        assert parse_lock(text) == [
            LockEntry("ffmpeg", "linux-x86_64", SHA, "https://example.com/f.tar.xz")
        ]

    @pytest.mark.parametrize(
        "line",
        [
            f"ffmpeg linux-x86_64 {SHA}",
            f"ffmpeg linux-x86_64 {'z' * 64} https://example.com/f",
            f"ffmpeg linux-x86_64 {SHA} http://example.com/f",
        ],
    )
    def test_rejects_malformed_pins(self, line: str) -> None:
        with pytest.raises(PortableError):
            parse_lock(line)

    def test_missing_platform_is_an_error(self) -> None:
        with pytest.raises(PortableError, match="no deno build"):
            find_entry([], "deno", "linux-x86_64")


class TestLayout:
    def test_windows_paths(self, tmp_path: Path) -> None:
        layout = RuntimeLayout(tmp_path, windows=True)
        assert layout.python_exe == tmp_path / "runtime" / "python" / "python.exe"
        assert layout.component_exe("ffmpeg") == tmp_path / "runtime" / "ffmpeg" / "ffmpeg.exe"

    def test_linux_paths(self, tmp_path: Path) -> None:
        layout = RuntimeLayout(tmp_path, windows=False)
        assert layout.python_exe == tmp_path / "runtime" / "python" / "bin" / "python3"
        assert layout.component_exe("deno") == tmp_path / "runtime" / "deno" / "deno"


class TestConfigureEnvironment:
    def _install_fake(self, app_dir: Path, component: str) -> Path:
        folder = app_dir / "runtime" / component
        folder.mkdir(parents=True)
        (folder / component).write_text("")
        return folder

    def test_bundled_tools_go_first_on_path(self, tmp_path: Path) -> None:
        ffmpeg_dir = self._install_fake(tmp_path, "ffmpeg")
        deno_dir = self._install_fake(tmp_path, "deno")
        env = {"PATH": "/usr/bin"}

        configure_environment(tmp_path, env, windows=False)

        assert env["PATH"].split(os.pathsep) == [str(ffmpeg_dir), str(deno_dir), "/usr/bin"]

    def test_missing_tools_are_not_added(self, tmp_path: Path) -> None:
        env = {"PATH": "/usr/bin"}
        configure_environment(tmp_path, env, windows=False)
        assert env["PATH"] == "/usr/bin"

    def test_caches_stay_inside_the_app_folder(self, tmp_path: Path) -> None:
        env: dict[str, str] = {}
        configure_environment(tmp_path, env, windows=False)
        assert env["XDG_CACHE_HOME"] == str(tmp_path / "cache")
        assert env["DENO_DIR"] == str(tmp_path / "cache" / "deno")


class FakeResponse(io.BytesIO):
    def __init__(self, payload: bytes) -> None:
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}


def _opener_for(payload: bytes):
    def opener(_request: Any, **_kwargs: Any) -> FakeResponse:
        return FakeResponse(payload)

    return opener


class TestDownload:
    PAYLOAD = b"portable runtime" * 1000

    def _entry(self, sha: str) -> LockEntry:
        return LockEntry("deno", "linux-x86_64", sha, "https://example.com/deno.zip")

    def test_verified_file_is_kept(self, tmp_path: Path) -> None:
        sha = hashlib.sha256(self.PAYLOAD).hexdigest()
        dest = tmp_path / "deno.zip"

        download(self._entry(sha), dest, opener=_opener_for(self.PAYLOAD), progress=None)

        assert dest.read_bytes() == self.PAYLOAD
        assert not (tmp_path / "deno.zip.part").exists()

    def test_checksum_mismatch_discards_everything(self, tmp_path: Path) -> None:
        dest = tmp_path / "deno.zip"
        with pytest.raises(PortableError, match="Checksum mismatch"):
            download(self._entry(SHA), dest, opener=_opener_for(self.PAYLOAD), progress=None)
        assert list(tmp_path.iterdir()) == []

    def test_network_error_is_reported_and_cleaned_up(self, tmp_path: Path) -> None:
        def broken(_request: Any, **_kwargs: Any) -> Any:
            raise OSError("connection reset")

        with pytest.raises(PortableError, match="connection reset"):
            download(self._entry(SHA), tmp_path / "deno.zip", opener=broken, progress=None)
        assert list(tmp_path.iterdir()) == []


def _zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


def _tar_xz(path: Path, members: dict[str, bytes]) -> Path:
    with tarfile.open(path, "w:xz") as tf:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return path


class TestExtract:
    def test_windows_ffmpeg_keeps_the_bin_folder_only(self, tmp_path: Path) -> None:
        archive = _zip(
            tmp_path / "ffmpeg-win64-gpl-shared.zip",
            {
                "ffmpeg-N-win64/bin/ffmpeg.exe": b"exe",
                "ffmpeg-N-win64/bin/ffprobe.exe": b"exe",
                "ffmpeg-N-win64/bin/avcodec-62.dll": b"dll",
                "ffmpeg-N-win64/bin/ffplay.exe": b"player the app never uses",
                "ffmpeg-N-win64/doc/ffmpeg.html": b"doc",
                "ffmpeg-N-win64/LICENSE.txt": b"gpl",
            },
        )
        target = tmp_path / "runtime" / "ffmpeg"

        extract_component("ffmpeg", archive, target, windows=True)

        assert sorted(p.name for p in target.iterdir()) == [
            "avcodec-62.dll",
            "ffmpeg.exe",
            "ffprobe.exe",
        ]

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
    def test_linux_ffmpeg_is_executable(self, tmp_path: Path) -> None:
        archive = _tar_xz(
            tmp_path / "ffmpeg-linux64-gpl.tar.xz",
            {"ffmpeg-N-linux64/bin/ffmpeg": b"elf", "ffmpeg-N-linux64/bin/ffprobe": b"elf"},
        )
        target = tmp_path / "ffmpeg"

        extract_component("ffmpeg", archive, target, windows=False)

        mode = (target / "ffmpeg").stat().st_mode
        assert mode & stat.S_IXUSR

    def test_deno(self, tmp_path: Path) -> None:
        archive = _zip(tmp_path / "deno.zip", {"deno": b"elf"})
        target = tmp_path / "deno"

        extract_component("deno", archive, target, windows=False)

        assert (target / "deno").read_bytes() == b"elf"

    def test_members_cannot_escape_the_target(self, tmp_path: Path) -> None:
        archive = _zip(
            tmp_path / "evil.zip",
            {"x/bin/ffmpeg": b"elf", "../../bin/evil": b"payload", "x/bin/../../../evil2": b"p"},
        )
        target = tmp_path / "app" / "runtime" / "ffmpeg"

        extract_component("ffmpeg", archive, target, windows=False)

        assert sorted(p.name for p in target.iterdir()) == ["evil", "ffmpeg"]
        assert not (tmp_path / "bin").exists()
        assert not (tmp_path / "evil2").exists()

    def test_archive_without_the_executable_keeps_the_old_copy(self, tmp_path: Path) -> None:
        target = tmp_path / "ffmpeg"
        target.mkdir()
        (target / "ffmpeg").write_bytes(b"old")
        archive = _zip(tmp_path / "wrong.zip", {"x/doc/readme": b"nothing useful"})

        with pytest.raises(PortableError, match="does not contain ffmpeg"):
            extract_component("ffmpeg", archive, target, windows=False)

        assert (target / "ffmpeg").read_bytes() == b"old"


class TestEnsureComponent:
    def _setup(self, tmp_path: Path) -> tuple[RuntimeLayout, list[LockEntry], list[LockEntry]]:
        layout = RuntimeLayout(tmp_path, windows=False)
        entries = [LockEntry("deno", "linux-x86_64", SHA, "https://example.com/deno.zip")]
        fetched: list[LockEntry] = []
        return layout, entries, fetched

    def _downloader(self, fetched: list[LockEntry]):
        def fake(entry: LockEntry, dest: Path) -> Path:
            fetched.append(entry)
            dest.parent.mkdir(parents=True, exist_ok=True)
            return _zip(dest, {"deno": b"elf"})

        return fake

    def test_installs_and_records_the_pin(self, tmp_path: Path) -> None:
        layout, entries, fetched = self._setup(tmp_path)
        state: dict[str, Any] = {}

        changed = ensure_component(
            "deno", layout, entries, "linux-x86_64", state, downloader=self._downloader(fetched)
        )

        assert changed is True
        assert layout.component_exe("deno").exists()
        assert load_state(layout)["components"]["deno"]["sha256"] == SHA
        # The downloaded archive does not linger.
        assert not any((layout.runtime_dir / "downloads").iterdir())

    def test_current_pin_is_not_downloaded_again(self, tmp_path: Path) -> None:
        layout, entries, fetched = self._setup(tmp_path)
        state: dict[str, Any] = {}
        downloader = self._downloader(fetched)
        ensure_component("deno", layout, entries, "linux-x86_64", state, downloader=downloader)

        changed = ensure_component(
            "deno", layout, entries, "linux-x86_64", state, downloader=downloader
        )

        assert changed is False
        assert len(fetched) == 1

    def test_a_new_pin_replaces_the_old_build(self, tmp_path: Path) -> None:
        layout, entries, fetched = self._setup(tmp_path)
        state: dict[str, Any] = {"components": {"deno": {"sha256": "b" * 64}}}
        layout.component_dir("deno").mkdir(parents=True)
        layout.component_exe("deno").write_bytes(b"old")

        changed = ensure_component(
            "deno", layout, entries, "linux-x86_64", state, downloader=self._downloader(fetched)
        )

        assert changed is True
        assert layout.component_exe("deno").read_bytes() == b"elf"


class FakePip:
    """Stands in for subprocess.run: answers the import probe and pip installs."""

    def __init__(self, *, installed: bool, pip_ok: bool = True) -> None:
        self.installed = installed
        self.pip_ok = pip_ok
        self.pip_calls = 0

    def __call__(self, cmd: list[str], **_kwargs: Any) -> SimpleNamespace:
        if "pip" in cmd:
            self.pip_calls += 1
            if self.pip_ok:
                self.installed = True
            return SimpleNamespace(returncode=0 if self.pip_ok else 1)
        return SimpleNamespace(returncode=0 if self.installed else 1)


NOW = datetime(2026, 9, 27, 12, 0, 0)


class TestEnsureYtdlp:
    def _layout(self, tmp_path: Path) -> RuntimeLayout:
        return RuntimeLayout(tmp_path, windows=False)

    def test_first_install(self, tmp_path: Path) -> None:
        runner = FakePip(installed=False)
        state: dict[str, Any] = {}

        ensure_ytdlp(self._layout(tmp_path), state, now=NOW, runner=runner)

        assert runner.pip_calls == 1
        assert state["ytdlp_updated_at"] == NOW.isoformat(timespec="seconds")

    def test_failed_first_install_is_fatal(self, tmp_path: Path) -> None:
        runner = FakePip(installed=False, pip_ok=False)
        with pytest.raises(PortableError, match="could not install yt-dlp"):
            ensure_ytdlp(self._layout(tmp_path), {}, now=NOW, runner=runner)

    def test_recent_install_is_left_alone(self, tmp_path: Path) -> None:
        runner = FakePip(installed=True)
        state = {
            "ytdlp_updated_at": (NOW - timedelta(days=2)).isoformat(),
            "ytdlp_requirement": portable.YTDLP_REQUIREMENT,
        }

        ensure_ytdlp(self._layout(tmp_path), state, now=NOW, runner=runner)

        assert runner.pip_calls == 0

    def test_changed_requirement_installs_right_away(self, tmp_path: Path) -> None:
        """An install from before curl-cffi was added gets it on the next launch."""
        runner = FakePip(installed=True)
        state = {
            "ytdlp_updated_at": (NOW - timedelta(days=1)).isoformat(),
            "ytdlp_requirement": "yt-dlp[default]",
        }

        ensure_ytdlp(self._layout(tmp_path), state, now=NOW, runner=runner)

        assert runner.pip_calls == 1
        assert state["ytdlp_requirement"] == portable.YTDLP_REQUIREMENT

    def test_requirement_includes_impersonation(self) -> None:
        """Without curl-cffi YouTube rejects every subtitle request with HTTP 429."""
        assert "curl-cffi" in portable.YTDLP_REQUIREMENT

    def test_stale_install_is_upgraded(self, tmp_path: Path) -> None:
        runner = FakePip(installed=True)
        state = {"ytdlp_updated_at": (NOW - timedelta(days=8)).isoformat()}

        ensure_ytdlp(self._layout(tmp_path), state, now=NOW, runner=runner)

        assert runner.pip_calls == 1
        assert state["ytdlp_updated_at"] == NOW.isoformat(timespec="seconds")

    def test_failed_upgrade_is_not_fatal(self, tmp_path: Path) -> None:
        """Offline launches must still work with the installed yt-dlp."""
        runner = FakePip(installed=True, pip_ok=False)
        old = (NOW - timedelta(days=30)).isoformat()
        state = {"ytdlp_updated_at": old}

        ensure_ytdlp(self._layout(tmp_path), state, now=NOW, runner=runner)

        assert state["ytdlp_updated_at"] == old

    def test_forced_update(self, tmp_path: Path) -> None:
        runner = FakePip(installed=True)
        state = {"ytdlp_updated_at": NOW.isoformat()}

        ensure_ytdlp(self._layout(tmp_path), state, now=NOW, runner=runner, force_update=True)

        assert runner.pip_calls == 1


class TestEnsure:
    def test_refuses_to_run_without_the_portable_python(self, tmp_path: Path) -> None:
        with pytest.raises(PortableError, match="install"):
            portable.ensure(RuntimeLayout(tmp_path), update_days=7)

    def test_status_command(self, capsys) -> None:
        assert portable.main(["status"]) == 0
        assert "Python" in capsys.readouterr().out

    def test_corrupt_state_is_treated_as_empty(self, tmp_path: Path) -> None:
        layout = RuntimeLayout(tmp_path)
        layout.runtime_dir.mkdir()
        layout.state_file.write_text("{not json", encoding="utf-8")
        assert load_state(layout) == {}
        layout.state_file.write_text(json.dumps(["list"]), encoding="utf-8")
        assert load_state(layout) == {}
