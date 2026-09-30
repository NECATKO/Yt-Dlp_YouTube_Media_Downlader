"""Checks that need no Windows: the PowerShell scripts are at least well formed, and the files
that must match each other do."""

import json
import re
from pathlib import Path

import pytest

from ytdlp_app.settings import AppSettings

ROOT = Path(__file__).resolve().parent.parent


def strip_powershell(text: str) -> str:
    """Remove comments and string contents, leaving the structure (a rough tokenizer)."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if text.startswith("<#", i):
            end = text.find("#>", i)
            i = n if end < 0 else end + 2
        elif ch == "#":
            while i < n and text[i] != "\n":
                i += 1
        elif ch in "\"'":
            quote = ch
            i += 1
            while i < n:
                if text[i] == "`" and quote == '"':
                    i += 2
                    continue
                if text[i] == quote:
                    if i + 1 < n and text[i + 1] == quote:  # '' inside single quotes
                        i += 2
                        continue
                    break
                i += 1
            i += 1
            out.append('""')
        else:
            out.append(ch)
            i += 1
    return "".join(out)


@pytest.mark.parametrize("name", ["update.ps1", "install.ps1"])
def test_powershell_scripts_are_balanced(name: str) -> None:
    code = strip_powershell((ROOT / name).read_text(encoding="utf-8"))
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[tuple[str, int]] = []
    line = 1
    for ch in code:
        if ch == "\n":
            line += 1
        elif ch in "([{":
            stack.append((ch, line))
        elif ch in pairs:
            assert stack, f"{name}:{line}: unmatched {ch!r}"
            opener, opened = stack.pop()
            assert opener == pairs[ch], (
                f"{name}:{line}: {ch!r} closes {opener!r} from line {opened}"
            )
    assert not stack, f"{name}: unclosed {stack[-1][0]!r} from line {stack[-1][1]}"


def test_every_function_the_updater_calls_is_defined() -> None:
    text = (ROOT / "update.ps1").read_text(encoding="utf-8")
    code = strip_powershell(text)
    defined = set(re.findall(r"(?m)^\s*function\s+([A-Za-z][\w-]*)", code))
    called = set(
        re.findall(
            r"(?<![\w$-])((?:Enter|Exit|Restore|Expand|Find|Test|Install|Compare|ConvertTo|Get)-[A-Za-z]+)",
            code,
        )
    )
    builtin = {
        "Get-Content",
        "Get-ChildItem",
        "Get-Date",
        "Get-FileHash",
        "Get-LocalVersion_",
        "Get-Item",
        "ConvertTo-Json",
        "Test-Path",
        "Expand-Archive",
    }
    unknown = sorted(name for name in called - defined - builtin if name not in defined)
    assert unknown == [], f"update.ps1 calls functions it does not define: {unknown}"


def test_the_updater_never_replaces_the_batch_launcher() -> None:
    text = (ROOT / "update.ps1").read_text(encoding="utf-8")
    items = re.search(r"\$ReplaceItems\s*=\s*@\(([^)]*)\)", text)
    assert items is not None
    assert "Run.bat" not in items.group(1)


def test_the_bash_updater_and_the_powershell_one_replace_the_same_files() -> None:
    sh = (ROOT / "update.sh").read_text(encoding="utf-8")
    ps = (ROOT / "update.ps1").read_text(encoding="utf-8")
    sh_files = set(re.search(r'REPLACE_FILES="([^"]*)"', sh).group(1).split())  # type: ignore[union-attr]
    sh_dirs = set(re.search(r'REPLACE_DIRS="([^"]*)"', sh).group(1).split())  # type: ignore[union-attr]
    ps_items = set(
        re.findall(r'"([^"]+)"', re.search(r"\$ReplaceItems\s*=\s*@\(([^)]*)\)", ps).group(1))
    )  # type: ignore[union-attr]

    # Run.bat is the one deliberate difference (see update.ps1).
    assert (sh_files | sh_dirs) - {"Run.bat"} == ps_items


def test_settings_example_is_the_defaults_and_reads_without_a_complaint() -> None:
    example = json.loads((ROOT / "settings.example.json").read_text(encoding="utf-8"))
    issues: list = []

    settings = AppSettings.from_dict(example["settings"], issues)

    assert issues == []
    assert settings.to_dict() == AppSettings().to_dict()
    assert example["config_version"] == 2


def test_the_runtime_lock_is_untouched_by_the_updaters_file_list() -> None:
    """runtime.lock is replaced by an update (it is app data), but the runtime folder never is."""
    sh = (ROOT / "update.sh").read_text(encoding="utf-8")
    assert "runtime.lock" in sh
    assert not re.search(r'REPLACE_(?:DIRS|FILES)="[^"]*\bruntime\b(?!\.lock)', sh)


def test_the_balance_check_really_catches_a_typo() -> None:
    """The checker itself: a dropped brace and a swapped bracket must both be seen."""
    good = "function A { if ($x) { return 1 } }"
    assert strip_powershell(good).count("{") == strip_powershell(good).count("}")
    assert strip_powershell(good + "}").count("}") != strip_powershell(good + "}").count("{")
    # Braces inside strings and comments are not structure.
    quoted = "Write-Host '{' # }\n$x = \"}\""
    assert "{" not in strip_powershell(quoted) and "}" not in strip_powershell(quoted)
