# Aşama 1 — Arşiv kanıtı (B02, B04, B05) — uygulama planı

> **Uygulayıcı için:** ZORUNLU ALT-BECERİ: `superpowers:executing-plans` (bu oturumda doğrudan) ya da `superpowers:subagent-driven-development`. Adımlar `- [ ]` kutularıyla izlenir.

**Hedef:** Arşiv denetimi ve indirme sonucu, bir öğenin "diskte var" olduğuna yalnızca moda uygun gerçek bir medya dosyasıyla karar versin. Tek video yeniden verildiğinde silinmiş dosya "zaten mevcut" sayılmasın. Program klasörü taşındığında manifest yolları geçerli kalsın.

**Mimari:** Yeni `ytdlp_app/evidence.py` tek karar noktası olur: medya dosyası tanıma, kimlikle dosya dizini ve `locate()`. Bunu hem `archive_audit` hem `outcome.evaluate` kullanır. Böylece audit ile oturum aynı dosya için aynı sonucu verir. Ledger eklentisi program klasörü içindeki dosyaları manifest klasörüne göreli yazar, dışarıdakileri mutlak bırakır. `read_manifest` iki biçimi de okur.

**Teknoloji:** Python ≥ 3.11, yalnızca stdlib; pytest, ruff, mypy.

**Spec:** `degerlendirme-raporlari/2026-10-02/master-prompt.md` §1 "B02/B04/B05" + `inceleme-raporu.md` B02/B04/B05. Yol haritası: `docs/superpowers/plans/2026-10-02-review-roadmap.md`.

## Genel kısıtlar

- Satır uzunluğu 100; `from __future__ import annotations`; `TYPE_CHECKING` import'ları; kod/yorum/commit İngilizce, kullanıcı metinleri `en.json` + `tr.json` (doğal Türkçe, aynı yer tutucular).
- Ağa çıkan test yok; her şey `tmp_path` altında.
- Audit raporu ve önizleme hiçbir şey yazmaz. Uygulama (`--apply`) önce yedek alır. Bu davranış korunur.
- Kanıt olmadan arşiv kaydı silinmez: manifesti olmayan eski kayıt, medya bulunamazsa `UNVERIFIED` olur, asla `MISSING` olmaz.
- Mevcut indirme arşivi adları ve config'in göreli yol politikası değişmez.
- Commit'ler `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` ile biter. Push yok.
- Doğrulama: `.venv/bin/python -m pytest -q`, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/mypy ytdlp_app --ignore-missing-imports`.

## Gözden geçirme odağı

1. **Birleştirilmemiş biçim akışı** (`Başlık [id].f137.mp4`) ya da `Başlık [id].temp.mkv` kalıntısı medya kanıtı sayılmamalı → Görev 1 testi.
2. **Arşiv modu dosyası adında kimlik taşımaz** (`.../T [id]/T.mkv`); kimlik klasör adındadır. Klasördeki medya kanıt sayılmalı, ama yalnız klasör ya da `.info.json` sayılmamalı → Görev 1 ve Görev 2 testleri.
3. **Windows'ta farklı sürücüdeki dış klasör:** `os.path.relpath` `ValueError` verir; mutlak yol yazılmalı, öğe başarısız olmamalı → Görev 3 testi (relpath'i taklit ederek).
4. **Eski (v1) manifeste yeni satır eklenmesi:** başlıksız eski dosyaya göreli satır eklenir. Okuyucu satır satır karar vermeli ve iki biçimi de doğru çözmeli → Görev 3 testi.
5. **Kimliği URL'den çıkmayan tek öğe** (başka site, kanalın `/live` adresi): "zaten mevcut" denmemeli, "denetlenemedi" denmeli; başarısızlık da sayılmamalı → Görev 4 testi.

---

### Görev 1: `evidence.py` — medya dosyası, dizin, `locate()`

**Dosyalar:**
- Oluştur: `ytdlp_app/evidence.py`
- Test: `tests/test_evidence.py`

**Arayüz (sonraki görevler bunları kullanır):**
- `class EvidenceStatus(StrEnum)`: `PRESENT`, `MISSING`, `UNVERIFIED`
- `@dataclass(frozen=True, slots=True) class Evidence: status: EvidenceStatus; path: Path | None = None`
- `mode_of_archive(archive: Path) -> DownloadMode | None`
- `is_media_file(path: Path, mode: DownloadMode | None) -> bool`
- `class MediaIndex(roots: Iterable[Path])` ve metodu `files_for(ident: str, mode: DownloadMode | None) -> tuple[Path, ...]`
- `locate(ident: str, recorded: Path | None, *, mode: DownloadMode | None, index: MediaIndex) -> Evidence`

- [ ] **Adım 1: Başarısız testleri yaz** (`tests/test_evidence.py`)

```python
"""Whether a download's file is really on disk."""

from pathlib import Path

import pytest

from ytdlp_app.evidence import (
    EvidenceStatus,
    MediaIndex,
    is_media_file,
    locate,
    mode_of_archive,
)
from ytdlp_app.models import DownloadMode


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    return path


class TestModeOfArchive:
    @pytest.mark.parametrize(
        ("name", "mode"),
        [
            ("single_videos_mp4.txt", DownloadMode.VIDEO),
            ("playlist_PL1_mp4.txt", DownloadMode.VIDEO),
            ("single_audios_mp3.txt", DownloadMode.AUDIO),
            ("channel_UC1_mp3.txt", DownloadMode.AUDIO),
            ("channel_UC1_archive.txt", DownloadMode.ARCHIVE),
            ("a.txt", None),
        ],
    )
    def test_the_mode_comes_from_the_archive_name(self, name: str, mode) -> None:
        assert mode_of_archive(Path(name)) is mode


class TestIsMediaFile:
    def test_a_video_file_is_media_in_video_mode(self, tmp_path: Path) -> None:
        assert is_media_file(touch(tmp_path / "T [id].mp4"), DownloadMode.VIDEO)

    def test_an_mp3_is_not_evidence_for_a_video_record(self, tmp_path: Path) -> None:
        assert not is_media_file(touch(tmp_path / "T [id].mp3"), DownloadMode.VIDEO)

    def test_a_video_is_not_evidence_for_an_audio_record(self, tmp_path: Path) -> None:
        assert not is_media_file(touch(tmp_path / "T [id].mkv"), DownloadMode.AUDIO)

    @pytest.mark.parametrize(
        "name",
        [
            "T [id].mkv.part",
            "T [id].f137.mp4",
            "T [id].f251-1.webm",
            "T [id].temp.mkv",
            "T [id].info.json",
            "T [id].jpg",
            "T [id].en.srt",
            "T [id].description",
            "T [id].txt",
        ],
    )
    def test_leftovers_and_side_files_are_not_media(self, tmp_path: Path, name: str) -> None:
        assert not is_media_file(touch(tmp_path / name), None)

    def test_a_folder_is_not_media_even_with_a_media_suffix(self, tmp_path: Path) -> None:
        folder = tmp_path / "T [id].mkv"
        folder.mkdir()
        assert not is_media_file(folder, DownloadMode.VIDEO)

    def test_a_path_that_does_not_exist_is_not_media(self, tmp_path: Path) -> None:
        assert not is_media_file(tmp_path / "gone.mp4", DownloadMode.VIDEO)


class TestMediaIndex:
    def test_finds_a_file_by_the_id_in_its_name(self, tmp_path: Path) -> None:
        file = touch(tmp_path / "x" / "Song [abc].mp4")
        assert MediaIndex([tmp_path]).files_for("abc", DownloadMode.VIDEO) == (file,)

    def test_finds_an_archive_mode_file_by_the_id_of_its_folder(self, tmp_path: Path) -> None:
        file = touch(tmp_path / "Chan" / "20260101 - T [abc]" / "T.mkv")
        assert MediaIndex([tmp_path]).files_for("abc", DownloadMode.ARCHIVE) == (file,)

    def test_a_folder_with_only_side_files_gives_no_media(self, tmp_path: Path) -> None:
        folder = tmp_path / "Chan" / "20260101 - T [abc]"
        touch(folder / "T.info.json")
        touch(folder / "T.jpg")
        touch(folder / "T.mkv.part")
        assert MediaIndex([tmp_path]).files_for("abc", DownloadMode.ARCHIVE) == ()

    def test_the_mode_filters_the_matches(self, tmp_path: Path) -> None:
        touch(tmp_path / "Song [abc].mp3")
        index = MediaIndex([tmp_path])
        assert index.files_for("abc", DownloadMode.VIDEO) == ()
        assert len(index.files_for("abc", DownloadMode.AUDIO)) == 1

    def test_a_root_that_does_not_exist_is_ignored(self, tmp_path: Path) -> None:
        assert MediaIndex([tmp_path / "nope"]).files_for("abc", None) == ()


class TestLocate:
    def test_a_recorded_media_file_is_present(self, tmp_path: Path) -> None:
        file = touch(tmp_path / "a.mp4")
        found = locate("a", file, mode=DownloadMode.VIDEO, index=MediaIndex([tmp_path]))
        assert (found.status, found.path) == (EvidenceStatus.PRESENT, file)

    def test_a_recorded_file_that_is_gone_is_missing(self, tmp_path: Path) -> None:
        gone = tmp_path / "gone.mp4"
        found = locate("a", gone, mode=DownloadMode.VIDEO, index=MediaIndex([tmp_path]))
        assert (found.status, found.path) == (EvidenceStatus.MISSING, gone)

    def test_a_recorded_path_that_is_a_folder_is_missing(self, tmp_path: Path) -> None:
        folder = tmp_path / "T [a]"
        folder.mkdir()
        touch(folder / "T.info.json")
        found = locate("a", folder, mode=DownloadMode.ARCHIVE, index=MediaIndex([tmp_path]))
        assert found.status is EvidenceStatus.MISSING

    def test_a_moved_file_is_found_by_its_id(self, tmp_path: Path) -> None:
        moved = touch(tmp_path / "new" / "T [a].mkv")
        found = locate(
            "a", tmp_path / "old" / "T [a].mkv", mode=DownloadMode.VIDEO, index=MediaIndex([tmp_path])
        )
        assert (found.status, found.path) == (EvidenceStatus.PRESENT, moved)

    def test_a_record_without_a_path_and_without_media_is_unverified(self, tmp_path: Path) -> None:
        touch(tmp_path / "Old title.mp4")
        found = locate("a", None, mode=DownloadMode.VIDEO, index=MediaIndex([tmp_path]))
        assert (found.status, found.path) == (EvidenceStatus.UNVERIFIED, None)

    def test_a_record_without_a_path_is_present_when_its_media_is_found(
        self, tmp_path: Path
    ) -> None:
        file = touch(tmp_path / "T [a].mp4")
        found = locate("a", None, mode=DownloadMode.VIDEO, index=MediaIndex([tmp_path]))
        assert (found.status, found.path) == (EvidenceStatus.PRESENT, file)
```

- [ ] **Adım 2: Testi çalıştır, başarısız olduğunu gör**

`.venv/bin/python -m pytest tests/test_evidence.py -q` → `ModuleNotFoundError: ytdlp_app.evidence`

- [ ] **Adım 3: `ytdlp_app/evidence.py`'yi yaz**

```python
"""Whether a download's file is really on disk: one answer for the archive check and the run.

An archive record says an id is done, and the manifest says where its file went. Neither
proves the file is there. A folder named after the id, the info JSON or thumbnail beside it,
a ``.part`` left by an interrupted download, or another mode's file of the same video are all
on disk long after the video itself is gone. Only a finished media file of the kind the
mode produces counts here.

The archive check (archive_audit) and the run outcome (outcome.evaluate) both ask locate(),
so they cannot disagree about the same file.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from .models import DownloadMode

if TYPE_CHECKING:
    from collections.abc import Iterable

_BRACKET_ID = re.compile(r"\[([^\[\]/\\]+)\]")

#: What each mode leaves behind as its finished file. Archive mode writes MKV, video mode
#: MP4 or MKV (or WebM/MOV when the user chose to keep the source container); audio mode
#: the chosen format, or the source's own for "best".
VIDEO_SUFFIXES = frozenset({".mp4", ".mkv", ".webm", ".mov", ".m4v"})
AUDIO_SUFFIXES = frozenset(
    {".mp3", ".m4a", ".opus", ".ogg", ".oga", ".flac", ".wav", ".aac", ".webm", ".mka"}
)
_SUFFIXES: dict[DownloadMode | None, frozenset[str]] = {
    DownloadMode.VIDEO: VIDEO_SUFFIXES,
    DownloadMode.ARCHIVE: VIDEO_SUFFIXES,
    DownloadMode.AUDIO: AUDIO_SUFFIXES,
    None: VIDEO_SUFFIXES | AUDIO_SUFFIXES,
}

#: yt-dlp's intermediate files: unmerged format streams (``.f137.mp4``) and ``.temp`` files.
#: ``.part`` and ``.ytdl`` never have a media suffix, so the suffix check already drops them.
_LEFTOVER = re.compile(r"\.(?:f\d+(?:-\w+)?|temp)\.[^.]+$", re.IGNORECASE)

#: The archive name suffix each mode uses (see planning.archive_file_name).
_ARCHIVE_SUFFIX_MODES = (
    ("_mp4", DownloadMode.VIDEO),
    ("_mp3", DownloadMode.AUDIO),
    ("_archive", DownloadMode.ARCHIVE),
)


class EvidenceStatus(StrEnum):
    """What the disk says about one archived item."""

    PRESENT = "present"
    MISSING = "missing"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class Evidence:
    """The verdict on one item and the file it rests on (None when there is none)."""

    status: EvidenceStatus
    path: Path | None = None


def mode_of_archive(archive: Path) -> DownloadMode | None:
    """The download mode an archive file belongs to, read from its name (None if unknown)."""
    stem = archive.stem
    for suffix, mode in _ARCHIVE_SUFFIX_MODES:
        if stem.endswith(suffix):
            return mode
    return None


def _is_media_name(name: str, mode: DownloadMode | None) -> bool:
    return Path(name).suffix.lower() in _SUFFIXES[mode] and not _LEFTOVER.search(name)


def is_media_file(path: Path, mode: DownloadMode | None) -> bool:
    """Whether ``path`` is a finished media file of the kind ``mode`` produces."""
    if not _is_media_name(path.name, mode):
        return False
    try:
        return path.is_file()
    except OSError:
        return False


class MediaIndex:
    """Media files under the download folders, by the id in their name or their folder's.

    The folders are walked once, on the first lookup. Archive mode names the folder
    ``... [id]`` and the file after the title alone, so a file counts for the ids in its
    own name and in its folder's name.
    """

    def __init__(self, roots: Iterable[Path]) -> None:
        self._roots = [r for r in roots if r.is_dir()]
        self._files: dict[str, list[Path]] | None = None

    def _build(self) -> dict[str, list[Path]]:
        found: dict[str, list[Path]] = {}
        for root in self._roots:
            for folder, dirs, files in os.walk(root):
                dirs.sort()
                folder_ids = _BRACKET_ID.findall(Path(folder).name)
                for name in sorted(files):
                    if not _is_media_name(name, None):
                        continue
                    for ident in dict.fromkeys([*_BRACKET_ID.findall(name), *folder_ids]):
                        found.setdefault(ident, []).append(Path(folder) / name)
        return found

    def files_for(self, ident: str, mode: DownloadMode | None) -> tuple[Path, ...]:
        """The media files that carry ``ident`` and suit ``mode``."""
        if self._files is None:
            self._files = self._build()
        return tuple(
            p for p in self._files.get(ident, ()) if _is_media_name(p.name, mode)
        )


def locate(
    ident: str, recorded: Path | None, *, mode: DownloadMode | None, index: MediaIndex
) -> Evidence:
    """Decide whether item ``ident`` is on disk.

    The recorded path wins when it is a media file. Otherwise a media file carrying the id
    (a moved file, or an old record with no path) is accepted. A recorded path with nothing
    to back it is MISSING; a record that never had a path and matches nothing is UNVERIFIED,
    because files named after their title alone cannot be told apart.
    """
    if recorded is not None and is_media_file(recorded, mode):
        return Evidence(EvidenceStatus.PRESENT, recorded)
    matches = index.files_for(ident, mode)
    if matches:
        return Evidence(EvidenceStatus.PRESENT, matches[0])
    if recorded is not None:
        return Evidence(EvidenceStatus.MISSING, recorded)
    return Evidence(EvidenceStatus.UNVERIFIED)


__all__ = [
    "AUDIO_SUFFIXES",
    "VIDEO_SUFFIXES",
    "Evidence",
    "EvidenceStatus",
    "MediaIndex",
    "is_media_file",
    "locate",
    "mode_of_archive",
]
```

- [ ] **Adım 4: Testi çalıştır, geçtiğini gör** → `pytest tests/test_evidence.py -q` PASS; ardından ruff ve mypy.

- [ ] **Adım 5: Commit** — `feat: shared file evidence for archived items`

---

### Görev 2: Arşiv denetimi `evidence` kullanır (B02)

**Dosyalar:** Değiştir: `ytdlp_app/archive_audit.py`. Test: `tests/test_archive_audit.py`.

**Arayüz:** `FindingStatus` adı korunur (`FindingStatus = EvidenceStatus`, `__all__`'da kalır). `audit_archive(archive, roots, *, index: MediaIndex | None = None)`. `audit_all` tek bir `MediaIndex` kurar.

- [ ] **Adım 1: Başarısız testleri `TestAudit`'e ekle**

```python
    def test_a_folder_and_side_files_without_media_do_not_prove_a_record(
        self, world: dict[str, Path]
    ) -> None:
        """B02: the video was deleted, its folder and info JSON were left behind."""
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

    def test_repair_plans_only_proven_missing_records(self, world: dict[str, Path]) -> None:
        archive = write_archive(world, "channel_UC1_archive.txt", ["gone1", "old1"])
        write_manifest(archive, {"gone1": world["videos"] / "x [gone1]" / "x.mkv"})
        touch(world["videos"] / "y [old1]" / "y.info.json")

        plan = plan_repair(audit_archive(archive, [world["videos"]]))

        assert plan.remove == ("gone1",)
```

Mevcut `test_an_id_in_a_folder_name_counts_as_present` (klasörde `T.mkv` var) ve `test_a_moved_file_is_found_by_its_id` aynen geçmeli.

- [ ] **Adım 2: Çalıştır, başarısızlığı gör** → yeni testlerin ilk dördü `PRESENT` alır (B02'nin kendisi).

- [ ] **Adım 3: `archive_audit.py`'yi değiştir**
  - `_IdIndex` sınıfını ve `_BRACKET_ID`'yi sil; `os` ve `re` import'ları kullanılmıyorsa kaldır.
  - `from .evidence import EvidenceStatus, MediaIndex, is_media_file, locate, mode_of_archive` ekle.
  - `class FindingStatus(StrEnum)` yerine `FindingStatus = EvidenceStatus` yaz (yorumla: "kept under its old name for the report and the tests"). `StrEnum` import'u kullanılmıyorsa kaldır.
  - `audit_archive`:

```python
def audit_archive(
    archive: Path, roots: Sequence[Path], *, index: MediaIndex | None = None
) -> ArchiveReport:
    """Check every record of one archive against the disk. Writes nothing."""
    ids = list(dict.fromkeys(i for i in map(_id_of, _archive_lines(archive)) if i))
    manifest = read_manifest(_manifest_of(archive))
    media = index if index is not None else MediaIndex(roots)
    mode = mode_of_archive(archive)

    findings: list[Finding] = []
    for ident in ids:
        evidence = locate(ident, manifest.get(ident), mode=mode, index=media)
        findings.append(Finding(ident, evidence.status, evidence.path))

    known = set(ids)
    unarchived = tuple(
        i for i, p in manifest.items() if i not in known and is_media_file(p, mode)
    )
    return ArchiveReport(archive, tuple(findings), unarchived)
```

  - `audit_all`: `index = MediaIndex(roots)`.
  - Modül docstring'inin ikinci paragrafını güncelle: kanıt artık moda uygun bitmiş medya dosyasıdır; klasör, yan dosya, `.part` ve başka modun dosyası kanıt değildir (ayrıntı `evidence.py`'de).

- [ ] **Adım 4: Çalıştır** → `pytest tests/test_archive_audit.py tests/test_evidence.py -q` PASS.

- [ ] **Adım 5: Commit** — `fix: the archive check needs a real media file of the right kind (B02)`

---

### Görev 3: Taşınabilir manifest yolları (B05)

**Dosyalar:**
- Değiştir: `ytdlp_app/plugins/ledger/yt_dlp_plugins/postprocessor/ytdlp_app_ledger.py`, `ytdlp_app/yt_dlp.py` (`ledger_args`, `CommandBuilder`), `ytdlp_app/outcome.py` (`read_manifest`), `ytdlp_app/session.py` (`CommandBuilder(..., app_dir=self.paths.app_dir)`)
- Test: `tests/test_mp4_compat_plugin.py::TestLedger`, `tests/test_outcome.py` (read_manifest), `tests/test_yt_dlp.py`, `tests/test_engine_contract.py` (manifestin ilk satırını okuyan iki assert)

**Biçim (sürüm 2):** Dosya yeni oluşturulurken ilk satır `# ytdlp_app download manifest v2` olur. Her satır `<id>\t<path>` biçimindedir. `<path>` program klasörü (`root`) içindeyse manifest klasörüne göreli ve `/` ayraçlı yazılır, değilse mutlak kalır. Okuyucu `#` satırlarını atlar ve satır satır karar verir: göreli yolu manifest klasörüne göre çözer. Eski v1 dosyalar (başlıksız, mutlak) aynen okunur.

**Arayüz:**
- `ledger_args(manifest: Path, root: Path | None = None) -> list[str]`; `root` verilirse `;root=<encoded>` eklenir.
- `CommandBuilder(..., app_dir: Path | None = None)`; `_assemble` ve ikinci `ledger_args` çağrısı `ledger_args(self.manifest_path, self.app_dir)` kullanır.
- `DownloadLedgerPP(downloader=None, path=None, root=None)`.
- `MANIFEST_HEADER = "# ytdlp_app download manifest v2"` (eklentide sabit; eklenti `ytdlp_app`'i import edemez, bu yüzden `outcome.py` yalnızca `#` ile başlayan satırları atlar).

- [ ] **Adım 1: Başarısız testler**

`TestLedger`'a ekle; `test_appends_one_line_per_finished_item` beklentisi başlık satırıyla güncellenir (biçim bilerek sürümlendi):

```python
    def test_appends_one_line_per_finished_item(self, tmp_path: Path) -> None:
        module = _ledger_module()
        manifest = tmp_path / "state" / "a.files.tsv"
        pp = module.DownloadLedgerPP(None, str(manifest))

        pp.run({"id": "X1", "filepath": "/v/one.mkv"})
        pp.run({"id": "X2", "filepath": "/v/two.mkv"})

        assert manifest.read_text(encoding="utf-8").splitlines() == [
            module.MANIFEST_HEADER,
            "X1\t/v/one.mkv",
            "X2\t/v/two.mkv",
        ]

    def test_a_file_inside_the_program_folder_is_recorded_relative(self, tmp_path: Path) -> None:
        module = _ledger_module()
        manifest = tmp_path / "archives" / "a.files.tsv"
        media = tmp_path / "downloads" / "Videos" / "T [X1].mkv"

        module.DownloadLedgerPP(None, str(manifest), str(tmp_path)).run(
            {"id": "X1", "filepath": str(media)}
        )

        assert manifest.read_text(encoding="utf-8").splitlines()[1] == (
            "X1\t../downloads/Videos/T [X1].mkv"
        )

    def test_a_file_outside_the_program_folder_stays_absolute(self, tmp_path: Path) -> None:
        module = _ledger_module()
        app = tmp_path / "app"
        manifest = app / "archives" / "a.files.tsv"
        media = tmp_path / "elsewhere" / "T [X1].mkv"

        module.DownloadLedgerPP(None, str(manifest), str(app)).run(
            {"id": "X1", "filepath": str(media)}
        )

        assert manifest.read_text(encoding="utf-8").splitlines()[1] == f"X1\t{media}"

    def test_a_path_relpath_cannot_express_stays_absolute(self, tmp_path: Path, monkeypatch) -> None:
        """Windows: a file on another drive than the program has no relative path."""
        module = _ledger_module()
        manifest = tmp_path / "archives" / "a.files.tsv"
        media = tmp_path / "downloads" / "T [X1].mkv"

        def no_relpath(*_a, **_k):
            raise ValueError("path is on mount 'D:', start on mount 'C:'")

        monkeypatch.setattr(module.os.path, "relpath", no_relpath)
        module.DownloadLedgerPP(None, str(manifest), str(tmp_path)).run(
            {"id": "X1", "filepath": str(media)}
        )

        assert manifest.read_text(encoding="utf-8").splitlines()[1] == f"X1\t{media}"

    def test_an_old_manifest_gets_no_second_header(self, tmp_path: Path) -> None:
        module = _ledger_module()
        manifest = tmp_path / "a.files.tsv"
        manifest.write_text("X0\t/v/zero.mkv\n", encoding="utf-8")

        module.DownloadLedgerPP(None, str(manifest)).run({"id": "X1", "filepath": "/v/one.mkv"})

        assert manifest.read_text(encoding="utf-8").splitlines() == [
            "X0\t/v/zero.mkv",
            "X1\t/v/one.mkv",
        ]
```

`tests/test_outcome.py` (read_manifest sınıfına):

```python
    def test_relative_paths_resolve_against_the_manifest_folder(self, tmp_path: Path) -> None:
        manifest = tmp_path / "archives" / "a.files.tsv"
        manifest.parent.mkdir()
        manifest.write_text(
            "# ytdlp_app download manifest v2\nv1\t../downloads/T [v1].mkv\n", encoding="utf-8"
        )

        assert read_manifest(manifest) == {"v1": tmp_path / "archives" / "../downloads/T [v1].mkv"}

    def test_old_absolute_and_new_relative_lines_mix(self, tmp_path: Path) -> None:
        manifest = tmp_path / "archives" / "a.files.tsv"
        manifest.parent.mkdir()
        old = tmp_path / "old" / "a.mkv"
        manifest.write_text(f"a\t{old}\nb\t../downloads/b.mkv\n", encoding="utf-8")

        entries = read_manifest(manifest)

        assert entries["a"] == old
        assert entries["b"] == tmp_path / "archives" / "../downloads/b.mkv"

    def test_a_moved_program_folder_keeps_its_relative_records(self, tmp_path: Path) -> None:
        """B05: the whole folder moved; the relative line still finds the file."""
        moved = tmp_path / "moved"
        manifest = moved / "archives" / "a.files.tsv"
        media = moved / "downloads" / "T [v1].mkv"
        media.parent.mkdir(parents=True)
        media.write_bytes(b"x")
        manifest.parent.mkdir(parents=True)
        manifest.write_text("v1\t../downloads/T [v1].mkv\n", encoding="utf-8")

        assert read_manifest(manifest)["v1"].resolve() == media.resolve()
```

`tests/test_yt_dlp.py`'ye:

```python
    def test_the_program_folder_is_passed_to_the_ledger(self, tmp_path: Path) -> None:
        value = ledger_args(tmp_path / "a.files.tsv", tmp_path / "app;x")[1]
        assert value.endswith(";root=" + str(tmp_path / "app%3Bx"))

    def test_without_a_program_folder_there_is_no_root(self, tmp_path: Path) -> None:
        assert ";root=" not in ledger_args(tmp_path / "a.files.tsv")[1]
```

- [ ] **Adım 2: Çalıştır, başarısızlığı gör.**

- [ ] **Adım 3: Uygula**

Eklenti (`DownloadLedgerPP`):

```python
import os
...
#: First line of a manifest this version creates. Lines are "<id>\t<path>"; a path inside
#: the program folder is relative to the manifest's folder (so the folder can be moved),
#: anything else absolute. Older manifests have no header and only absolute paths.
MANIFEST_HEADER = "# ytdlp_app download manifest v2"


class DownloadLedgerPP(PostProcessor):
    """Append the finished item's id and final file path to a manifest."""

    def __init__(
        self, downloader: Any = None, path: str | None = None, root: str | None = None
    ) -> None:
        super().__init__(downloader)
        self._path = Path(unquote(path)) if path else None
        self._root = Path(unquote(root)) if root else None

    def _recorded(self, manifest: Path, filepath: str) -> str:
        """The path as written: relative to the manifest when inside the program folder."""
        if self._root is None:
            return filepath
        try:
            target = Path(filepath).resolve()
            target.relative_to(self._root.resolve())
            return Path(os.path.relpath(target, manifest.parent.resolve())).as_posix()
        except (ValueError, OSError):
            return filepath

    def run(self, info: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
        if self._path is None:
            return [], info
        item_id, filepath = info.get("id"), info.get("filepath")
        if not item_id or not filepath:
            return [], info
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            fresh = not self._path.exists() or self._path.stat().st_size == 0
            with self._path.open("a", encoding="utf-8", newline="\n") as manifest:
                if fresh:
                    manifest.write(MANIFEST_HEADER + "\n")
                manifest.write(f"{item_id}\t{self._recorded(self._path, filepath)}\n")
        except OSError as ex:
            ...  # unchanged
```

Eklenti docstring'ine `root` parametresini ekle (`...;path=<file>;root=<program folder>`).

`yt_dlp.py`:

```python
def _encode_option(value: Path) -> str:
    return str(value).replace("%", "%25").replace(";", "%3B")


def ledger_args(manifest: Path, root: Path | None = None) -> list[str]:
    """Arguments that append each finished item to a manifest (see DownloadLedger).

    With ``root`` (the program folder) files inside it are recorded relative to the
    manifest, so moving the whole folder keeps the records valid.
    """
    value = f"DownloadLedger:when=after_move;path={_encode_option(manifest)}"
    if root is not None:
        value += f";root={_encode_option(root)}"
    return ["--use-postprocessor", value]
```

Mevcut docstring'deki `%`/`;` notunu koru. `CommandBuilder.__init__`'e `app_dir: Path | None = None` ekle (`self.app_dir = app_dir`, docstring'e bir satır). İki `ledger_args(self.manifest_path)` çağrısı `ledger_args(self.manifest_path, self.app_dir)` olur. `session.py`'deki `CommandBuilder(...)` çağrısına `app_dir=self.paths.app_dir` ekle.

`outcome.read_manifest`:

```python
def read_manifest(path: Path) -> dict[str, Path]:
    """Read a download manifest: ``<id><TAB><path>`` lines, the last per id wins.

    ``#`` lines are comments (the format header). A relative path is relative to the
    manifest's folder (files inside the program folder); an absolute one is used as is.
    """
    entries: dict[str, Path] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entries
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        ident, sep, file = line.partition("\t")
        if sep and ident.strip() and file.strip():
            recorded = Path(file.strip())
            entries[ident.strip()] = recorded if recorded.is_absolute() else path.parent / recorded
    return entries
```

`tests/test_engine_contract.py` satır ~529 ve ~716: manifestin ilk satırı artık başlık. İlk kayıt satırını okuyan bir yardımcıyla düzelt:

```python
def first_record(manifest: Path) -> str:
    return next(l for l in manifest.read_text(encoding="utf-8").splitlines() if not l.startswith("#"))
```

Satır ~501'deki `lines` okuması da `#` satırlarını atlamalı. Değişikliğin nedeni commit mesajına yazılır.

- [ ] **Adım 4: Çalıştır** → `pytest tests/test_mp4_compat_plugin.py tests/test_outcome.py tests/test_yt_dlp.py tests/test_engine_contract.py -q` PASS.

- [ ] **Adım 5: Commit** — `fix: manifests survive moving the program folder (B05)`

---

### Görev 4: Sonuç modeli dosya kanıtını kullanır; tek videonun kimliği (B04)

**Dosyalar:**
- Değiştir: `ytdlp_app/outcome.py` (`RunOutcome.unverified`, `evaluate(locate=...)`, `describe`), `ytdlp_app/playlist.py` (`video_id_from_url`), `ytdlp_app/session.py` (beklenen kimlik, locator, not), `ytdlp_app/locales/en.json`, `tr.json`
- Test: `tests/test_outcome.py`, `tests/test_playlist.py`, `tests/test_session_outcomes.py`

**Arayüz:**
- `RunOutcome.unverified: int = 0`: arşivde zaten olan ama dosyası denetlenemeyen öğeler. Başarısızlık sayılmaz.
- `evaluate(..., locate: Callable[[str, Path | None], EvidenceStatus] | None = None)`; `path_exists` parametresi kalkar. Varsayılan locator: `None` → UNVERIFIED; dosya var → PRESENT; yok → MISSING.
- `video_id_from_url(url: str) -> str | None`.
- Locale anahtarı: `outcome_unverified` (`{count}`).

- [ ] **Adım 1: Başarısız testler**

`tests/test_playlist.py`:

```python
class TestVideoIdFromUrl:
    @pytest.mark.parametrize(
        ("url", "ident"),
        [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL1", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ?t=3", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://m.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/@chan/live", None),
            ("https://www.youtube.com/playlist?list=PL1", None),
            ("https://www.youtube.com/watch?v=short", None),
            ("https://vimeo.com/12345678901", None),
        ],
    )
    def test_the_id_a_single_video_url_names(self, url: str, ident: str | None) -> None:
        assert video_id_from_url(url) == ident
```

`tests/test_outcome.py`: iki mevcut testin beklentisi bilerek değişir (inceleme B04: kimliği/yolu bilinmeyen kayıt "denetlenemedi" olarak sunulur):

```python
    def test_an_old_record_without_manifest_entry_cannot_be_checked(self) -> None:
        outcome = evaluate(
            stage_codes=(0,),
            archive_before={"a"},
            archive_after={"a"},
            manifest={},
            expected_ids=["a"],
        )

        assert (outcome.already_present, outcome.unverified) == (0, 1)
        assert outcome.status is RunStatus.SUCCESS

    def test_a_single_item_of_unknown_id_skipped_by_the_archive_is_unverified(self) -> None:
        outcome = evaluate(
            stage_codes=(0,),
            archive_before={"a"},
            archive_after={"a"},
            manifest={},
            expected_ids=None,
        )

        assert (outcome.completed, outcome.already_present, outcome.unverified) == (0, 0, 1)
        assert outcome.status is RunStatus.SUCCESS
```

Yeni testler:

```python
    def test_a_single_video_rerun_whose_file_was_deleted_is_missing(self, tmp_path: Path) -> None:
        """B04: the archive skipped it, but the recorded file is gone."""
        outcome = evaluate(
            stage_codes=(0,),
            archive_before={"dQw4w9WgXcQ"},
            archive_after={"dQw4w9WgXcQ"},
            manifest={"dQw4w9WgXcQ": tmp_path / "T [dQw4w9WgXcQ].mp4"},
            expected_ids=["dQw4w9WgXcQ"],
        )

        assert outcome.missing == ("dQw4w9WgXcQ",)
        assert outcome.already_present == 0
        assert outcome.status is RunStatus.FAILED

    def test_the_locator_decides_what_is_on_disk(self) -> None:
        verdicts = {"a": EvidenceStatus.PRESENT, "b": EvidenceStatus.MISSING}
        outcome = evaluate(
            stage_codes=(0,),
            archive_before={"a", "b", "c"},
            archive_after={"a", "b", "c"},
            manifest={},
            expected_ids=["a", "b", "c"],
            locate=lambda ident, _path: verdicts.get(ident, EvidenceStatus.UNVERIFIED),
        )

        assert (outcome.already_present, outcome.missing, outcome.unverified) == (1, ("b",), 1)

    def test_unverified_items_get_their_own_line(self) -> None:
        lines = describe(RunOutcome(unverified=2))
        assert ("info", t("outcome_unverified", count=2)) in lines
```

`tests/test_session_outcomes.py`: tek video, arşivde kayıtlı, manifestteki dosya silinmiş, yt-dlp 0 dönüyor. Bu oturum başarı mesajı vermemeli, eksik dosyayı söylemeli ve arşiv araçlarına yönlendirmeli. Testi dosyadaki mevcut tek-video yardımcılarıyla yaz (`ScriptedUI`, `Recorder(rc=0, archive_writes=[])`, arşive önceden `youtube dQw4w9WgXcQ` satırı ve manifestte silinmiş yol). Beklenenler:

```python
        assert t("tasks_completed") not in ui.text()
        assert "dQw4w9WgXcQ" in ui.text()          # outcome_missing_items lists it
        assert t("archive_records_note") in ui.text()
```

- [ ] **Adım 2: Çalıştır, başarısızlığı gör.**

- [ ] **Adım 3: Uygula**

`playlist.py`:

```python
# A YouTube video id: 11 URL-safe base64 characters.
_VIDEO_ID_PATTERN = re.compile(r"^[\w-]{11}$")

# Path forms that carry a video id as their second segment.
_VIDEO_PATH_KINDS = ("shorts", "live", "embed", "v", "e")


def video_id_from_url(url: str) -> str | None:
    """The id of the video a single-video YouTube URL names, or None.

    None for other sites, playlists and channels, and a channel's ``/live`` address
    (its id is only known once it redirects).
    """
    if not is_youtube_host(url):
        return None
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    parts = [p for p in parsed.path.split("/") if p]
    candidate: str | None = None
    if host == "youtu.be" or host.endswith(".youtu.be"):
        candidate = parts[0] if parts else None
    elif "v" in (query := parse_qs(parsed.query)):
        candidate = query["v"][0]
    elif len(parts) >= 2 and parts[0].lower() in _VIDEO_PATH_KINDS:
        candidate = parts[1]
    return candidate if candidate and _VIDEO_ID_PATTERN.match(candidate) else None
```

`outcome.py`:
- `from .evidence import EvidenceStatus` (çalışma zamanında gerekli).
- `RunOutcome`'a `unverified: int = 0` alanını ekle ve docstring'ine yaz ("Items the archive already held whose file could not be checked (no recorded path, no id in a name, or a single item of unknown id). Not a failure.").
- `evaluate`:

```python
def _by_existence(_ident: str, path: Path | None) -> EvidenceStatus:
    if path is None:
        return EvidenceStatus.UNVERIFIED
    return EvidenceStatus.PRESENT if path.exists() else EvidenceStatus.MISSING
```

  Gövde: `check = locate or _by_existence`.
  - Yeni kayıtlarda: `if check(ident, manifest.get(ident)) is EvidenceStatus.MISSING: missing.append(ident) else: completed += 1`.
  - Beklenen kayıtlarda, `ident in before` için: PRESENT → `already_present += 1`, MISSING → `missing`, UNVERIFIED → `unverified += 1`.
  - Tek öğe ve kimlik bilinmiyorsa, eski `already_present = 1` dalı `unverified = 1` olur. `failed_unknown` dalı `already_present = 0` yerine `unverified = 0` yapar.
  - `path_exists` parametresi ve docstring satırı kalkar; `locate` docstring'e eklenir.
- `describe`: `already_present` satırından sonra `if outcome.unverified: lines.append(("info", t("outcome_unverified", count=outcome.unverified)))`.

Locale:
- en: `"outcome_unverified": "{count} item(s) were already in the archive, but their file could not be checked"`
- tr: `"outcome_unverified": "{count} öğe arşivde zaten kayıtlıydı, ancak dosyası denetlenemedi"`

`session.py` (indirme değerlendirmesi):

```python
        expected_ids: list[str] | None
        if plan.is_playlist:
            expected_ids = [e.id for e in entries if e.id] if listing else None
        else:
            single = video_id_from_url(url)
            expected_ids = [single] if single else None
        media = MediaIndex([plan.base_dir])
        outcome = evaluate(
            ...,
            expected_ids=expected_ids,
            ...,
            locate=lambda ident, path: locate(ident, path, mode=mode, index=media).status,
        )
```

  Log satırına `unverified={outcome.unverified}` eklenir. `if outcome.already_present:` notu `if outcome.already_present or outcome.unverified:` olur. `FAILED` dalında, `handle_error`'dan önce `if outcome.missing: self.ui.print(paint(t("archive_records_note"), Colors.CYAN))` eklenir; böylece kullanıcı onarım yolunu görür.

- [ ] **Adım 4: Tüm paketi çalıştır** → `pytest -q`. Tek videonun "zaten mevcut" metnini bekleyen eski oturum testleri varsa yeni sözleşmeye göre güncellenir; her birinin nedeni commit mesajına yazılır.

- [ ] **Adım 5: Commit** — `fix: a rerun single video is checked against its file (B04)`

---

### Görev 5: Aşama kapanışı

- [ ] Tam kontroller: pytest, ruff check, ruff format --check, mypy, `scripts/check_version.py`, `bash -n run.sh install.sh update.sh`.
- [ ] İnceleme deneyini tekrar et: `REVIEW_ENGINE_PYTHON=... .venv/bin/python degerlendirme-raporlari/2026-10-02/probes.py` içindeki B02/B04/B05 denemeleri (betiğin çıktısı yeni davranışı göstermeli; betik eski davranışı "beklenen" diye kodladıysa sonucu raporda açıkla, betiği değiştirme).
- [ ] `CHANGELOG.md` `[Unreleased]` → "Fixed" altına B02/B04/B05 maddeleri; `TASKS.md`'ye 2 Ekim incelemesi bölümü ve Aşama 1 durumu; yol haritasındaki durum tablosu.
- [ ] Commit — `docs: stage 1 of the 2026-10-02 review in CHANGELOG and TASKS`
