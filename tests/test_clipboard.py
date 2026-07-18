import subprocess
import unittest
from unittest.mock import patch

from cleepwheel.clipboard import read_clipboard_text, write_clipboard_text


class ClipboardTest(unittest.TestCase):
    @patch("cleepwheel.clipboard.subprocess.run")
    def test_read_returns_text_without_trailing_newlines(self, run):
        run.return_value = subprocess.CompletedProcess(["pbpaste"], 0, "hello\n\n", "")

        self.assertEqual(read_clipboard_text(), "hello")
        run.assert_called_once_with(["pbpaste"], capture_output=True, text=True, check=False)

    @patch("cleepwheel.clipboard.subprocess.run")
    def test_read_raises_useful_error(self, run):
        run.return_value = subprocess.CompletedProcess(["pbpaste"], 1, "", "clipboard unavailable\n")

        with self.assertRaisesRegex(RuntimeError, "clipboard unavailable"):
            read_clipboard_text()

    @patch("cleepwheel.clipboard.subprocess.run")
    def test_read_uses_fallback_error_when_stderr_is_empty(self, run):
        run.return_value = subprocess.CompletedProcess(["pbpaste"], 1, "", "")

        with self.assertRaisesRegex(RuntimeError, "pbpaste failed"):
            read_clipboard_text()

    @patch("cleepwheel.clipboard.subprocess.run")
    def test_write_sends_exact_text_to_pbcopy(self, run):
        write_clipboard_text("hello\nworld")

        run.assert_called_once_with(["pbcopy"], input="hello\nworld", text=True, check=True)
