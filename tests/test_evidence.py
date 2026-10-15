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
            ("single_videos_archive.txt", DownloadMode.ARCHIVE),
            ("a.txt", None),
        ],
    )
    def test_the_mode_comes_from_the_archive_name(
        self, name: str, mode: DownloadMode | None
    ) -> None:
        assert mode_of_archive(Path(name)) is mode


class TestIsMediaFile:
    def test_a_video_file_is_media_in_video_mode(self, tmp_path: Path) -> None:
        assert is_media_file(touch(tmp_path / "T [id].mp4"), DownloadMode.VIDEO)

    def test_an_mp3_is_not_evidence_for_a_video_record(self, tmp_path: Path) -> None:
        assert not is_media_file(touch(tmp_path / "T [id].mp3"), DownloadMode.VIDEO)

    def test_a_video_is_not_evidence_for_an_audio_record(self, tmp_path: Path) -> None:
        assert not is_media_file(touch(tmp_path / "T [id].mkv"), DownloadMode.AUDIO)

    def test_the_suffix_is_matched_without_regard_to_case(self, tmp_path: Path) -> None:
        assert is_media_file(touch(tmp_path / "T [id].MP4"), DownloadMode.VIDEO)

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

    def test_the_folders_are_walked_once(self, tmp_path: Path) -> None:
        touch(tmp_path / "Song [abc].mp4")
        index = MediaIndex([tmp_path])
        index.files_for("abc", None)
        touch(tmp_path / "Other [def].mp4")

        assert index.files_for("def", None) == ()


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
            "a",
            tmp_path / "old" / "T [a].mkv",
            mode=DownloadMode.VIDEO,
            index=MediaIndex([tmp_path]),
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


A = "AAAAAAAAAAA"
B = "BBBBBBBBBBB"


class TestWhichIdANameCarries:
    """D10: only the id field of the default templates counts, never a title's brackets."""

    def test_a_title_quoting_another_id_is_evidence_only_for_the_last_one(
        self, tmp_path: Path
    ) -> None:
        touch(tmp_path / f"A title quoting [{A}] [{B}].mkv")
        index = MediaIndex([tmp_path])

        assert index.files_for(A, DownloadMode.VIDEO) == ()
        assert len(index.files_for(B, DownloadMode.VIDEO)) == 1

    def test_an_archive_folder_counts_for_its_last_id_not_the_titles(self, tmp_path: Path) -> None:
        # Archive layout: "<date> - <title> [<id>]/<title>.mkv", the title quoting A.
        folder = tmp_path / "Chan" / f"20260101 - Quote [{A}] [{B}]"
        media = touch(folder / f"Quote [{A}].mkv")
        index = MediaIndex([tmp_path])

        assert index.files_for(A, DownloadMode.ARCHIVE) == ()
        assert index.files_for(B, DownloadMode.ARCHIVE) == (media,)

    def test_an_archive_folder_and_a_file_naming_different_ids_prove_neither(
        self, tmp_path: Path
    ) -> None:
        touch(tmp_path / "Chan" / f"20260101 - Something [{B}]" / f"Other [{A}].mkv")
        index = MediaIndex([tmp_path])

        assert index.files_for(A, DownloadMode.ARCHIVE) == ()
        assert index.files_for(B, DownloadMode.ARCHIVE) == ()

    def test_a_playlist_folder_ending_in_brackets_does_not_hide_the_files_id(
        self, tmp_path: Path
    ) -> None:
        media = touch(tmp_path / "Best of [2020]" / f"001 - Song [{A}].mp4")
        index = MediaIndex([tmp_path])

        assert index.files_for(A, DownloadMode.VIDEO) == (media,)
        assert index.files_for("2020", DownloadMode.VIDEO) == ()

    def test_the_same_id_in_folder_and_file_is_one_match(self, tmp_path: Path) -> None:
        media = touch(tmp_path / f"20260101 - T [{A}]" / f"T [{A}].mkv")

        assert MediaIndex([tmp_path]).files_for(A, DownloadMode.ARCHIVE) == (media,)


class TestUnfinishedConversion:
    """D11: the MP4 compatibility step's work file is not a finished download."""

    @pytest.mark.parametrize("name", [f"T [{A}].compat.mp4", f"T [{A}].COMPAT.MP4"])
    def test_a_compat_work_file_is_not_media(self, tmp_path: Path, name: str) -> None:
        path = touch(tmp_path / name)

        assert not is_media_file(path, DownloadMode.VIDEO)
        assert MediaIndex([tmp_path]).files_for(A, DownloadMode.VIDEO) == ()

    def test_a_record_pointing_at_the_work_file_is_missing(self, tmp_path: Path) -> None:
        work = touch(tmp_path / f"T [{A}].compat.mp4")

        verdict = locate(
            A, tmp_path / f"T [{A}].mp4", mode=DownloadMode.VIDEO, index=MediaIndex([tmp_path])
        )

        assert verdict.status is EvidenceStatus.MISSING
        assert verdict.path != work
