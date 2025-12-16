"""
Tests for localization (i18n) module.
"""

import pytest

from ytdlp_app.locales import (
    DEFAULT_LANGUAGE,
    MESSAGES,
    Translator,
    get_language,
    set_language,
    t,
)


class TestTranslator:
    """Tests for Translator class."""

    def test_default_language_is_english(self):
        translator = Translator()
        assert translator.language == "en"

    def test_set_language_turkish(self):
        translator = Translator()
        translator.language = "tr"
        assert translator.language == "tr"

    def test_invalid_language_falls_back_to_default(self):
        translator = Translator()
        translator.language = "invalid"
        assert translator.language == DEFAULT_LANGUAGE

    def test_get_english_message(self):
        translator = Translator("en")
        msg = translator.get("exit")
        assert msg == "Exiting."

    def test_get_turkish_message(self):
        translator = Translator("tr")
        msg = translator.get("exit")
        assert msg == "Çıkılıyor."

    def test_get_nonexistent_key_returns_key(self):
        translator = Translator("en")
        msg = translator.get("nonexistent_key")
        assert msg == "nonexistent_key"

    def test_format_placeholders(self):
        translator = Translator("en")
        msg = translator.get("config_using_folders", v_dir="/videos", m_dir="/music")
        assert "/videos" in msg
        assert "/music" in msg

    def test_callable_shorthand(self):
        translator = Translator("en")
        assert translator("exit") == translator.get("exit")


class TestGlobalFunctions:
    """Tests for global translation functions."""

    def test_set_and_get_language(self):
        original = get_language()
        try:
            set_language("tr")
            assert get_language() == "tr"
            set_language("en")
            assert get_language() == "en"
        finally:
            set_language(original)

    def test_t_function_english(self):
        original = get_language()
        try:
            set_language("en")
            assert t("exit") == "Exiting."
        finally:
            set_language(original)

    def test_t_function_turkish(self):
        original = get_language()
        try:
            set_language("tr")
            assert t("exit") == "Çıkılıyor."
        finally:
            set_language(original)


class TestMessagesCompleteness:
    """Tests to ensure all messages have both translations."""

    def test_all_messages_have_english(self):
        for key, translations in MESSAGES.items():
            assert "en" in translations, f"Missing English translation for: {key}"

    def test_all_messages_have_turkish(self):
        for key, translations in MESSAGES.items():
            assert "tr" in translations, f"Missing Turkish translation for: {key}"
