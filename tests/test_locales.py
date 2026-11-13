"""Consistency checks on the message catalogue (ytdlp_app/locales/en.json)."""

import ast
import json
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "ytdlp_app"
CATALOGUE = PACKAGE_DIR / "locales" / "en.json"


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


def test_every_key_used_in_code_has_a_message() -> None:
    """A t() call with no matching key would print the raw key to the user."""
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    missing = sorted(_keys_used_in_source() - set(catalogue))
    assert not missing, f"en.json has no entry for: {missing}"
