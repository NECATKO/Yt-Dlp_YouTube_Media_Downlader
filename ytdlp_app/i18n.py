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
    # Shipped inside the package, so it survives both wheel installs and the
    # portable ZIP (which copies the ytdlp_app directory wholesale).
    package_dir = Path(__file__).parent / "locales"
    if package_dir.exists():
        return package_dir

    # Fall back to the pre-0.4 repository layout (locales/ next to the package)
    repo_dir = Path(__file__).parent.parent / "locales"
    if repo_dir.exists():
        return repo_dir

    # Fall back to current working directory
    cwd_locales = Path.cwd() / "locales"
    if cwd_locales.exists():
        return cwd_locales

    return package_dir


def _read_locale_file(locales_dir: Path, language: str) -> dict[str, str]:
    """Read a single locale JSON file, returning {} if unreadable."""
    locale_file = locales_dir / f"{language}.json"
    if not locale_file.exists():
        return {}
    try:
        data = json.loads(locale_file.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=8)
def load_locale(language: str) -> dict[str, str]:
    """Load translations for a specific language.

    English is always loaded as the base layer and the requested language is
    overlaid on top, so a key that a translation has not caught up on yet
    renders as English rather than leaking the raw key to the user.

    Args:
        language: Language code (e.g., 'en', 'tr', 'de').

    Returns:
        Dictionary mapping translation keys to translated strings.
    """
    locales_dir = get_locales_dir()

    merged = _read_locale_file(locales_dir, "en")
    if language != "en":
        merged.update(_read_locale_file(locales_dir, language))

    return merged


def set_language(language: str) -> None:
    """Set the current language for translations.

    Args:
        language: Language code (e.g., 'en', 'tr', 'de').
    """
    # Process-wide state by design: t() is called from every module and taking a
    # catalogue argument at each of the ~80 call sites would serve nobody.
    global _current_language, _translations  # noqa: PLW0603

    _current_language = language
    # Copy: load_locale is lru_cached, so handing out the cached object itself
    # would let any mutation poison every later lookup.
    _translations = dict(load_locale(language))


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
    if not _translations:
        # Nothing loaded yet: fall back to the default catalogue rather than
        # echoing raw keys at the user. This covers UI shown before the
        # language is known, such as the language picker itself.
        set_language(_current_language)

    text = _translations.get(key, key)

    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            # A malformed placeholder in a translation must not crash the app.
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
