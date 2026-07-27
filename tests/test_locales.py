"""Consistency checks across the shipped locale files.

These guard the failure mode that shipped in v0.3.0: the UI moved behind t()
while tr.json lagged 27 keys behind en.json, so Turkish users saw raw keys.
"""

import ast
import json
import string
from pathlib import Path

import pytest

from ytdlp_app.i18n import get_available_languages, get_locales_dir

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "ytdlp_app"


def _load(language: str) -> dict[str, str]:
    return json.loads((get_locales_dir() / f"{language}.json").read_text(encoding="utf-8"))


def _keys_used_in_source() -> set[str]:
    """Collect every literal key passed to t() across the package."""
    keys: set[str] = set()
    for path in PACKAGE_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "t"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                keys.add(node.args[0].value)
    return keys


def test_locales_ship_inside_the_package() -> None:
    """The wheel and the portable ZIP both only carry ytdlp_app/."""
    assert get_locales_dir() == PACKAGE_DIR / "locales"


@pytest.mark.parametrize("language", get_available_languages())
def test_locale_has_every_key_english_has(language: str) -> None:
    """No locale may lag behind English."""
    missing = sorted(set(_load("en")) - set(_load(language)))
    assert not missing, f"{language}.json is missing: {missing}"


@pytest.mark.parametrize("language", get_available_languages())
def test_every_key_used_in_code_is_translated(language: str) -> None:
    """A t() call with no matching key would print the raw key to the user."""
    missing = sorted(_keys_used_in_source() - set(_load(language)))
    assert not missing, f"{language}.json has no entry for: {missing}"


@pytest.mark.parametrize("language", get_available_languages())
def test_placeholders_match_english(language: str) -> None:
    """A translation dropping a {placeholder} would silently lose information."""

    def fields(text: str) -> set[str]:
        return {f for _, f, _, _ in string.Formatter().parse(text) if f}

    en = _load("en")
    other = _load(language)
    for key, en_text in en.items():
        assert fields(other[key]) == fields(en_text), f"{language}.json[{key}] placeholder mismatch"
