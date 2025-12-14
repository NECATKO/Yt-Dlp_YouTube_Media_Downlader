from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from .logging_utils import append_log, log_error


def run_capture(cmd: list[str]) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, shell=False, capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr
    except KeyboardInterrupt:
        return 130, "", "Interrupted by user"
    except Exception as ex:
        # Keep behavior predictable for callers; provide something useful in stderr.
        return 1, "", f"{type(ex).__name__}: {ex}"


def run_cmd_tee(cmd: list[str], log_path: Path) -> int:
    print("\n=== €ALIžTIRILIYOR ===")
    print(" ".join(cmd))
    print("======================\n")

    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with log_path.open("a", encoding="utf-8", errors="ignore") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write(
                f"[{datetime.now().isoformat(timespec='seconds')}] CMD: {' '.join(cmd)}\n"
            )
            f.write("=" * 80 + "\n")

            p = subprocess.Popen(
                cmd,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            assert p.stdout is not None
            for line in p.stdout:
                print(line, end="")
                f.write(line)

            rc = p.wait()
            print(f"\n>>> Komut bitti. returncode = {rc}\n")
            f.write(f"\n>>> returncode = {rc}\n")
            return rc

    except KeyboardInterrupt:
        print("\n>>> ˜Ÿlem kullanc tarafndan durduruldu (Ctrl+C).")
        append_log(
            log_path,
            f"\n[INFO {datetime.now().isoformat(timespec='seconds')}] Interrupted by user (Ctrl+C)\n",
        )
        return 130
    except Exception as ex:
        log_error(log_path, "Komut ‡alŸtrma srasnda beklenmeyen hata", ex)
        return 1
