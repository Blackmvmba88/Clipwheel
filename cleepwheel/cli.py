from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from .launchd import (
    build_launchd_plist,
    build_mouse_launchd_plist,
    is_loaded,
    load_agent,
    unload_agent,
    write_launchd_plist,
)
from .mouse import MouseListenerError, listen_for_middle_click, run_mouse_window
from .ui import open_warm_window
from .settings import load_settings
from .storage import ClipboardStore
from .webui import serve_webui
from .tui import run_quick_view, run_tui
from .watcher import ClipboardWatcher


SETTINGS = load_settings()
MOUSE_LAUNCHD_LABEL = "com.blackmamba.cleepwheel.mouse"


def _default_db() -> Path:
    return SETTINGS.db_path


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def format_entry(entry) -> str:
    snippet = entry.content.replace("\n", " ").replace("\r", " ")
    if len(snippet) > SETTINGS.snippet_width:
        snippet = snippet[: SETTINGS.snippet_width - 3] + "..."
    return f"[{entry.id}] {entry.created_at} | {snippet}"


def cmd_watch(args: argparse.Namespace) -> int:
    watcher = ClipboardWatcher(ClipboardStore(args.db), interval_seconds=args.interval)
    try:
        watcher.run_forever()
        return 0
    except KeyboardInterrupt:
        return 0


def cmd_mouse(args: argparse.Namespace) -> int:
    return run_mouse_window(args.db)


def cmd_mouse_listen(args: argparse.Namespace) -> int:
    try:
        return listen_for_middle_click(args.db, debounce_seconds=args.debounce)
    except MouseListenerError as exc:
        print(f"mouse listener unavailable: {exc}", file=sys.stderr)
        return 1


def cmd_warm_window(args: argparse.Namespace) -> int:
    return open_warm_window(args.db)


def cmd_webui(args: argparse.Namespace) -> int:
    return serve_webui(args.db, host=args.host, port=args.port, open_browser=not args.no_browser)


def cmd_tui(args: argparse.Namespace) -> int:
    return run_tui(args.db)


def cmd_quick(args: argparse.Namespace) -> int:
    return run_quick_view(args.db)


def cmd_list(args: argparse.Namespace) -> int:
    store = ClipboardStore(args.db)
    for entry in store.list(args.limit):
        print(format_entry(entry))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    store = ClipboardStore(args.db)
    for entry in store.search(args.query, args.limit):
        print(format_entry(entry))
    return 0


def cmd_clear(args: argparse.Namespace) -> int:
    store = ClipboardStore(args.db)
    print(f"removed {store.clear()} entries")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    store = ClipboardStore(args.db)
    limit = args.limit if args.limit > 0 else None
    count = (
        store.export_json(args.output, limit)
        if args.format == "json"
        else store.export_csv(args.output, limit)
    )
    print(f"exported {count} entries -> {args.output}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    store = ClipboardStore(args.db)
    warnings = store.doctor()
    stats = store.stats()
    print(f"db: {args.db}")
    print(f"entries: {stats['entries']}")
    print(f"distinct_hashes: {stats['distinct_hashes']}")
    print("storage_capacity: unlimited")
    print(f"history_view_limit: {SETTINGS.history_view_limit}")
    runtime_warnings = []
    if sys.platform == "darwin":
        for tool in ("pbcopy", "pbpaste"):
            path = shutil.which(tool)
            print(f"{tool}: {path or 'missing'}")
            if not path:
                runtime_warnings.append(f"{tool} is missing")
        watcher_loaded = is_loaded(SETTINGS.launchd_label)
        mouse_loaded = is_loaded(MOUSE_LAUNCHD_LABEL)
        print(f"watcher: {'running' if watcher_loaded else 'stopped'}")
        print(f"mouse_listener: {'running' if mouse_loaded else 'stopped'}")
        if not watcher_loaded:
            runtime_warnings.append("clipboard watcher is stopped")
        if not mouse_loaded:
            runtime_warnings.append("mouse listener is stopped")
    warnings.extend(runtime_warnings)
    if warnings:
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        if any(
            warning
            not in (
                "clipboard history is empty",
                "clipboard watcher is stopped",
                "mouse listener is stopped",
            )
            for warning in warnings
        ):
            return 1
    confidence = "high" if not warnings else "medium"
    print(f"confidence: {confidence}")
    print(f"evidence: database readable and writable at {args.db}")
    print("fallback_reason: none" if not warnings else "fallback_reason: see warnings")
    print("status: ok")
    return 0


def cmd_launchd_install(args: argparse.Namespace) -> int:
    settings = load_settings(args.db)
    plist = build_launchd_plist(settings, sys.executable, Path.cwd())
    write_launchd_plist(settings.launchd_plist_path, plist)
    print(f"wrote {settings.launchd_plist_path}")
    return 0


def _change_launchd_state(args: argparse.Namespace, start: bool) -> int:
    settings = load_settings(args.db)
    if not settings.launchd_plist_path.exists():
        print(f"missing plist: {settings.launchd_plist_path}", file=sys.stderr)
        return 1
    result = load_agent(settings.launchd_plist_path) if start else unload_agent(settings.launchd_plist_path)
    if result.returncode != 0:
        print(result.stderr.strip() or "launchctl failed", file=sys.stderr)
        return result.returncode
    print(f"{'loaded' if start else 'unloaded'} {settings.launchd_label}")
    return 0


def cmd_launchd_start(args: argparse.Namespace) -> int:
    return _change_launchd_state(args, True)


def cmd_launchd_stop(args: argparse.Namespace) -> int:
    return _change_launchd_state(args, False)


def cmd_launchd_status(args: argparse.Namespace) -> int:
    settings = load_settings(args.db)
    print(f"label: {settings.launchd_label}")
    print(f"plist: {settings.launchd_plist_path}")
    print(f"loaded: {is_loaded(settings.launchd_label)}")
    return 0


def _mouse_plist_path() -> Path:
    return Path.home() / "Library/LaunchAgents" / f"{MOUSE_LAUNCHD_LABEL}.plist"


def cmd_mouse_launchd_install(args: argparse.Namespace) -> int:
    settings = load_settings(args.db)
    path = _mouse_plist_path()
    plist = build_mouse_launchd_plist(settings, sys.executable, Path.cwd())
    write_launchd_plist(path, plist)
    print(f"wrote {path}")
    return 0


def _change_mouse_launchd_state(start: bool) -> int:
    path = _mouse_plist_path()
    if not path.exists():
        print(f"missing plist: {path}", file=sys.stderr)
        return 1
    result = load_agent(path) if start else unload_agent(path)
    if result.returncode != 0:
        print(result.stderr.strip() or "launchctl failed", file=sys.stderr)
        return result.returncode
    print(f"{'loaded' if start else 'unloaded'} {MOUSE_LAUNCHD_LABEL}")
    return 0


def cmd_mouse_launchd_start(_args: argparse.Namespace) -> int:
    return _change_mouse_launchd_state(True)


def cmd_mouse_launchd_stop(_args: argparse.Namespace) -> int:
    return _change_mouse_launchd_state(False)


def cmd_mouse_launchd_status(_args: argparse.Namespace) -> int:
    print(f"label: {MOUSE_LAUNCHD_LABEL}")
    print(f"plist: {_mouse_plist_path()}")
    print(f"loaded: {is_loaded(MOUSE_LAUNCHD_LABEL)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cleepwheel")
    parser.add_argument("--db", type=Path, default=_default_db())
    subparsers = parser.add_subparsers(dest="command", required=True)

    watch = subparsers.add_parser("watch", help="monitor clipboard changes")
    watch.add_argument("--interval", type=float, default=SETTINGS.watch_interval)
    watch.set_defaults(func=cmd_watch)

    mouse = subparsers.add_parser("mouse", help="open clipboard window")
    mouse.set_defaults(func=cmd_mouse)

    mouse_listen = subparsers.add_parser(
        "mouse-listen", help="listen globally for the wheel click"
    )
    mouse_listen.add_argument("--debounce", type=float, default=0.18)
    mouse_listen.set_defaults(func=cmd_mouse_listen)

    window = subparsers.add_parser("window", help="open clipboard window")
    window.set_defaults(func=cmd_mouse)

    warm_window = subparsers.add_parser(
        "warm-window", help="keep a hidden window ready for the mouse listener"
    )
    warm_window.set_defaults(func=cmd_warm_window)

    webui = subparsers.add_parser("webui", help="open browser-based clipboard UI")
    webui.add_argument("--host", default="127.0.0.1")
    webui.add_argument("--port", type=positive_int, default=8765)
    webui.add_argument("--no-browser", action="store_true")
    webui.set_defaults(func=cmd_webui)

    tui = subparsers.add_parser("tui", help="open full terminal UI")
    tui.set_defaults(func=cmd_tui)

    quick = subparsers.add_parser("quick", help="open compact terminal UI")
    quick.set_defaults(func=cmd_quick)

    list_cmd = subparsers.add_parser("list", help="show recent entries")
    list_cmd.add_argument("--limit", type=positive_int, default=SETTINGS.history_view_limit)
    list_cmd.set_defaults(func=cmd_list)

    search = subparsers.add_parser("search", help="search entries")
    search.add_argument("query")
    search.add_argument("--limit", type=positive_int, default=SETTINGS.history_view_limit)
    search.set_defaults(func=cmd_search)

    clear = subparsers.add_parser("clear", help="delete all entries")
    clear.set_defaults(func=cmd_clear)

    doctor = subparsers.add_parser("doctor", help="check database health")
    doctor.set_defaults(func=cmd_doctor)

    export = subparsers.add_parser("export", help="export history")
    export.add_argument("--format", choices=["json", "csv"], default="json")
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--limit", type=int, default=0)
    export.set_defaults(func=cmd_export)

    launchd = subparsers.add_parser("launchd", help="manage the clipboard watcher")
    launchd_sub = launchd.add_subparsers(dest="launchd_command", required=True)
    for name, help_text, func in (
        ("install", "write the launch agent plist", cmd_launchd_install),
        ("start", "start the launch agent", cmd_launchd_start),
        ("stop", "stop the launch agent", cmd_launchd_stop),
        ("status", "show launch agent status", cmd_launchd_status),
    ):
        command = launchd_sub.add_parser(name, help=help_text)
        command.set_defaults(func=func)

    mouse_launchd = subparsers.add_parser(
        "mouse-launchd", help="manage the global wheel-click listener"
    )
    mouse_launchd_sub = mouse_launchd.add_subparsers(
        dest="mouse_launchd_command", required=True
    )
    for name, help_text, func in (
        ("install", "write the mouse listener plist", cmd_mouse_launchd_install),
        ("start", "start the mouse listener", cmd_mouse_launchd_start),
        ("stop", "stop the mouse listener", cmd_mouse_launchd_stop),
        ("status", "show mouse listener status", cmd_mouse_launchd_status),
    ):
        command = mouse_launchd_sub.add_parser(name, help=help_text)
        command.set_defaults(func=func)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


def clipwill_main() -> int:
    """Open the graphical history by default, while preserving CLI subcommands."""
    argv = sys.argv[1:]
    return main(argv if argv else ["window"])
