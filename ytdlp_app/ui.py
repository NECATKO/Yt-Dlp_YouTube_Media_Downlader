from __future__ import annotations

from typing import Protocol

from .logging_utils import Colors


class UI(Protocol):
    def print(self, text: str = "") -> None: ...

    def pick(self, prompt: str, options: list[str]) -> int: ...

    def ask_text(self, prompt: str) -> str: ...

    def prompt_exit_on_failure(self) -> bool: ...


class ConsoleUI:
    def print(self, text: str = "") -> None:
        print(text)

    def pick(self, prompt: str, options: list[str]) -> int:
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
        return input(f"{Colors.CYAN}{prompt}{Colors.RESET}").strip()

    def prompt_exit_on_failure(self) -> bool:
        ans = input(f"\n{Colors.RED}{Colors.BOLD}An error occurred. Do you want to exit? (Y/N): {Colors.RESET}").strip().lower()
        return ans in ("y", "yes")
