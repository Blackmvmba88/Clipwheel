from __future__ import annotations

import subprocess


def read_clipboard_text() -> str:
    result = subprocess.run(["pbpaste"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "pbpaste failed")
    return result.stdout.rstrip("\n")


def write_clipboard_text(text: str) -> None:
    subprocess.run(["pbcopy"], input=text, text=True, check=True)
