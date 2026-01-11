"""Internationalization (i18n) support for ytdlp_app.

This module provides translation support for the application,
allowing users to use the interface in their preferred language.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

# Default language
_current_language: str = "en"
_translations: dict[str, str] = {}


def get_locales_dir() -> Path:
    """Get the path to the locales directory.

    Returns:
        Path to the locales directory.
    """
    # Check for locales in package directory first
    package_dir = Path(__file__).parent.parent / "locales"
    if package_dir.exists():
        return package_dir

    # Fall back to current working directory
    cwd_locales = Path.cwd() / "locales"
    if cwd_locales.exists():
        return cwd_locales

    return package_dir


@lru_cache(maxsize=8)
def load_locale(language: str) -> dict[str, str]:
    """Load translations for a specific language.

    Args:
        language: Language code (e.g., 'en', 'tr', 'de').

    Returns:
        Dictionary mapping translation keys to translated strings.
        Falls back to English if the requested language is not found.
    """
    locales_dir = get_locales_dir()
    locale_file = locales_dir / f"{language}.json"

    # Try requested language
    if locale_file.exists():
        try:
            return json.loads(locale_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Fall back to English
    if language != "en":
        en_file = locales_dir / "en.json"
        if en_file.exists():
            try:
                return json.loads(en_file.read_text(encoding="utf-8"))
            except Exception:
                pass

    # Return empty dict if no locale found
    return {}


def set_language(language: str) -> None:
    """Set the current language for translations.

    Args:
        language: Language code (e.g., 'en', 'tr', 'de').
    """
    global _current_language, _translations
    _current_language = language
    _translations = load_locale(language)


def get_language() -> str:
    """Get the current language code.

    Returns:
        The current language code.
    """
    return _current_language


def t(key: str, **kwargs: Any) -> str:
    """Translate a key to the current language.

    If the key is not found, returns the key itself as a fallback.
    Supports format string placeholders using kwargs.

    Args:
        key: The translation key.
        **kwargs: Format string arguments.

    Returns:
        The translated string, or the key if not found.

    Example:
        >>> set_language("en")
        >>> t("greeting", name="World")
        "Hello, World!"
    """
    text = _translations.get(key, key)

    if kwargs:
        try:
            return text.format(**kwargs)
        except KeyError:
            return text

    return text


def get_available_languages() -> list[str]:
    """Get a list of available language codes.

    Returns:
        List of language codes for which translations exist.
    """
    locales_dir = get_locales_dir()

    if not locales_dir.exists():
        return ["en"]

    languages = []
    for file in locales_dir.glob("*.json"):
        languages.append(file.stem)

    return sorted(languages) if languages else ["en"]


# Language display names
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "tr": "Turkce",
    "de": "Deutsch",
    "es": "Espanol",
    "fr": "Francais",
    "it": "Italiano",
    "pt": "Portugues",
    "ru": "Russkiy",
    "zh": "Zhongwen",
    "ja": "Nihongo",
    "ko": "Hangugeo",
}


def get_language_name(code: str) -> str:
    """Get the display name for a language code.

    Args:
        code: Language code.

    Returns:
        Human-readable language name.
    """
    return LANGUAGE_NAMES.get(code, code.upper())
