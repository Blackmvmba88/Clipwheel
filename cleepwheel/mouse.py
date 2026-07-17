from __future__ import annotations

from pathlib import Path

from .ui import open_window


def run_mouse_window(db_path: Path) -> int:
    return open_window(db_path)
