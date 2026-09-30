"""Terminal behaviour: colour only on a real terminal, panels that fit the width."""

import io
import shutil

import pytest

from ytdlp_app import logging_utils
from ytdlp_app.logging_utils import Colors, colors_enabled, console_print, strip_ansi
from ytdlp_app.ui import ConsoleUI, visible_len, wrap_ansi

RED = Colors.RED
RESET = Colors.RESET


class FakeStream(io.StringIO):
    def __init__(self, tty: bool) -> None:
        super().__init__()
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch):
    for name in ("NO_COLOR", "FORCE_COLOR", "TERM"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


class TestColorPolicy:
    def test_a_terminal_gets_color(self, env) -> None:
        env.setenv("TERM", "xterm-256color")

        assert colors_enabled(FakeStream(tty=True))

    def test_redirected_output_gets_none(self, env) -> None:
        env.setenv("TERM", "xterm-256color")

        assert not colors_enabled(FakeStream(tty=False))

    def test_no_color_wins_over_a_terminal(self, env) -> None:
        env.setenv("NO_COLOR", "1")

        assert not colors_enabled(FakeStream(tty=True))

    def test_a_dumb_terminal_gets_none(self, env) -> None:
        env.setenv("TERM", "dumb")

        assert not colors_enabled(FakeStream(tty=True))

    def test_force_color_turns_it_on_when_redirected(self, env) -> None:
        env.setenv("FORCE_COLOR", "1")

        assert colors_enabled(FakeStream(tty=False))

    def test_no_color_still_wins_over_force_color(self, env) -> None:
        env.setenv("FORCE_COLOR", "1")
        env.setenv("NO_COLOR", "1")

        assert not colors_enabled(FakeStream(tty=True))


class TestOutput:
    def test_strip_ansi(self) -> None:
        assert strip_ansi(f"{RED}error{RESET} and {Colors.BOLD}bold{RESET}") == "error and bold"

    def test_redirected_output_carries_no_escape_codes(self, env) -> None:
        stream = FakeStream(tty=False)

        console_print(f"{RED}error{RESET}", file=stream)

        assert stream.getvalue() == "error\n"

    def test_a_terminal_keeps_them(self, env) -> None:
        env.setenv("TERM", "xterm")
        stream = FakeStream(tty=True)

        console_print(f"{RED}error{RESET}", file=stream)

        assert stream.getvalue() == f"{RED}error{RESET}\n"

    def test_console_ui_is_plain_when_captured(self, capsys, env) -> None:
        ConsoleUI().print_panel(f"{RED}hello{RESET}", title="T", color=Colors.CYAN)

        assert "\x1b" not in capsys.readouterr().out

    def test_prompts_are_plain_when_redirected(self, monkeypatch, env) -> None:
        shown: list[str] = []
        monkeypatch.setattr("builtins.input", lambda prompt="": shown.append(prompt) or "1")

        ConsoleUI().ask_text(f"{Colors.CYAN}URL: {RESET}")

        assert shown == ["URL: "]

    def test_log_functions_always_write_plain_text(self) -> None:
        assert hasattr(logging_utils, "strip_ansi")


class TestWrap:
    def test_short_lines_are_unchanged(self) -> None:
        assert wrap_ansi("short", 20) == ["short"]

    def test_long_lines_break_at_spaces_within_the_width(self) -> None:
        lines = wrap_ansi("alpha beta gamma delta epsilon", 12)

        assert all(visible_len(line) <= 12 for line in lines)
        assert " ".join(lines) == "alpha beta gamma delta epsilon"

    def test_a_word_longer_than_the_width_is_split(self) -> None:
        lines = wrap_ansi("x" * 25, 10)

        assert [visible_len(line) for line in lines] == [10, 10, 5]

    def test_color_continues_on_the_next_line_and_is_closed_on_each(self) -> None:
        lines = wrap_ansi(f"{RED}alpha beta gamma delta{RESET}", 11)

        assert len(lines) >= 2
        for line in lines:
            assert line.startswith(RED)
            assert line.endswith(RESET)
        assert " ".join(strip_ansi(line) for line in lines) == "alpha beta gamma delta"

    def test_turkish_letters_count_as_one_column_each(self) -> None:
        lines = wrap_ansi("çğıöşü çğıöşü", 6)

        assert lines == ["çğıöşü", "çğıöşü"]

    def test_no_width_means_no_wrap(self) -> None:
        assert wrap_ansi("a b c", 0) == ["a b c"]


class TestPanelsFitTheTerminal:
    def use_width(self, monkeypatch: pytest.MonkeyPatch, columns: int) -> None:
        monkeypatch.setattr(
            shutil, "get_terminal_size", lambda *_a, **_k: shutil.os.terminal_size((columns, 24))
        )

    def test_a_panel_never_exceeds_the_terminal(self, monkeypatch, capsys, env) -> None:
        self.use_width(monkeypatch, 40)
        text = "\n".join(["Output folder: /home/user/Videos/yt-dlp/a/very/long/path/name.mkv"] * 2)

        ConsoleUI().print_panel(text, title="Summary")

        lines = capsys.readouterr().out.splitlines()
        assert lines
        assert max(visible_len(line) for line in lines) <= 40

    def test_no_text_is_lost_when_a_panel_wraps(self, monkeypatch, capsys, env) -> None:
        self.use_width(monkeypatch, 30)

        ConsoleUI().print_panel("alpha beta gamma delta epsilon zeta eta theta", title="T")

        body = "".join(
            line.strip("│ ").rstrip() + " " for line in capsys.readouterr().out.splitlines()[1:-1]
        )
        for word in ("alpha", "epsilon", "theta"):
            assert word in body

    def test_a_wide_terminal_keeps_the_original_shape(self, monkeypatch, capsys, env) -> None:
        self.use_width(monkeypatch, 120)

        ConsoleUI().print_panel("short", title="T")

        out = capsys.readouterr().out.splitlines()
        assert len(out) == 3
        assert visible_len(out[0]) == visible_len(out[1]) == visible_len(out[2])

    def test_a_menu_fits_a_narrow_terminal(self, monkeypatch, capsys, env) -> None:
        self.use_width(monkeypatch, 36)
        monkeypatch.setattr("builtins.input", lambda _prompt="": "1")

        ConsoleUI().pick(
            "Which archive mode do you want to use for this whole channel?",
            ["Video + description + subtitles + metadata for a very long option", "Two"],
        )

        lines = capsys.readouterr().out.splitlines()
        assert max(visible_len(line) for line in lines) <= 36
        assert any("Two" in line for line in lines)
