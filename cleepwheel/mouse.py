from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

from .ui import open_window


class MouseListenerError(RuntimeError):
    """Raised when macOS cannot create the global mouse event tap."""


def run_mouse_window(db_path: Path) -> int:
    return open_window(db_path)


def _load_quartz() -> Tuple[ctypes.CDLL, ctypes.CDLL]:
    try:
        core_graphics = ctypes.CDLL(
            "/System/Library/Frameworks/ApplicationServices.framework/"
            "Frameworks/CoreGraphics.framework/CoreGraphics"
        )
        core_foundation = ctypes.CDLL(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
        )
    except OSError as exc:
        raise MouseListenerError(f"failed to load macOS mouse frameworks: {exc}") from exc
    return core_graphics, core_foundation


def _spawn_window(db_path: Path) -> subprocess.Popen:
    def ignore_wake_signal_until_ready() -> None:
        signal.signal(signal.SIGUSR1, signal.SIG_IGN)

    return subprocess.Popen(
        [sys.executable, "-m", "cleepwheel", "--db", str(db_path), "warm-window"],
        cwd=str(Path(__file__).resolve().parent.parent),
        start_new_session=True,
        preexec_fn=ignore_wake_signal_until_ready,
    )


def _wake_window(window_process: subprocess.Popen) -> float:
    started = time.perf_counter()
    os.kill(window_process.pid, signal.SIGUSR1)
    return (time.perf_counter() - started) * 1000


def listen_for_middle_click(db_path: Path, debounce_seconds: float = 0.18) -> int:
    """Listen globally for the center button and open one CleepWheel window."""
    core_graphics, core_foundation = _load_quartz()

    # kCGMouseEventButtonNumber from CGEventTypes.h.
    event_field_button_number = 3
    mouse_button_center = 2
    mask_other_mouse_down = 1 << 25

    get_button = core_graphics.CGEventGetIntegerValueField
    get_button.restype = ctypes.c_longlong
    get_button.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

    create_tap = core_graphics.CGEventTapCreate
    create_tap.restype = ctypes.c_void_p
    create_tap.argtypes = [
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint64,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]

    create_source = core_foundation.CFMachPortCreateRunLoopSource
    create_source.restype = ctypes.c_void_p
    create_source.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]

    get_run_loop = core_foundation.CFRunLoopGetCurrent
    get_run_loop.restype = ctypes.c_void_p
    add_source = core_foundation.CFRunLoopAddSource
    add_source.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    run_loop = core_foundation.CFRunLoopRun
    common_modes = ctypes.c_void_p.in_dll(core_foundation, "kCFRunLoopCommonModes")

    last_click = 0.0
    window_process: Optional[subprocess.Popen] = _spawn_window(db_path)

    def callback(_proxy, _event_type, event, _refcon):
        nonlocal last_click, window_process
        if get_button(event, event_field_button_number) != mouse_button_center:
            return event
        now = time.monotonic()
        if now - last_click < debounce_seconds:
            return event
        last_click = now
        if window_process is None or window_process.poll() is not None:
            window_process = _spawn_window(db_path)
            print("middle click detected; warm window restarting", flush=True)
            return event
        elapsed_ms = _wake_window(window_process)
        print(f"middle click detected; signal_ms={elapsed_ms:.3f}", flush=True)
        return event

    callback_type = ctypes.CFUNCTYPE(
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_void_p,
    )
    tap_callback = callback_type(callback)
    tap = create_tap(1, 0, 1, mask_other_mouse_down, tap_callback, None)
    if not tap:
        raise MouseListenerError(
            "unable to listen for the wheel click; grant Accessibility and Input "
            "Monitoring permissions to Python or Terminal in System Settings"
        )

    source = create_source(None, tap, 0)
    if not source:
        raise MouseListenerError("unable to create the mouse listener run-loop source")
    current_loop = get_run_loop()
    add_source(current_loop, source, common_modes)
    run_loop()
    return 0
