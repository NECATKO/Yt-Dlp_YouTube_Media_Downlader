from __future__ import annotations

from typing import Protocol


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
            self.print("\n" + prompt)
            for i, opt in enumerate(options, start=1):
                self.print(f"  {i}) {opt}")
            ans = input("Select (numbers only): ").strip()
            if ans.isdigit():
                n = int(ans)
                if 1 <= n <= len(options):
                    return n
            self.print("Invalid choice. Please enter one of the listed numbers.")

    def ask_text(self, prompt: str) -> str:
        return input(prompt).strip()

    def prompt_exit_on_failure(self) -> bool:
        ans = input("\nAn error occurred. Do you want to exit? (Y/N): ").strip().lower()
        return ans in ("y", "yes")
