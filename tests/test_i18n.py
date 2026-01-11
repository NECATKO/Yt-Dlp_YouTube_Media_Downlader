"""Tests for ytdlp_app.i18n module."""

from pathlib import Path

import pytest

from ytdlp_app.i18n import (
    get_available_languages,
    get_language,
    get_language_name,
    load_locale,
    set_language,
    t,
)


class TestLoadLocale:
    """Tests for load_locale function."""

    def test_loads_english(self) -> None:
        """Test loading English locale."""
        locale = load_locale("en")
        assert "prompt_url" in locale
        assert "mode_video" in locale

    def test_loads_turkish(self) -> None:
        """Test loading Turkish locale."""
        locale = load_locale("tr")
        assert "prompt_url" in locale
        # Turkish has different text
        assert locale.get("mode_audio") == "Ses (MP3)"

    def test_fallback_to_english(self) -> None:
        """Test fallback to English for unknown language."""
        locale = load_locale("xyz_unknown")
        # Should return English or empty dict
        assert isinstance(locale, dict)


class TestSetAndGetLanguage:
    """Tests for set_language and get_language functions."""

    def test_set_and_get_language(self) -> None:
        """Test setting and getting language."""
        set_language("tr")
        assert get_language() == "tr"

        set_language("en")
        assert get_language() == "en"


class TestTranslation:
    """Tests for t (translate) function."""

    def test_translate_simple_key(self) -> None:
        """Test translating a simple key."""
        set_language("en")
        result = t("mode_video")
        assert result == "Video (MP4)"

    def test_translate_with_placeholder(self) -> None:
        """Test translating with format placeholders."""
        set_language("en")
        result = t("app_version", version="1.0.0")
        assert result == "Version 1.0.0"

    def test_missing_key_returns_key(self) -> None:
        """Test that missing keys return the key itself."""
        set_language("en")
        result = t("nonexistent_key_xyz")
        assert result == "nonexistent_key_xyz"

    def test_turkish_translation(self) -> None:
        """Test Turkish translations."""
        set_language("tr")
        result = t("mode_audio")
        assert result == "Ses (MP3)"


class TestAvailableLanguages:
    """Tests for get_available_languages function."""

    def test_returns_list(self) -> None:
        """Test that available languages returns a list."""
        languages = get_available_languages()
        assert isinstance(languages, list)
        assert len(languages) >= 1

    def test_includes_english(self) -> None:
        """Test that English is always available."""
        languages = get_available_languages()
        assert "en" in languages


class TestLanguageName:
    """Tests for get_language_name function."""

    def test_known_languages(self) -> None:
        """Test getting names for known languages."""
        assert get_language_name("en") == "English"
        assert get_language_name("tr") == "Turkce"

    def test_unknown_language(self) -> None:
        """Test getting name for unknown language."""
        result = get_language_name("xyz")
        assert result == "XYZ"  # Should uppercase the code
