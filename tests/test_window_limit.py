import tempfile
import unittest
from pathlib import Path

from cleepwheel.ui import WindowLimitError, acquire_window_slot


class WindowLimitTest(unittest.TestCase):
    def test_only_two_window_slots_can_be_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "history.sqlite3"
            first = acquire_window_slot(db)
            second = acquire_window_slot(db)
            self.addCleanup(first.close)
            self.addCleanup(second.close)

            with self.assertRaisesRegex(WindowLimitError, "two window"):
                acquire_window_slot(db)

            first.close()
            replacement = acquire_window_slot(db)
            replacement.close()
