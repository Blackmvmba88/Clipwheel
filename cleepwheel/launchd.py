from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path
from typing import Dict, Any

from .settings import Settings


def build_launchd_plist(
    settings: Settings, python_executable: str, project_root: Path
) -> Dict[str, Any]:
    return {
        "Label": settings.launchd_label,
        "ProgramArguments": [
            python_executable,
            "-m",
            "cleepwheel",
            "--db",
            str(settings.db_path),
            "watch",
            "--interval",
            str(settings.watch_interval),
        ],
        "RunAtLoad": True,
        "KeepAlive": True,
        "WorkingDirectory": str(project_root),
        "StandardOutPath": str(settings.db_path.parent / "cleepwheel-watch.log"),
        "StandardErrorPath": str(settings.db_path.parent / "cleepwheel-watch.err"),
    }


def build_mouse_launchd_plist(
    settings: Settings, python_executable: str, project_root: Path
) -> Dict[str, Any]:
    return {
        "Label": "com.blackmamba.cleepwheel.mouse",
        "ProgramArguments": [
            python_executable,
            "-m",
            "cleepwheel",
            "--db",
            str(settings.db_path),
            "mouse-listen",
        ],
        "RunAtLoad": True,
        "KeepAlive": True,
        "WorkingDirectory": str(project_root),
        "StandardOutPath": str(settings.db_path.parent / "cleepwheel-mouse.log"),
        "StandardErrorPath": str(settings.db_path.parent / "cleepwheel-mouse.err"),
    }


def write_launchd_plist(path: Path, plist: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        plistlib.dump(plist, handle)


def _uid() -> str:
    return subprocess.check_output(["id", "-u"], text=True).strip()


def load_agent(plist_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["launchctl", "bootstrap", f"gui/{_uid()}", str(plist_path)],
        check=False,
        capture_output=True,
        text=True,
    )


def unload_agent(plist_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["launchctl", "bootout", f"gui/{_uid()}", str(plist_path)],
        check=False,
        capture_output=True,
        text=True,
    )


def is_loaded(label: str) -> bool:
    result = subprocess.run(
        ["launchctl", "print", f"gui/{_uid()}/{label}"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0
