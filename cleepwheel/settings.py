from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Settings:
    db_path: Path
    watch_interval: float
    snippet_width: int
    max_content_chars: int
    history_view_limit: int
    launchd_label: str
    launchd_plist_path: Path


def default_db_path() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "cleepwheel" / "clipboard.sqlite3"


def _read_float(name: str, default: str, minimum: Optional[float] = None) -> float:
    raw = os.environ.get(name, default)
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _read_int(name: str, default: str, minimum: Optional[int] = None) -> int:
    raw = os.environ.get(name, default)
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def load_settings(db_path: Optional[Path] = None) -> Settings:
    snippet_width = _read_int("CLEEPWHEEL_SNIPPET_WIDTH", "120", minimum=20)
    max_content_chars = _read_int("CLEEPWHEEL_MAX_CONTENT_CHARS", "50000", minimum=1)
    history_view_limit = _read_int(
        "CLEEPWHEEL_HISTORY_LIMIT", "10000", minimum=500
    )
    launchd_label = os.environ.get(
        "CLEEPWHEEL_LAUNCHD_LABEL", "com.blackmamba.cleepwheel.watch"
    )
    return Settings(
        db_path=db_path or default_db_path(),
        watch_interval=_read_float("CLEEPWHEEL_WATCH_INTERVAL", "1.0", minimum=0.1),
        snippet_width=snippet_width,
        max_content_chars=max_content_chars,
        history_view_limit=history_view_limit,
        launchd_label=launchd_label,
        launchd_plist_path=(
            Path.home() / "Library/LaunchAgents" / f"{launchd_label}.plist"
        ),
    )
