"""config.json and the runtime state survive interruptions, bad edits and old versions."""

import json
import os
from pathlib import Path
from typing import Any

import pytest

import ytdlp_app.config as config_module
from ytdlp_app.atomic import atomic_write_text
from ytdlp_app.config import (
    CONFIG_VERSION,
    load_config,
    load_settings,
    migrate_config,
    save_config,
    save_settings,
)
from ytdlp_app.i18n import set_language
from ytdlp_app.settings import LEGACY_TEMPLATES, AppSettings, OutputSettings


@pytest.fixture(autouse=True)
def _english():
    set_language("en")
    yield
    set_language("en")


def leftovers(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.iterdir() if p.name != "config.json")


class TestAtomicWrite:
    def test_the_new_content_replaces_the_old(self, tmp_path: Path) -> None:
        target = tmp_path / "config.json"
        target.write_text("old", encoding="utf-8")

        atomic_write_text(target, "new")

        assert target.read_text(encoding="utf-8") == "new"
        assert leftovers(tmp_path) == []

    def test_a_failed_replace_leaves_the_old_file_intact_and_no_litter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "config.json"
        target.write_text("old", encoding="utf-8")

        def broken(*_a: Any, **_k: Any) -> None:
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(os, "replace", broken)

        with pytest.raises(OSError, match="No space"):
            atomic_write_text(target, "new")

        monkeypatch.undo()
        assert target.read_text(encoding="utf-8") == "old"
        assert leftovers(tmp_path) == []

    def test_a_failure_while_writing_the_temp_file_leaves_the_old_file_intact(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "config.json"
        target.write_text("old", encoding="utf-8")

        def broken(_fd: int) -> None:
            raise OSError(5, "I/O error")

        monkeypatch.setattr(os, "fsync", broken)

        with pytest.raises(OSError, match="I/O"):
            atomic_write_text(target, "new")

        monkeypatch.undo()
        assert target.read_text(encoding="utf-8") == "old"
        assert leftovers(tmp_path) == []

    def test_a_missing_folder_is_created(self, tmp_path: Path) -> None:
        target = tmp_path / "deep" / "er" / "state.json"

        atomic_write_text(target, "{}")

        assert target.read_text(encoding="utf-8") == "{}"

    def test_unicode_survives(self, tmp_path: Path) -> None:
        target = tmp_path / "c.json"

        atomic_write_text(target, "İndirilenler çğışöü")

        assert target.read_text(encoding="utf-8") == "İndirilenler çğışöü"


class TestSaveFailuresKeepMemoryAndDiskTogether:
    def test_a_failed_save_does_not_touch_the_valid_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "config.json"
        save_config(path, {"language": "tr"})
        before = path.read_text(encoding="utf-8")
        monkeypatch.setattr(os, "replace", lambda *_a, **_k: (_ for _ in ()).throw(OSError("full")))

        with pytest.raises(OSError, match="full"):
            save_config(path, {"language": "en"})

        monkeypatch.undo()
        assert path.read_text(encoding="utf-8") == before
        assert load_config(path) == {"language": "tr"}

    def test_save_settings_leaves_the_callers_dict_alone_when_it_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "config.json"
        cfg: dict[str, Any] = {"language": "tr", "settings": {"marker": 1}}
        settings = AppSettings()
        settings.download.proxy = "http://p:1"
        monkeypatch.setattr(os, "replace", lambda *_a, **_k: (_ for _ in ()).throw(OSError("full")))

        with pytest.raises(OSError, match="full"):
            save_settings(path, cfg, settings)

        assert cfg == {"language": "tr", "settings": {"marker": 1}}

    def test_a_successful_save_updates_the_dict_and_the_file_together(self, tmp_path: Path) -> None:
        path = tmp_path / "config.json"
        cfg: dict[str, Any] = {"language": "tr"}
        settings = AppSettings()
        settings.download.proxy = "http://p:1"

        save_settings(path, cfg, settings)

        on_disk = json.loads(path.read_text(encoding="utf-8"))
        assert on_disk == cfg
        assert cfg["settings"]["download"]["proxy"] == "http://p:1"
        assert cfg["config_version"] == CONFIG_VERSION


class TestCorruptConfig:
    def test_an_unreadable_file_is_kept_aside_before_it_can_be_overwritten(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = tmp_path / "config.json"
        path.write_text('{"language": "tr", "videos_dir": ', encoding="utf-8")

        assert load_config(path) == {}

        kept = list(tmp_path.glob("config.json.corrupt*"))
        assert len(kept) == 1
        assert kept[0].read_text(encoding="utf-8").startswith('{"language"')
        assert kept[0].name in capsys.readouterr().out

    def test_a_valid_file_leaves_no_copy(self, tmp_path: Path) -> None:
        path = tmp_path / "config.json"
        path.write_text('{"language": "tr"}', encoding="utf-8")

        load_config(path)

        assert not list(tmp_path.glob("config.json.corrupt*"))

    def test_a_list_at_the_top_level_is_kept_aside_too(self, tmp_path: Path) -> None:
        path = tmp_path / "config.json"
        path.write_text("[1, 2]", encoding="utf-8")

        assert load_config(path) == {}
        assert len(list(tmp_path.glob("config.json.corrupt*"))) == 1


class TestSchemaMigration:
    def old_config(self, **output: str) -> dict[str, Any]:
        settings = AppSettings().to_dict()
        settings["output"] = {**LEGACY_TEMPLATES, "archive_template": "%(id)s/%(id)s.%(ext)s"}
        settings["output"].update(output)
        return {"language": "tr", "settings": settings}

    def test_a_config_without_a_version_is_version_1(self) -> None:
        cfg = self.old_config()

        migrate_config(cfg)

        assert cfg["config_version"] == CONFIG_VERSION

    def test_saved_default_templates_move_to_the_id_based_ones(self) -> None:
        cfg = self.old_config()

        notes = migrate_config(cfg)

        defaults = OutputSettings()
        out = cfg["settings"]["output"]
        assert out["single_video_template"] == defaults.single_video_template
        assert out["single_audio_template"] == defaults.single_audio_template
        assert out["playlist_video_template"] == defaults.playlist_video_template
        assert out["playlist_audio_template"] == defaults.playlist_audio_template
        assert notes

    def test_a_template_the_user_wrote_is_left_exactly_as_it_is(self) -> None:
        mine = "Music/%(uploader)s - %(title)s.%(ext)s"
        cfg = self.old_config(single_audio_template=mine)

        migrate_config(cfg)

        assert cfg["settings"]["output"]["single_audio_template"] == mine
        # The other, untouched defaults still migrate.
        assert "%(id)s" in cfg["settings"]["output"]["single_video_template"]

    def test_the_archive_template_is_never_touched(self) -> None:
        cfg = self.old_config()

        migrate_config(cfg)

        assert cfg["settings"]["output"]["archive_template"] == "%(id)s/%(id)s.%(ext)s"

    def test_migration_is_idempotent(self) -> None:
        cfg = self.old_config()
        migrate_config(cfg)
        once = json.dumps(cfg, sort_keys=True)

        notes = migrate_config(cfg)

        assert json.dumps(cfg, sort_keys=True) == once
        assert notes == []

    def test_a_config_from_a_newer_version_is_not_downgraded(self) -> None:
        cfg = {"config_version": CONFIG_VERSION + 5, "settings": {"output": dict(LEGACY_TEMPLATES)}}

        migrate_config(cfg)

        assert cfg["config_version"] == CONFIG_VERSION + 5
        assert cfg["settings"]["output"] == dict(LEGACY_TEMPLATES)

    @pytest.mark.parametrize("bad", ["2", None, 1.5, True, [], -3])
    def test_a_junk_version_is_treated_as_the_first(self, bad: Any) -> None:
        cfg = {"config_version": bad}

        migrate_config(cfg)

        assert cfg["config_version"] == CONFIG_VERSION

    @pytest.mark.parametrize("settings", [None, [], "x", 3])
    def test_unusable_settings_do_not_break_migration(self, settings: Any) -> None:
        cfg = {"settings": settings}

        migrate_config(cfg)

        assert cfg["config_version"] == CONFIG_VERSION

    def test_the_old_file_is_backed_up_when_the_migrated_one_is_first_saved(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "config.json"
        old = self.old_config()
        path.write_text(json.dumps(old), encoding="utf-8")
        cfg = load_config(path)
        migrate_config(cfg)

        save_settings(path, cfg, load_settings(cfg))

        backup = tmp_path / "config.json.v1.bak"
        assert json.loads(backup.read_text(encoding="utf-8")) == old
        assert json.loads(path.read_text(encoding="utf-8"))["config_version"] == CONFIG_VERSION

    def test_the_backup_is_not_overwritten_by_later_saves(self, tmp_path: Path) -> None:
        path = tmp_path / "config.json"
        path.write_text(json.dumps(self.old_config()), encoding="utf-8")
        cfg = load_config(path)
        migrate_config(cfg)
        save_settings(path, cfg, load_settings(cfg))
        first = (tmp_path / "config.json.v1.bak").read_text(encoding="utf-8")

        save_settings(path, cfg, load_settings(cfg))

        assert (tmp_path / "config.json.v1.bak").read_text(encoding="utf-8") == first


class TestLoadSettingsReportsProblems:
    def test_issues_are_collected_by_field_name(self) -> None:
        issues: list[Any] = []

        settings = load_settings({"settings": {"audio": None, "download": {"retries": -4}}}, issues)

        assert settings.audio.audio_format == "mp3"
        assert {i.field for i in issues} == {"audio", "download.retries"}

    def test_a_settings_value_that_is_not_an_object_is_reported_too(self) -> None:
        issues: list[Any] = []

        load_settings({"settings": [1]}, issues)

        assert [i.field for i in issues] == ["settings"]

    def test_the_old_call_shape_still_works(self) -> None:
        assert load_settings({}).audio.audio_format == "mp3"


def test_the_config_module_exposes_one_save_path() -> None:
    """save_settings goes through save_config, so patching or hardening it covers both."""
    assert config_module.save_config is save_config
