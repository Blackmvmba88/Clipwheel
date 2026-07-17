from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .mouse import run_mouse_window
from .storage import ClipboardStore
from .watcher import ClipboardWatcher


def _default_db() -> Path:
    return Path.home() / ".local/share/cleepwheel/clipboard.sqlite3"


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def format_entry(entry) -> str:
    snippet = entry.content.replace("\n", " ").replace("\r", " ")
    if len(snippet) > 120:
        snippet = snippet[:117] + "..."
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
    count = store.export_json(args.output) if args.format == "json" else store.export_csv(args.output)
    print(f"exported {count} entries -> {args.output}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    store = ClipboardStore(args.db)
    warnings = store.doctor()
    print(f"db: {args.db}")
    print(f"entries: {store.count()}")
    if warnings:
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        if any(warning != "clipboard history is empty" for warning in warnings):
            return 1
    print("status: ok")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cleepwheel")
    parser.add_argument("--db", type=Path, default=_default_db())
    subparsers = parser.add_subparsers(dest="command", required=True)

    watch = subparsers.add_parser("watch", help="monitor clipboard changes")
    watch.add_argument("--interval", type=float, default=1.0)
    watch.set_defaults(func=cmd_watch)

    mouse = subparsers.add_parser("mouse", help="open clipboard window")
    mouse.set_defaults(func=cmd_mouse)

    list_cmd = subparsers.add_parser("list", help="show recent entries")
    list_cmd.add_argument("--limit", type=positive_int, default=50)
    list_cmd.set_defaults(func=cmd_list)

    search = subparsers.add_parser("search", help="search entries")
    search.add_argument("query")
    search.add_argument("--limit", type=positive_int, default=50)
    search.set_defaults(func=cmd_search)

    clear = subparsers.add_parser("clear", help="delete all entries")
    clear.set_defaults(func=cmd_clear)

    doctor = subparsers.add_parser("doctor", help="check database health")
    doctor.set_defaults(func=cmd_doctor)

    export = subparsers.add_parser("export", help="export history")
    export.add_argument("--format", choices=["json", "csv"], default="json")
    export.add_argument("--output", type=Path, required=True)
    export.set_defaults(func=cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
