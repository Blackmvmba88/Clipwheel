from __future__ import annotations

import time
from pathlib import Path

from .clipboard import read_clipboard_text
from .storage import ClipboardStore


class ClipboardWatcher:
    def __init__(self, store: ClipboardStore, interval_seconds: float = 1.0):
        self.store = store
        self.interval_seconds = interval_seconds

    def run_forever(self) -> None:
        last = None
        while True:
            current = read_clipboard_text()
            if current and current != last:
                self.store.add(current)
                last = current
            time.sleep(self.interval_seconds)
