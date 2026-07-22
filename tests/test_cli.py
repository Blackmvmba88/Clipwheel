import argparse
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from cleepwheel import cli
from cleepwheel.domain import ClipboardEntry
from cleepwheel.soundcloud_auth import SoundCloudTokens, save_tokens


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

    def test_classify_command_handles_text_entries_and_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "history.sqlite3"
            store = cli.ClipboardStore(db)
            store.add("Coro\nUna voz\nUna voz\nVerso\nSigue el sol")
            entry = store.latest()

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(cli.main(["--db", str(db), "classify", "Black Mamba - Beat.wav"]), 0)
                self.assertEqual(cli.main(["--db", str(db), "classify", "--entry", str(entry.id)]), 0)
                self.assertEqual(cli.main(["--db", str(db), "classify", "--category", "song"]), 0)

            text = stdout.getvalue()
            self.assertIn("category: song", text)
            self.assertIn("song |", text)

    def test_doctor_treats_empty_history_as_healthy_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "history.sqlite3"
            stdout, stderr = io.StringIO(), io.StringIO()

            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = cli.main(["--db", str(db), "doctor"])

            self.assertEqual(result, 0)
            self.assertIn("status: ok", stdout.getvalue())
            self.assertIn("warning: clipboard history is empty", stderr.getvalue())

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

    @patch("cleepwheel.cli.serve_soundcloud_autofill", return_value=0)
    def test_soundcloud_autofill_delegates_to_server(self, serve_autofill):
        self.assertEqual(
            cli.main(
                [
                    "soundcloud-autofill",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "9999",
                    "--main-artist",
                    "Artist",
                    "--songwriter",
                    "Writer",
                    "--label",
                    "Label",
                    "--explicit",
                    "--has-isrc",
                    "--no-browser",
                ]
            ),
            0,
        )

        kwargs = serve_autofill.call_args.kwargs
        self.assertEqual(kwargs["host"], "0.0.0.0")
        self.assertEqual(kwargs["port"], 9999)
        self.assertFalse(kwargs["open_browser"])
        self.assertEqual(kwargs["profile"].main_artist, "Artist")
        self.assertEqual(kwargs["profile"].songwriter, "Writer")
        self.assertEqual(kwargs["profile"].label, "Label")
        self.assertTrue(kwargs["profile"].explicit)
        self.assertTrue(kwargs["profile"].has_isrc)

    @patch("cleepwheel.cli.login_with_pkce")
    def test_soundcloud_auth_login_uses_env_credentials(self, login):
        login.return_value = Path("/tmp/token.json")

        with patch.dict(
            "os.environ",
            {"SOUNDCLOUD_CLIENT_ID": "client", "SOUNDCLOUD_CLIENT_SECRET": "secret"},
        ), contextlib.redirect_stdout(io.StringIO()) as stdout:
            result = cli.main(["soundcloud-auth", "login", "--no-browser", "--timeout", "1"])

        self.assertEqual(result, 0)
        self.assertIn("saved SoundCloud tokens", stdout.getvalue())
        login.assert_called_once()
        kwargs = login.call_args.kwargs
        self.assertEqual(kwargs["client_id"], "client")
        self.assertEqual(kwargs["client_secret"], "secret")
        self.assertFalse(kwargs["open_browser"])

    def test_soundcloud_auth_status_reads_token_file_without_printing_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "token.json"
            save_tokens(
                SoundCloudTokens(
                    access_token="secret-access",
                    refresh_token="secret-refresh",
                    expires_in=3600,
                    obtained_at=100,
                ),
                path,
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = cli.main(["soundcloud-auth", "status", "--token-file", str(path)])

        text = stdout.getvalue()
        self.assertEqual(result, 0)
        self.assertIn("access_token: present", text)
        self.assertIn("refresh_token: present", text)
        self.assertNotIn("secret-access", text)
        self.assertNotIn("secret-refresh", text)

    @patch("cleepwheel.cli.refresh_access_token")
    def test_soundcloud_auth_refresh_updates_token_file(self, refresh):
        refresh.return_value = SoundCloudTokens(
            access_token="new-access",
            refresh_token="new-refresh",
            expires_in=3600,
            obtained_at=200,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "token.json"
            save_tokens(
                SoundCloudTokens(
                    access_token="old-access",
                    refresh_token="old-refresh",
                    expires_in=3600,
                    obtained_at=100,
                ),
                path,
            )
            with patch.dict("os.environ", {"SOUNDCLOUD_CLIENT_ID": "client"}):
                with contextlib.redirect_stdout(io.StringIO()):
                    result = cli.main(["soundcloud-auth", "refresh", "--token-file", str(path)])

            refreshed = cli.load_tokens(path)

        self.assertEqual(result, 0)
        self.assertEqual(refreshed.access_token, "new-access")
        refresh.assert_called_once()

    @patch("cleepwheel.cli.run_mouse_window", return_value=0)
    @patch("sys.argv", ["clipwill"])
    def test_clipwill_opens_window_by_default(self, run_window):
        self.assertEqual(cli.clipwill_main(), 0)
        run_window.assert_called_once_with(cli.SETTINGS.db_path)
