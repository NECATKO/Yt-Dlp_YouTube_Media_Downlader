"""User interface components for ytdlp_app.

This module provides a protocol-based UI abstraction that allows
for different UI implementations (console, GUI, testing mocks).
"""

from __future__ import annotations

import re
from typing import Protocol

from .logging_utils import Colors


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
        width = max(
            (len(line.replace(Colors.RESET, "").replace(Colors.BOLD, "")) for line in lines),
            default=0,
        )
        width = max(width, len(title) + 4 if title else 0)
        width += 2  # Padding

        # Box drawing characters
        tl, tr = "╭", "╮"
        bl, br = "╰", "╯"
        h, v = "─", "│"

        # Top border
        if title:
            title_text = f" {Colors.BOLD}{title}{Colors.RESET}{color} "
            left_len = (width - len(title) - 2) // 2
            right_len = width - len(title) - 2 - left_len
            print(f"{color}{tl}{h * left_len}{title_text}{h * right_len}{tr}{Colors.RESET}")
        else:
            print(f"{color}{tl}{h * width}{tr}{Colors.RESET}")

        # Content
        for line in lines:
            # Simple padding calculation (ignoring color codes for length)
            # This is a basic approximation; strictly accurate ANSI length is harder
            visible_len = len(re.sub(r"\x1b\[[0-9;]*m", "", line))
            padding = width - visible_len
            print(f"{color}{v}{Colors.RESET} {line}{' ' * (padding - 1)}{color}{v}{Colors.RESET}")

        # Bottom border
        print(f"{color}{bl}{h * width}{br}{Colors.RESET}")

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
        while True:
            # Calculate width for the box
            max_len = max(len(opt) for opt in options)
            max_len = max(max_len, len(prompt)) + 6

            print(
                f"\n{Colors.CYAN}┌─ {Colors.BOLD}{prompt}{Colors.RESET}{Colors.CYAN} {'─' * (max_len - len(prompt) - 3)}┐{Colors.RESET}"
            )

            for i, opt in enumerate(options, start=1):
                idx_str = f"{i}."
                padding = max_len - len(opt) - len(idx_str) - 2
                print(
                    f"{Colors.CYAN}│{Colors.RESET} {Colors.YELLOW}{idx_str}{Colors.RESET} {Colors.WHITE}{opt}{Colors.RESET}{' ' * padding}{Colors.CYAN}│{Colors.RESET}"
                )

            print(f"{Colors.CYAN}└{'─' * max_len}┘{Colors.RESET}")

            ans = input(f"{Colors.GREEN}Select (1-{len(options)}): {Colors.RESET}").strip()
            if ans.isdigit():
                n = int(ans)
                if 1 <= n <= len(options):
                    return n
            print(f"{Colors.RED}Invalid choice. Please enter 1-{len(options)}.{Colors.RESET}")

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
            True if user enters 'y' or 'yes', False otherwise.
        """
        ans = (
            input(
                f"\n{Colors.RED}{Colors.BOLD}An error occurred. Do you want to exit? (Y/N): {Colors.RESET}"
            )
            .strip()
            .lower()
        )
        return ans in ("y", "yes")
