import unittest
from unittest.mock import Mock, patch

from cleepwheel.watcher import ClipboardWatcher


class ClipboardWatcherTest(unittest.TestCase):
    @patch("cleepwheel.watcher.time.sleep", side_effect=KeyboardInterrupt)
    @patch("cleepwheel.watcher.read_clipboard_text", return_value="copied text")
    def test_adds_new_clipboard_text(self, _read, _sleep):
        store = Mock()

        with self.assertRaises(KeyboardInterrupt):
            ClipboardWatcher(store, interval_seconds=0.25).run_forever()

        store.add.assert_called_once_with("copied text")
        _sleep.assert_called_once_with(0.25)

    @patch("cleepwheel.watcher.time.sleep", side_effect=[None, KeyboardInterrupt])
    @patch("cleepwheel.watcher.read_clipboard_text", side_effect=["same", "same"])
    def test_ignores_unchanged_clipboard_text(self, _read, _sleep):
        store = Mock()

        with self.assertRaises(KeyboardInterrupt):
            ClipboardWatcher(store).run_forever()

        store.add.assert_called_once_with("same")

    @patch("cleepwheel.watcher.time.sleep", side_effect=KeyboardInterrupt)
    @patch("cleepwheel.watcher.read_clipboard_text", return_value="")
    def test_ignores_empty_clipboard(self, _read, _sleep):
        store = Mock()

        with self.assertRaises(KeyboardInterrupt):
            ClipboardWatcher(store).run_forever()

        store.add.assert_not_called()

    @patch("cleepwheel.watcher.time.sleep", side_effect=[None, KeyboardInterrupt])
    @patch(
        "cleepwheel.watcher.read_clipboard_text",
        side_effect=[RuntimeError("temporary failure"), "recovered"],
    )
    def test_recovers_after_clipboard_read_failure(self, _read, _sleep):
        store = Mock()

        with patch("sys.stderr"), self.assertRaises(KeyboardInterrupt):
            ClipboardWatcher(store).run_forever()

        store.add.assert_called_once_with("recovered")
