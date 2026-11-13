"""The app's messages: one English catalogue, looked up by key.

Every user-facing string lives in ``locales/en.json`` rather than in the code, so the
wording can be reviewed and changed in one place.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

_CATALOGUE = Path(__file__).parent / "locales" / "en.json"


@cache
def _messages() -> dict[str, str]:
    """Read the catalogue once; an unreadable one leaves every key as its own text."""
    try:
        data = json.loads(_CATALOGUE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def t(key: str, **kwargs: Any) -> str:
    """Return the message for ``key``, with ``kwargs`` filled into its placeholders.

    An unknown key is returned as is, and a malformed placeholder leaves the message
    unformatted: neither may crash the app.
    """
    text = _messages().get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text
