"""User interface components for ytdlp_app.

This module provides a protocol-based UI abstraction that allows
for different UI implementations (console, GUI, testing mocks).
"""

from __future__ import annotations

import re
from typing import Protocol

from .i18n import t
from .logging_utils import Colors, paint

#: Matches ANSI SGR escape sequences, which occupy no columns on screen.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def visible_len(text: str) -> int:
    """Return the on-screen width of a string, ignoring ANSI color codes."""
    return len(_ANSI_RE.sub("", text))


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

    def print(self, text: str = "") -> None:
        """Display text to the console.

        Args:
            text: The text to display.
        """
        print(text)

    def print_panel(self, text: str, title: str | None = None, color: str = Colors.CYAN) -> None:
        """Display text inside a stylized box.

        Args:
            text: The content to display.
            title: Optional title for the panel.
            color: Color code for the border.
        """
        lines = text.split("\n")
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

        prompt_len = visible_len(prompt)

        while True:
            # Calculate width for the box
            max_len = max(visible_len(opt) for opt in options)
            max_len = max(max_len, prompt_len) + 6

            self.print(
                f"\n{Colors.CYAN}┌─ {paint(prompt, Colors.BOLD)}{Colors.CYAN} "
                f"{'─' * max(max_len - prompt_len - 3, 0)}┐{Colors.RESET}"
            )

            for i, opt in enumerate(options, start=1):
                idx_str = f"{i}."
                padding = max(max_len - visible_len(opt) - len(idx_str) - 2, 0)
                self.print(
                    f"{paint('│', Colors.CYAN)} {paint(idx_str, Colors.YELLOW)} "
                    f"{paint(opt, Colors.WHITE)}{' ' * padding}{paint('│', Colors.CYAN)}"
                )

            self.print(f"{Colors.CYAN}└{'─' * max_len}┘{Colors.RESET}")

            ans = input(
                f"{Colors.GREEN}{t('prompt_select', max=len(options))}{Colors.RESET}"
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
        return input(f"{Colors.CYAN}{prompt}{Colors.RESET}").strip()

    def prompt_exit_on_failure(self) -> bool:
        """Ask if user wants to exit after an error.

        Returns:
            True if the user affirms, False otherwise.
        """
        ans = (
            input(f"\n{Colors.RED}{Colors.BOLD}{t('prompt_exit_error')}{Colors.RESET}")
            .strip()
            .lower()
        )
        # Accept the localized affirmative (Turkish uses "e") as well as the
        # English forms, which users type out of habit regardless of language.
        affirmative = {"y", "yes", t("yes").strip().lower()}
        return ans in affirmative
