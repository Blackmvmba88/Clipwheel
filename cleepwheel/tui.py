from __future__ import annotations

import curses
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .domain import ClipboardEntry
from .storage import ClipboardStore
from .settings import load_settings


HELP_TEXT = "j/k move  / search  Backspace delete  Enter copy  r refresh  c clear  d details  h help  q quit"
HELP_LINES = [
    "j/k or arrows: move selection",
    "f/b or PageDown/PageUp: move by page",
    "g/G: go to first/last entry",
    "/: search with live incremental filter",
    "Enter or y: copy selected entry to clipboard",
    "r: refresh history",
    "c: clear search",
    "d: toggle detail pane",
    "h or ?: toggle this help",
    "q or Esc: quit",
]


@dataclass
class TUIState:
    query: str = ""
    selected: int = 0
    message: str = "ready"
    detail: bool = True
    help_visible: bool = False


def _clipboard_set(text: str) -> None:
    subprocess.run(["pbcopy"], input=text, text=True, check=True)


def _truncate(text: str, width: int) -> str:
    cleaned = text.replace("\n", " ").replace("\r", " ")
    if width <= 0:
        return ""
    if len(cleaned) <= width:
        return cleaned
    if width <= 3:
        return cleaned[:width]
    return cleaned[: width - 3] + "..."


def _highlight_match(text: str, query: str) -> tuple[str, bool]:
    if not query:
        return text, False
    lower = text.lower()
    needle = query.lower()
    idx = lower.find(needle)
    if idx < 0:
        return text, False
    end = idx + len(query)
    return f"{text[:idx]}<{text[idx:end]}>{text[end:]}", True


def _wrap_lines(text: str, width: int) -> list[str]:
    if width <= 1:
        return [text[:width]]
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        chunk = paragraph.strip() or ""
        while len(chunk) > width:
            lines.append(chunk[:width])
            chunk = chunk[width:]
        lines.append(chunk)
    return lines or [""]


def _filter_entries(entries: list[ClipboardEntry], query: str) -> list[ClipboardEntry]:
    if not query:
        return entries
    q = query.lower()
    return [entry for entry in entries if q in entry.content.lower()]


def _load_entries(store: ClipboardStore) -> list[ClipboardEntry]:
    return store.list(load_settings(store.db_path).history_view_limit)


def run_tui(db_path: Path) -> int:
    store = ClipboardStore(db_path)
    state = TUIState()
    entries = _load_entries(store)
    cursor = 0
    jump_buffer = ""
    jump_hits = 0

    def current_filtered() -> list[ClipboardEntry]:
        return _filter_entries(entries, state.query)

    def refresh() -> list[ClipboardEntry]:
        nonlocal entries, cursor
        entries = _load_entries(store)
        cursor = 0
        state.selected = 0
        return current_filtered()

    def set_message(message: str) -> None:
        state.message = message

    def sync_selection(filtered: list[ClipboardEntry]) -> None:
        nonlocal cursor
        if not filtered:
            state.selected = 0
            cursor = 0
            return
        cursor = max(0, min(cursor, len(filtered) - 1))
        state.selected = cursor

    def draw(stdscr: curses.window, filtered: list[ClipboardEntry]) -> None:
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        list_top = 5
        detail_width = max(24, width // 2)
        list_width = max(20, width - detail_width - 3)
        available = max(1, height - list_top - 2)

        stdscr.addnstr(0, 0, f"CleepWheel  {db_path}", width - 1, curses.A_BOLD)
        stdscr.addnstr(1, 0, f"{state.message}", width - 1)
        stdscr.addnstr(2, 0, f"search: {state.query or '(none)'}", width - 1)
        stdscr.addnstr(3, 0, f"items: {len(filtered)} / {len(entries)}  detail: {'on' if state.detail else 'off'}", width - 1)
        stdscr.addnstr(4, 0, HELP_TEXT, width - 1)

        if state.help_visible:
            box_w = min(width - 4, 60)
            box_h = min(height - 4, len(HELP_LINES) + 4)
            start_y = max(0, (height - box_h) // 2)
            start_x = max(0, (width - box_w) // 2)
            for y in range(start_y, start_y + box_h):
                stdscr.addnstr(y, start_x, " " * box_w, box_w, curses.A_REVERSE)
            stdscr.addnstr(start_y + 1, start_x + 2, "Help", box_w - 4, curses.A_BOLD)
            for idx, line in enumerate(HELP_LINES):
                if idx + 3 >= box_h:
                    break
                stdscr.addnstr(start_y + 2 + idx, start_x + 2, line, box_w - 4)
            stdscr.addnstr(start_y + box_h - 2, start_x + 2, "press h, ?, or Esc to close", box_w - 4)

        if not filtered:
            stdscr.addnstr(list_top, 0, "(no matches)", width - 1)
            stdscr.refresh()
            return

        top = max(0, state.selected - available + 1)
        visible = filtered[top : top + available]
        for idx, entry in enumerate(visible):
            absolute = top + idx
            selected = absolute == state.selected
            prefix = ">" if selected else " "
            content = _truncate(entry.content, list_width - 24)
            content, matched = _highlight_match(content, state.query)
            line = f"{prefix} [{entry.id}] {entry.created_at} {content}"
            attr = curses.A_REVERSE if selected else curses.A_NORMAL
            if matched:
                attr |= curses.A_BOLD
            stdscr.addnstr(list_top + idx, 0, line, list_width - 1, attr)

        if state.detail:
            selected_entry = filtered[state.selected]
            detail_x = list_width + 2
            detail_lines = [
                f"id: {selected_entry.id}",
                f"created_at: {selected_entry.created_at}",
                f"hash: {selected_entry.content_hash[:16]}...",
                f"chars: {len(selected_entry.content)}",
                "",
                "content:",
            ]
            wrapped = _wrap_lines(selected_entry.content, max(10, detail_width - 2))
            detail_lines.extend(wrapped)
            for idx, line in enumerate(detail_lines[: max(0, height - list_top - 1)]):
                stdscr.addnstr(list_top + idx, detail_x, _truncate(line, detail_width - 1), detail_width - 1)

        stdscr.refresh()

    def apply_jump(filtered: list[ClipboardEntry]) -> None:
        nonlocal jump_buffer, jump_hits
        if not jump_buffer:
            return
        try:
            target = int(jump_buffer)
        except ValueError:
            set_message(f"invalid id {jump_buffer}")
            jump_buffer = ""
            return
        matches = [i for i, entry in enumerate(filtered) if entry.id == target]
        jump_hits = len(matches)
        if matches:
            state.selected = matches[0]
            set_message(f"jumped to id {target}")
        else:
            set_message(f"no entry with id {target}")
        jump_buffer = ""

    def read_search(stdscr: curses.window) -> None:
        curses.curs_set(1)
        stdscr.move(2, len("search: "))
        stdscr.clrtoeol()
        stdscr.refresh()
        value = state.query
        pos = len(value)
        while True:
            stdscr.move(2, len("search: ") + pos)
            stdscr.clrtoeol()
            stdscr.addstr(2, len("search: "), value)
            stdscr.refresh()
            key = stdscr.getch()
            if key in (10, 13, curses.KEY_ENTER):
                break
            if key in (27,):
                value = state.query
                break
            if key in (curses.KEY_BACKSPACE, 127, 8):
                if pos > 0:
                    value = value[: pos - 1] + value[pos:]
                    pos -= 1
            elif key in (curses.KEY_LEFT,):
                pos = max(0, pos - 1)
            elif key in (curses.KEY_RIGHT,):
                pos = min(len(value), pos + 1)
            elif key in (curses.KEY_HOME,):
                pos = 0
            elif key in (curses.KEY_END,):
                pos = len(value)
            elif 32 <= key <= 126:
                ch = chr(key)
                value = value[:pos] + ch + value[pos:]
                pos += 1
            state.query = value.strip()
            filtered = current_filtered()
            sync_selection(filtered)
            draw(stdscr, filtered)
        state.query = value.strip()
        curses.curs_set(0)
        filtered = current_filtered()
        sync_selection(filtered)
        state.message = f"search: {state.query or '(none)'}"
        draw(stdscr, filtered)

    def loop(stdscr: curses.window) -> int:
        curses.curs_set(0)
        stdscr.keypad(True)
        filtered = current_filtered()
        sync_selection(filtered)
        while True:
            state.message = state.message if jump_buffer == "" else f"jump id: {jump_buffer}"
            draw(stdscr, filtered)
            key = stdscr.getch()

            if key in (ord("h"), ord("?")):
                state.help_visible = not state.help_visible
                set_message(f"help {'on' if state.help_visible else 'off'}")
                continue
            if state.help_visible and key in (27,):
                state.help_visible = False
                set_message("help off")
                continue
            if key in (ord("q"), 27):
                return 0
            if ord("0") <= key <= ord("9") and not state.query:
                jump_buffer += chr(key)
                set_message(f"jump id: {jump_buffer}")
                continue
            if key in (curses.KEY_DOWN, ord("j")) and state.selected < len(filtered) - 1:
                state.selected += 1
                cursor = state.selected
            elif key in (curses.KEY_UP, ord("k")) and state.selected > 0:
                state.selected -= 1
                cursor = state.selected
            elif key in (curses.KEY_NPAGE, ord("f")):
                state.selected = min(len(filtered) - 1, state.selected + 10)
                cursor = state.selected
            elif key in (curses.KEY_PPAGE, ord("b")):
                state.selected = max(0, state.selected - 10)
                cursor = state.selected
            elif key in (ord("g"),):
                state.selected = 0
                cursor = state.selected
            elif key in (ord("G"),):
                state.selected = max(0, len(filtered) - 1)
                cursor = state.selected
            elif key in (ord("r"),):
                filtered = refresh()
                set_message("refreshed")
            elif key in (ord("c"),):
                state.query = ""
                filtered = refresh()
                set_message("search cleared")
            elif key in (ord("d"),):
                state.detail = not state.detail
                set_message(f"detail {'on' if state.detail else 'off'}")
            elif key in (ord("/"),):
                read_search(stdscr)
                filtered = current_filtered()
                sync_selection(filtered)
            elif key in (curses.KEY_BACKSPACE, 127, 8) and jump_buffer:
                jump_buffer = jump_buffer[:-1]
                set_message(f"jump id: {jump_buffer or '(none)'}")
            elif key in (10, 13, curses.KEY_ENTER) and jump_buffer:
                apply_jump(filtered)
            elif key in (curses.KEY_ENTER, 10, 13, ord("y")):
                if filtered:
                    selected = filtered[state.selected]
                    _clipboard_set(selected.content)
                    set_message(f"copied entry {selected.id}")
            elif key in (ord("x"),):
                return 0

            sync_selection(filtered)

        return 0

    return curses.wrapper(loop)


def run_quick_view(db_path: Path) -> int:
    store = ClipboardStore(db_path)
    entries = store.list(12)
    selected = 0

    def draw(stdscr: curses.window) -> None:
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        title = "CleepWheel Quick View"
        stdscr.addnstr(0, 0, title, width - 1, curses.A_BOLD)
        if not entries:
            stdscr.addnstr(2, 0, "No clipboard history yet.", width - 1)
            stdscr.addnstr(3, 0, "Press q to exit.", width - 1)
            stdscr.refresh()
            return

        latest = entries[0]
        stdscr.addnstr(2, 0, f"latest: [{latest.id}] {latest.created_at}", width - 1, curses.A_BOLD)
        stdscr.addnstr(3, 0, _truncate(latest.content, width - 1), width - 1)
        stdscr.addnstr(5, 0, "recent copied items:", width - 1, curses.A_BOLD)

        start = 0
        visible = entries[start : start + max(1, height - 8)]
        for idx, entry in enumerate(visible):
            attr = curses.A_REVERSE if idx == selected else curses.A_NORMAL
            line = f"{entry.id:>4}  {entry.created_at}  {_truncate(entry.content, width - 14)}"
            stdscr.addnstr(6 + idx, 0, line, width - 1, attr)

        stdscr.addnstr(height - 2, 0, "Enter/y copy  q exit  r refresh", width - 1)
        stdscr.refresh()

    def loop(stdscr: curses.window) -> int:
        nonlocal entries, selected
        curses.curs_set(0)
        stdscr.keypad(True)
        while True:
            draw(stdscr)
            key = stdscr.getch()
            if key in (ord("q"), 27):
                return 0
            if key in (curses.KEY_DOWN, ord("j")) and selected < len(entries) - 1:
                selected += 1
            elif key in (curses.KEY_UP, ord("k")) and selected > 0:
                selected -= 1
            elif key in (ord("r"),):
                entries = store.list(12)
                selected = 0
            elif key in (curses.KEY_ENTER, 10, 13, ord("y")) and entries:
                _clipboard_set(entries[selected].content)
            elif key in (ord("e"),):
                return 0
        return 0

    return curses.wrapper(loop)
