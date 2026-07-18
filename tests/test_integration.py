import os
import tempfile
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib import request
from unittest.mock import patch

from cleepwheel.launchd import build_launchd_plist, build_mouse_launchd_plist
from cleepwheel.settings import default_db_path, load_settings
from cleepwheel.tui import _filter_entries, _highlight_match, _truncate
from cleepwheel.domain import ClipboardEntry
from cleepwheel.webui import WebUIHandler
from cleepwheel.storage import ClipboardStore


class IntegratedInfrastructureTest(unittest.TestCase):
    def test_settings_support_environment_overrides(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "XDG_DATA_HOME": tmp,
                "CLEEPWHEEL_WATCH_INTERVAL": "0.5",
                "CLEEPWHEEL_SNIPPET_WIDTH": "80",
                "CLEEPWHEEL_MAX_CONTENT_CHARS": "1000",
                "CLEEPWHEEL_HISTORY_LIMIT": "2500",
            },
            clear=False,
        ):
            settings = load_settings()

        self.assertEqual(settings.db_path, Path(tmp) / "cleepwheel/clipboard.sqlite3")
        self.assertEqual(settings.watch_interval, 0.5)
        self.assertEqual(settings.snippet_width, 80)
        self.assertEqual(settings.max_content_chars, 1000)
        self.assertEqual(settings.history_view_limit, 2500)

    def test_default_db_remains_the_live_history_path(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                default_db_path(),
                Path.home() / ".local/share/cleepwheel/clipboard.sqlite3",
            )

    def test_launchd_plist_runs_the_integrated_watcher(self):
        settings = load_settings(Path("/tmp/cleepwheel.sqlite3"))
        plist = build_launchd_plist(settings, "/usr/bin/python3", Path("/tmp/project"))

        self.assertEqual(plist["Label"], settings.launchd_label)
        self.assertEqual(plist["WorkingDirectory"], "/tmp/project")
        self.assertEqual(
            plist["ProgramArguments"],
            [
                "/usr/bin/python3",
                "-m",
                "cleepwheel",
                "--db",
                "/tmp/cleepwheel.sqlite3",
                "watch",
                "--interval",
                str(settings.watch_interval),
            ],
        )

    def test_tui_helpers_filter_and_format_entries(self):
        entries = [
            ClipboardEntry(1, "Alpha text", "now", "a" * 64),
            ClipboardEntry(2, "Beta text", "now", "b" * 64),
        ]

        self.assertEqual(_filter_entries(entries, "ALPHA"), [entries[0]])
        self.assertEqual(_truncate("one\ntwo", 20), "one two")
        self.assertEqual(_truncate("123456", 5), "12...")
        self.assertEqual(_highlight_match("Alpha text", "alpha"), ("<Alpha> text", True))

    def test_mouse_launchd_plist_runs_global_listener(self):
        settings = load_settings(Path("/tmp/cleepwheel.sqlite3"))
        plist = build_mouse_launchd_plist(
            settings, "/usr/bin/python3", Path("/tmp/project")
        )

        self.assertEqual(plist["Label"], "com.blackmamba.cleepwheel.mouse")
        self.assertEqual(plist["ProgramArguments"][-1], "mouse-listen")
        self.assertTrue(plist["KeepAlive"])

    def test_webui_serves_and_mutates_shared_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "history.sqlite3"
            store = ClipboardStore(db)
            store.add("first entry")
            store.add("second entry")

            handler = type("TestWebUIHandler", (WebUIHandler,), {})
            handler.store = store
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                index = request.urlopen(f"{base}/").read().decode("utf-8")
                self.assertIn("CleepWheel WebUI", index)

                entries = request.urlopen(f"{base}/api/entries?query=second").read().decode("utf-8")
                self.assertIn("second entry", entries)

                copy_req = request.Request(f"{base}/api/entries/2/copy", method="POST")
                with patch("cleepwheel.webui.write_clipboard_text") as write_clipboard:
                    copy_resp = request.urlopen(copy_req).read().decode("utf-8")
                self.assertIn('"ok": true', copy_resp)
                write_clipboard.assert_called_once_with("second entry")

                update_req = request.Request(
                    f"{base}/api/entries/2",
                    data=b'{"content":"second updated"}',
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                update_resp = request.urlopen(update_req).read().decode("utf-8")
                self.assertIn("second updated", update_resp)

                pin_req = request.Request(
                    f"{base}/api/entries/2/pin",
                    data=b'{"pinned":true}',
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                pin_resp = request.urlopen(pin_req).read().decode("utf-8")
                self.assertIn('"pinned": true', pin_resp)
                self.assertTrue(store.get(2).pinned)

                delete_req = request.Request(f"{base}/api/entries/1", method="DELETE")
                delete_resp = request.urlopen(delete_req).read().decode("utf-8")
                self.assertIn('"ok": true', delete_resp)
            finally:
                server.shutdown()
                server.server_close()
