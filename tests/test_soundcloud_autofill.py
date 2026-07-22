import json
import tempfile
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib import request

from cleepwheel.soundcloud_autofill import (
    SoundCloudAutofillHandler,
    SoundCloudAutofillProfile,
    generate_autofill_script,
)


class SoundCloudAutofillTest(unittest.TestCase):
    def test_generate_autofill_script_embeds_profile_without_secrets(self):
        script = generate_autofill_script(
            SoundCloudAutofillProfile(
                main_artist="Artist",
                songwriter="Writer",
                label="Label",
                explicit=True,
                has_isrc=True,
            )
        )

        self.assertIn('"main_artist": "Artist"', script)
        self.assertIn('"songwriter": "Writer"', script)
        self.assertIn('"label": "Label"', script)
        self.assertIn('"explicit": true', script)
        self.assertIn("monetize this track", script)
        self.assertNotIn("access_token", script)
        self.assertNotIn("client_secret", script)

    def test_autofill_handler_serves_page_and_generates_custom_script(self):
        handler = type("TestAutofillHandler", (SoundCloudAutofillHandler,), {})
        handler.profile = SoundCloudAutofillProfile()
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            index = request.urlopen(f"{base}/").read().decode("utf-8")
            self.assertIn("SoundCloud Autofill", index)

            payload = json.dumps(
                {
                    "main_artist": "Custom Artist",
                    "songwriter": "Custom Writer",
                    "label": "Custom Label",
                    "explicit": False,
                }
            ).encode("utf-8")
            req = request.Request(
                f"{base}/script",
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            script = request.urlopen(req).read().decode("utf-8")
            self.assertIn("Custom Artist", script)
            self.assertIn("Custom Writer", script)
            self.assertIn("Custom Label", script)
        finally:
            server.shutdown()
            server.server_close()
