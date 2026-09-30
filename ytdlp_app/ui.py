"""User interface components for ytdlp_app.

This module provides a protocol-based UI abstraction that allows
for different UI implementations (console, GUI, testing mocks).
"""

from __future__ import annotations

import re
import shutil
from typing import Protocol

from .i18n import t
from .logging_utils import Colors, colors_enabled, console_print, paint, strip_ansi

#: Matches ANSI SGR escape sequences, which occupy no columns on screen.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

#: One SGR sequence or one character; wrapping walks these.
_TOKEN_RE = re.compile(r"\x1b\[[0-9;]*m|.", re.DOTALL)

#: Width assumed when the output is not a terminal (and COLUMNS is unset).
_FALLBACK_COLUMNS = 100

#: Never squeeze a panel narrower than this, however small the terminal reports.
_MIN_COLUMNS = 20


def visible_len(text: str) -> int:
    """Return the on-screen width of a string, ignoring ANSI color codes."""
    return len(_ANSI_RE.sub("", text))


def terminal_columns() -> int:
    """The width of the terminal in columns."""
    return max(shutil.get_terminal_size(fallback=(_FALLBACK_COLUMNS, 24)).columns, _MIN_COLUMNS)


def _is_code(token: str) -> bool:
    return token.startswith("\x1b")


def _columns(tokens: list[str]) -> int:
    return sum(1 for token in tokens if not _is_code(token))


def wrap_ansi(text: str, width: int) -> list[str]:
    """Wrap one line of text to a width without counting or losing colour codes.

    Breaks between words, or in the middle of a word longer than the width. A colour
    that is active at a break is closed at the end of that line and reopened at the
    start of the next, so every line stands alone.

    Args:
        text: The text, possibly with ANSI colour codes.
        width: Maximum visible columns per line; 0 or less disables wrapping.
    """
    if width <= 0 or visible_len(text) <= width:
        return [text]

    words: list[list[str]] = [[]]
    for token in _TOKEN_RE.findall(text):
        if token == " ":
            words.append([])
        else:
            words[-1].append(token)

    rows: list[list[str]] = []
    row: list[str] = []
    for word in words:
        size = _columns(word)
        if not word:
            continue
        if size > width:
            if row:
                rows.append(row)
            chunk: list[str] = []
            used = 0
            for token in word:
                if not _is_code(token):
                    if used == width:
                        rows.append(chunk)
                        chunk, used = [], 0
                    used += 1
                chunk.append(token)
            row = chunk
        elif not row:
            row = list(word)
        elif _columns(row) + 1 + size <= width:
            row += [" ", *word]
        else:
            rows.append(row)
            row = list(word)
    if row or not rows:
        rows.append(row)

    lines: list[str] = []
    state = ""
    for tokens in rows:
        start = state
        for token in tokens:
            if _is_code(token):
                state = "" if token == Colors.RESET else state + token
        line = start + "".join(tokens)
        if (start or state) and not line.endswith(Colors.RESET):
            line += Colors.RESET
        lines.append(line)
    return lines


class UI(Protocol):
    """Protocol defining the user interface contract.

    This protocol allows for dependency injection of different UI
    implementations, making the application easier to test and
    potentially extend with GUI implementations.
    """

    def print(self, text: str = "") -> None:
        """Display text to the user.

        Args:
            text: The text to display. Defaults to empty string for blank line.
        """
        ...

    def pick(self, prompt: str, options: list[str]) -> int:
        """Present a list of options and get user's choice.

        Args:
            prompt: The question or instruction to display.
            options: List of options to choose from.

        Returns:
            The 1-based index of the selected option.
        """
        ...

    def ask_text(self, prompt: str) -> str:
        """Ask the user for text input.

        Args:
            prompt: The prompt to display before the input.

        Returns:
            The user's input, stripped of leading/trailing whitespace.
        """
        ...

    def prompt_exit_on_failure(self) -> bool:
        """Ask the user if they want to exit after an error.

        Returns:
            True if the user wants to exit, False to continue.
        """
        ...

    def print_panel(self, text: str, title: str | None = None, color: str = "") -> None:
        """Display text inside a stylized box.

        Args:
            text: The content to display.
            title: Optional title for the panel.
            color: Color code for the border.
        """
        ...


class ConsoleUI:
    """Console-based implementation of the UI protocol.

    Provides colorized terminal output and interactive prompts
    for command-line usage.
    """

    @staticmethod
    def _plain(prompt: str) -> str:
        """A prompt for input(), without colour codes when stdout is not a colour terminal."""
        return prompt if colors_enabled() else strip_ansi(prompt)

    def print(self, text: str = "") -> None:
        """Display text to the console.

        Args:
            text: The text to display.
        """
        console_print(text)

    def print_panel(self, text: str, title: str | None = None, color: str = Colors.CYAN) -> None:
        """Display text inside a stylized box.

        Args:
            text: The content to display.
            title: Optional title for the panel.
            color: Color code for the border.
        """
        # The box spends 4 columns on its borders and padding; the rest is text.
        limit = terminal_columns() - 4
        lines = [wrapped for line in text.split("\n") for wrapped in wrap_ansi(line, limit)]
        if title and visible_len(title) > limit - 4:
            title = strip_ansi(title)[: max(limit - 5, 1)] + "…"
        title_len = visible_len(title) if title else 0
        width = max((visible_len(line) for line in lines), default=0)
        width = max(width, title_len + 4 if title else 0)
        width += 2  # Padding

        # Box drawing characters
        tl, tr = "╭", "╮"
        bl, br = "╰", "╯"
        h, v = "─", "│"

        # Top border
        if title:
            title_text = f" {Colors.BOLD}{title}{Colors.RESET}{color} "
            left_len = (width - title_len - 2) // 2
            right_len = width - title_len - 2 - left_len
            self.print(f"{color}{tl}{h * left_len}{title_text}{h * right_len}{tr}{Colors.RESET}")
        else:
            self.print(f"{color}{tl}{h * width}{tr}{Colors.RESET}")

        # Content
        for line in lines:
            padding = max(width - visible_len(line) - 1, 0)
            self.print(f"{color}{v}{Colors.RESET} {line}{' ' * padding}{color}{v}{Colors.RESET}")

        # Bottom border
        self.print(f"{color}{bl}{h * width}{br}{Colors.RESET}")

    def pick(self, prompt: str, options: list[str]) -> int:
        """Present numbered options and get user's choice.

        Displays options with numbers and validates input until
        a valid selection is made.

        Args:
            prompt: The question to display.
            options: List of options to choose from.

        Returns:
            The 1-based index of the selected option.
        """
        if not options:
            raise ValueError("pick() requires at least one option")

        while True:
            # The box has one column of border on each side plus a space of padding.
            avail = terminal_columns() - 2
            option_lines = []
            for i, opt in enumerate(options, start=1):
                idx_str = f"{i}."
                room = max(avail - len(idx_str) - 3, 8)
                parts = wrap_ansi(opt, room)
                option_lines.append((idx_str, parts))

            prompt_parts = wrap_ansi(prompt, max(avail - 4, 8))
            content = max(
                [visible_len(part) + len(idx) + 2 for idx, parts in option_lines for part in parts]
                + [visible_len(part) + 3 for part in prompt_parts]
            )
            max_len = min(content + 4, avail)

            first = prompt_parts[0]
            self.print(
                f"\n{Colors.CYAN}┌─ {paint(first, Colors.BOLD)}{Colors.CYAN} "
                f"{'─' * max(max_len - visible_len(first) - 3, 0)}┐{Colors.RESET}"
            )
            for extra in prompt_parts[1:]:
                pad = " " * max(max_len - visible_len(extra) - 2, 0)
                edge = paint("│", Colors.CYAN)
                self.print(f"{edge} {paint(extra, Colors.BOLD)}{pad}{edge}")

            for idx_str, parts in option_lines:
                for n, part in enumerate(parts):
                    lead = idx_str if n == 0 else " " * len(idx_str)
                    padding = max(max_len - visible_len(part) - len(lead) - 2, 0)
                    self.print(
                        f"{paint('│', Colors.CYAN)} {paint(lead, Colors.YELLOW)} "
                        f"{paint(part, Colors.WHITE)}{' ' * padding}{paint('│', Colors.CYAN)}"
                    )

            self.print(f"{Colors.CYAN}└{'─' * max_len}┘{Colors.RESET}")

            ans = input(
                self._plain(f"{Colors.GREEN}{t('prompt_select', max=len(options))}{Colors.RESET}")
            ).strip()
            if ans.isdigit():
                n = int(ans)
                if 1 <= n <= len(options):
                    return n
            self.print(f"{Colors.RED}{t('error_invalid_choice', max=len(options))}{Colors.RESET}")

    def ask_text(self, prompt: str) -> str:
        """Ask the user for text input with colored prompt.

        Args:
            prompt: The prompt to display.

        Returns:
            The user's input, stripped of whitespace.
        """
        return input(self._plain(f"{Colors.CYAN}{prompt}{Colors.RESET}")).strip()

    def prompt_exit_on_failure(self) -> bool:
        """Ask if user wants to exit after an error.

        Returns:
            True if the user affirms, False otherwise.
        """
        ans = (
            input(self._plain(f"\n{Colors.RED}{Colors.BOLD}{t('prompt_exit_error')}{Colors.RESET}"))
            .strip()
            .lower()
        )
        # Accept the localized affirmative (Turkish uses "e") as well as the
        # English forms, which users type out of habit regardless of language.
        affirmative = {"y", "yes", t("yes").strip().lower()}
        return ans in affirmative
