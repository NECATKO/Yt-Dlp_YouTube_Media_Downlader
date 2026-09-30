"""Where a download goes and which archive file remembers it."""

from pathlib import Path
from typing import Any

import pytest

import ytdlp_app.planning as planning
from ytdlp_app.exceptions import ValidationError
from ytdlp_app.models import DownloadMode, UserConfig
from ytdlp_app.planning import archive_file_name, ensure_within, plan_targets
from ytdlp_app.settings import AppSettings

CHANNEL_ID = "UCuAXFkgsw1L7xaCfnd5JJOw"
V, A, X = DownloadMode.VIDEO, DownloadMode.AUDIO, DownloadMode.ARCHIVE


@pytest.fixture
def config(tmp_path: Path) -> UserConfig:
    return UserConfig(app="a", videos_dir=tmp_path / "Videos", music_dir=tmp_path / "Music")


class TestArchiveFileName:
    @pytest.mark.parametrize(
        ("mode", "expected"),
        [
            (V, "playlist_PLabc_mp4.txt"),
            (A, "playlist_PLabc_mp3.txt"),
            (X, "playlist_PLabc_archive.txt"),
        ],
    )
    def test_playlists_are_named_by_their_id(self, mode: DownloadMode, expected: str) -> None:
        name = archive_file_name(mode, is_playlist=True, is_channel=False, key="PLabc")

        assert name == expected

    @pytest.mark.parametrize(
        ("mode", "expected"),
        [
            (V, "channel_" + CHANNEL_ID + "_mp4.txt"),
            (A, "channel_" + CHANNEL_ID + "_mp3.txt"),
            (X, "channel_" + CHANNEL_ID + "_archive.txt"),
        ],
    )
    def test_channels_are_named_by_their_channel_id_in_every_mode(
        self, mode: DownloadMode, expected: str
    ) -> None:
        name = archive_file_name(mode, is_playlist=True, is_channel=True, key=CHANNEL_ID)

        assert name == expected

    @pytest.mark.parametrize(
        ("mode", "expected"),
        [
            (V, "single_videos_mp4.txt"),
            (A, "single_audios_mp3.txt"),
            (X, "single_videos_archive.txt"),
        ],
    )
    def test_single_items_share_one_archive_per_mode(
        self, mode: DownloadMode, expected: str
    ) -> None:
        assert archive_file_name(mode, is_playlist=False, is_channel=False, key=None) == expected

    @pytest.mark.parametrize(
        "hostile",
        ["/../../outside", "..", "a/b", "a\\b", "x\x00y", "../../etc/passwd", "PL id with spaces"],
    )
    @pytest.mark.parametrize("mode", [V, A, X])
    def test_a_hostile_playlist_id_never_becomes_a_path(
        self, mode: DownloadMode, hostile: str
    ) -> None:
        name = archive_file_name(mode, is_playlist=True, is_channel=False, key=hostile)

        assert "/" not in name and "\\" not in name and "\x00" not in name
        assert Path(name).name == name

    def test_two_different_ids_never_collide_after_sanitising(self) -> None:
        first = archive_file_name(V, is_playlist=True, is_channel=False, key="a/b")
        second = archive_file_name(V, is_playlist=True, is_channel=False, key="a_b")

        assert first != second


class TestEnsureWithin:
    def test_a_file_inside_the_root_is_returned(self, tmp_path: Path) -> None:
        inside = tmp_path / "archives" / "x.txt"

        assert ensure_within(tmp_path / "archives", inside) == inside

    @pytest.mark.parametrize("escape", ["../x.txt", "sub/../../x.txt", "/etc/x.txt"])
    def test_anything_that_normalises_outside_is_refused(self, tmp_path: Path, escape: str) -> None:
        root = tmp_path / "archives"
        root.mkdir()

        with pytest.raises(ValidationError):
            ensure_within(root, root / escape)

    def test_a_symlink_out_of_the_root_is_refused(self, tmp_path: Path) -> None:
        root = tmp_path / "archives"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        try:
            (root / "link").symlink_to(outside, target_is_directory=True)
        except OSError:
            pytest.skip("symlinks are not available here")

        with pytest.raises(ValidationError):
            ensure_within(root, root / "link" / "x.txt")

    def test_the_root_itself_is_not_a_valid_target(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            ensure_within(tmp_path, tmp_path)


class TestPlanTargets:
    def plan(self, config: UserConfig, tmp_path: Path, **kw):
        base: dict[str, Any] = {
            "mode": V,
            "is_playlist": False,
            "is_channel": False,
            "key": None,
            "config": config,
            "settings": AppSettings(),
            "archives_dir": tmp_path / "archives",
        }
        base.update(kw)
        return plan_targets(**base)

    def test_a_single_video(self, config: UserConfig, tmp_path: Path) -> None:
        t = self.plan(config, tmp_path)

        assert t.base_dir == config.videos_dir / "Downloaded Videos"
        assert t.output_template == str(t.base_dir / AppSettings().output.single_video_template)
        assert t.archive_path == tmp_path / "archives" / "single_videos_mp4.txt"

    def test_a_video_playlist(self, config: UserConfig, tmp_path: Path) -> None:
        t = self.plan(config, tmp_path, is_playlist=True, key="PLabc")

        assert t.base_dir == config.videos_dir / "yt-dlp"
        assert t.output_template == str(t.base_dir / AppSettings().output.playlist_video_template)
        assert t.archive_path == tmp_path / "archives" / "playlist_PLabc_mp4.txt"

    def test_audio_goes_to_the_music_folder(self, config: UserConfig, tmp_path: Path) -> None:
        single = self.plan(config, tmp_path, mode=A)
        playlist = self.plan(config, tmp_path, mode=A, is_playlist=True, key="PL1")

        assert single.base_dir == config.music_dir / "Downloaded Music"
        assert playlist.base_dir == config.music_dir / "yt-dlp"
        assert single.archive_path.name == "single_audios_mp3.txt"

    def test_archive_mode_uses_the_archive_template_under_the_videos_folder(
        self, config: UserConfig, tmp_path: Path
    ) -> None:
        t = self.plan(config, tmp_path, mode=X, is_playlist=True, is_channel=True, key=CHANNEL_ID)

        assert t.base_dir == config.videos_dir / "yt-dlp"
        assert t.output_template == str(t.base_dir / AppSettings().output.archive_template)
        assert t.archive_path.name == f"channel_{CHANNEL_ID}_archive.txt"

    def test_a_hostile_playlist_id_stays_inside_the_archives_folder(
        self, config: UserConfig, tmp_path: Path
    ) -> None:
        t = self.plan(config, tmp_path, is_playlist=True, key="/../../outside")

        assert t.archive_path.resolve().parent == (tmp_path / "archives").resolve()

    def test_a_name_that_would_escape_is_refused_not_used(
        self, config: UserConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(planning, "archive_file_name", lambda *_a, **_k: "../escape.txt")

        with pytest.raises(ValidationError):
            self.plan(config, tmp_path, is_playlist=True, key="PL1")

    def test_an_older_channel_archive_is_still_used_when_the_new_one_does_not_exist(
        self, config: UserConfig, tmp_path: Path
    ) -> None:
        """Before channels were keyed by id, MP4/MP3 kept "playlist_<handle>_mp4.txt"."""
        archives = tmp_path / "archives"
        archives.mkdir()
        legacy = archives / "playlist_ChannelHandle_mp4.txt"
        legacy.write_text("youtube abc\n", encoding="utf-8")

        t = self.plan(
            config,
            tmp_path,
            is_playlist=True,
            is_channel=True,
            key=CHANNEL_ID,
            legacy_key="ChannelHandle",
        )

        assert t.archive_path == legacy

    def test_the_new_archive_wins_once_it_exists(self, config: UserConfig, tmp_path: Path) -> None:
        archives = tmp_path / "archives"
        archives.mkdir()
        (archives / "playlist_ChannelHandle_mp4.txt").write_text("youtube abc\n")
        current = archives / f"channel_{CHANNEL_ID}_mp4.txt"
        current.write_text("youtube def\n")

        t = self.plan(
            config,
            tmp_path,
            is_playlist=True,
            is_channel=True,
            key=CHANNEL_ID,
            legacy_key="ChannelHandle",
        )

        assert t.archive_path == current
