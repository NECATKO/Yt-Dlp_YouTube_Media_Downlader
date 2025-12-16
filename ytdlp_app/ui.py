from __future__ import annotations

from typing import Protocol

from .locales import get_language, t


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
            ans = input(t("prompt_select")).strip()
            if ans.isdigit():
                n = int(ans)
                if 1 <= n <= len(options):
                    return n
            self.print(t("error_invalid_choice"))

    def ask_text(self, prompt: str) -> str:
        return input(prompt).strip()

    def prompt_exit_on_failure(self) -> bool:
        ans = input("\n" + t("prompt_exit_on_failure")).strip().lower()
        lang = get_language()
        if lang == "tr":
            return ans in ("e", "evet")
        return ans in ("y", "yes")
