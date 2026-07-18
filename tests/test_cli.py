import argparse
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from cleepwheel import cli
from cleepwheel.domain import ClipboardEntry


class CliTest(unittest.TestCase):
    def test_positive_int_accepts_positive_values_and_rejects_others(self):
        self.assertEqual(cli.positive_int("3"), 3)
        with self.assertRaises(argparse.ArgumentTypeError):
            cli.positive_int("0")

    def test_format_entry_flattens_and_truncates_content(self):
        entry = ClipboardEntry(7, "a\n" + "b" * 130, "now", "hash")
        rendered = cli.format_entry(entry)

        self.assertTrue(rendered.startswith("[7] now | a "))
        self.assertTrue(rendered.endswith("..."))
        self.assertNotIn("\n", rendered)

    def test_list_search_clear_and_export_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "history.sqlite3"
            output = Path(tmp) / "history.json"
            store = cli.ClipboardStore(db)
            store.add("alpha")
            store.add("beta")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(cli.main(["--db", str(db), "list", "--limit", "1"]), 0)
                self.assertEqual(cli.main(["--db", str(db), "search", "alpha"]), 0)
                self.assertEqual(
                    cli.main(["--db", str(db), "export", "--output", str(output)]), 0
                )
                self.assertEqual(cli.main(["--db", str(db), "clear"]), 0)

            text = stdout.getvalue()
            self.assertIn("beta", text)
            self.assertIn("alpha", text)
            self.assertIn("exported 2 entries", text)
            self.assertIn("removed 2 entries", text)
            self.assertTrue(output.exists())

    def test_doctor_treats_empty_history_as_healthy_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "history.sqlite3"
            stdout, stderr = io.StringIO(), io.StringIO()

            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = cli.main(["--db", str(db), "doctor"])

            self.assertEqual(result, 0)
            self.assertIn("status: ok", stdout.getvalue())
            self.assertIn("warning: clipboard history is empty", stderr.getvalue())

    def test_pin_and_unpin_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "history.sqlite3"
            store = cli.ClipboardStore(db)
            store.add("important")
            entry_id = store.latest().id
            self.assertEqual(cli.main(["--db", str(db), "pin", str(entry_id)]), 0)
            self.assertTrue(store.get(entry_id).pinned)
            self.assertEqual(cli.main(["--db", str(db), "unpin", str(entry_id)]), 0)
            self.assertFalse(store.get(entry_id).pinned)
            self.assertEqual(cli.main(["--db", str(db), "pin", "999"]), 1)

    @patch("cleepwheel.cli.ClipboardStore")
    def test_doctor_fails_for_database_warning(self, store_type):
        store_type.return_value.doctor.return_value = ["integrity check failed"]
        store_type.return_value.count.return_value = 4

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = cli.main(["doctor"])

        self.assertEqual(result, 1)

    @patch("cleepwheel.cli.ClipboardWatcher")
    @patch("cleepwheel.cli.ClipboardStore")
    def test_watch_exits_cleanly_on_keyboard_interrupt(self, _store, watcher_type):
        watcher_type.return_value.run_forever.side_effect = KeyboardInterrupt

        self.assertEqual(cli.main(["watch", "--interval", "0.1"]), 0)

    @patch("cleepwheel.cli.run_mouse_window", return_value=0)
    def test_mouse_delegates_to_window(self, run_window):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "history.sqlite3"
            self.assertEqual(cli.main(["--db", str(db), "mouse"]), 0)
            run_window.assert_called_once_with(db)

    @patch("cleepwheel.cli.listen_for_middle_click", return_value=0)
    def test_mouse_listener_delegates_with_debounce(self, listen):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "history.sqlite3"
            self.assertEqual(
                cli.main(["--db", str(db), "mouse-listen", "--debounce", "1.25"]),
                0,
            )
        listen.assert_called_once_with(db, debounce_seconds=1.25)

    @patch("cleepwheel.cli.serve_webui", return_value=0)
    def test_webui_delegates_to_browser_server(self, serve_webui):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "history.sqlite3"
            self.assertEqual(
                cli.main(["--db", str(db), "webui", "--host", "0.0.0.0", "--port", "9010", "--no-browser"]),
                0,
            )
            serve_webui.assert_called_once_with(db, host="0.0.0.0", port=9010, open_browser=False)

    @patch("cleepwheel.cli.run_mouse_window", return_value=0)
    @patch("sys.argv", ["clipwill"])
    def test_clipwill_opens_window_by_default(self, run_window):
        self.assertEqual(cli.clipwill_main(), 0)
        run_window.assert_called_once_with(cli.SETTINGS.db_path)
