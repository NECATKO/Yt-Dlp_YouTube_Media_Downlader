"""Checks that need no Windows: the PowerShell scripts are at least well formed, and the files
that must match each other do."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ytdlp_app.settings import AppSettings

ROOT = Path(__file__).resolve().parent.parent

BASH_SCRIPTS = ("run.sh", "install.sh")


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


@pytest.mark.parametrize("name", ["install.ps1"])
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


def test_settings_example_is_the_defaults_and_reads_without_a_complaint() -> None:
    example = json.loads((ROOT / "settings.example.json").read_text(encoding="utf-8"))
    issues: list = []

    settings = AppSettings.from_dict(example["settings"], issues)

    assert issues == []
    assert settings.to_dict() == AppSettings().to_dict()
    assert example["config_version"] == 2


def test_the_balance_check_really_catches_a_typo() -> None:
    """The checker itself: a dropped brace and a swapped bracket must both be seen."""
    good = "function A { if ($x) { return 1 } }"
    assert strip_powershell(good).count("{") == strip_powershell(good).count("}")
    assert strip_powershell(good + "}").count("}") != strip_powershell(good + "}").count("{")
    # Braces inside strings and comments are not structure.
    quoted = "Write-Host '{' # }\n$x = \"}\""
    assert "{" not in strip_powershell(quoted) and "}" not in strip_powershell(quoted)


@pytest.mark.parametrize("name", BASH_SCRIPTS)
def test_the_bash_scripts_have_lf_line_endings_in_the_working_tree(name: str) -> None:
    """A Windows checkout (core.autocrlf) once turned them into CRLF, which Linux bash
    rejects, and the portable ZIP is packed from such a checkout."""
    assert b"\r" not in (ROOT / name).read_bytes(), f"{name} has CR bytes"


@pytest.mark.skipif(
    not shutil.which("git") or not (ROOT / ".git").exists(), reason="needs a git checkout"
)
def test_git_keeps_the_bash_scripts_lf_and_the_batch_launcher_crlf() -> None:
    result = subprocess.run(
        ["git", "check-attr", "eol", "--", *BASH_SCRIPTS, "Run.bat"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    eol = dict(line.split(": eol: ") for line in result.stdout.splitlines())
    assert eol == {**dict.fromkeys(BASH_SCRIPTS, "lf"), "Run.bat": "crlf"}


# Git Bash on Windows accepts CRLF scripts, so only a POSIX bash proves anything.
@pytest.mark.skipif(os.name != "posix" or not shutil.which("bash"), reason="needs a POSIX bash")
@pytest.mark.parametrize("name", BASH_SCRIPTS)
def test_each_bash_script_parses(name: str) -> None:
    # One file per call: "bash -n a b" checks a only and passes b to it as an argument.
    result = subprocess.run(
        ["bash", "-n", str(ROOT / name)], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
