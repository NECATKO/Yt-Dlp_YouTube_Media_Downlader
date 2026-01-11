"""User interface components for ytdlp_app.

This module provides a protocol-based UI abstraction that allows
for different UI implementations (console, GUI, testing mocks).
"""

from __future__ import annotations

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
            self.print(f"\n{Colors.CYAN}{Colors.BOLD}{prompt}{Colors.RESET}")
            for i, opt in enumerate(options, start=1):
                self.print(f"  {Colors.YELLOW}{i}{Colors.RESET}) {Colors.WHITE}{opt}{Colors.RESET}")
            ans = input(f"{Colors.GREEN}Select (numbers only): {Colors.RESET}").strip()
            if ans.isdigit():
                n = int(ans)
                if 1 <= n <= len(options):
                    return n
            self.print("Invalid choice. Please enter one of the listed numbers.")

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
