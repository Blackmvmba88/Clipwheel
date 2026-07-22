import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cleepwheel.soundcloud import SoundCloudClient
from cleepwheel.soundcloud_auth import (
    SoundCloudTokens,
    build_authorize_url,
    exchange_authorization_code,
    generate_pkce_pair,
    load_tokens,
    refresh_access_token,
    save_tokens,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class SoundCloudAuthTest(unittest.TestCase):
    def test_generates_pkce_verifier_and_challenge(self):
        pair = generate_pkce_pair()

        self.assertGreaterEqual(len(pair.verifier), 43)
        self.assertNotIn("=", pair.challenge)
        self.assertGreaterEqual(len(pair.challenge), 43)

    def test_build_authorize_url_contains_pkce_params(self):
        url = build_authorize_url(
            "client-id",
            "http://127.0.0.1:8765/callback",
            "challenge",
            "state",
        )

        self.assertIn("client_id=client-id", url)
        self.assertIn("response_type=code", url)
        self.assertIn("code_challenge=challenge", url)
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn("state=state", url)

    def test_exchange_authorization_code_posts_form_data(self):
        captured = {}

        def fake_urlopen(req, timeout):
            captured["method"] = req.get_method()
            captured["body"] = req.data.decode("utf-8")
            captured["headers"] = dict(req.header_items())
            captured["timeout"] = timeout
            return FakeResponse(
                {
                    "access_token": "access",
                    "refresh_token": "refresh",
                    "expires_in": 3600,
                    "token_type": "OAuth",
                }
            )

        with patch("cleepwheel.soundcloud_auth.request.urlopen", side_effect=fake_urlopen):
            tokens = exchange_authorization_code(
                client_id="client-id",
                client_secret="secret",
                redirect_uri="http://127.0.0.1:8765/callback",
                code="code",
                code_verifier="verifier",
            )

        self.assertEqual(tokens.access_token, "access")
        self.assertEqual(tokens.refresh_token, "refresh")
        self.assertEqual(captured["method"], "POST")
        self.assertIn("grant_type=authorization_code", captured["body"])
        self.assertIn("client_secret=secret", captured["body"])
        self.assertEqual(captured["headers"]["Content-type"], "application/x-www-form-urlencoded")
        self.assertEqual(captured["timeout"], 20)

    def test_refresh_access_token_posts_refresh_grant(self):
        captured = {}

        def fake_urlopen(req, timeout):
            captured["body"] = req.data.decode("utf-8")
            return FakeResponse({"access_token": "new", "expires_in": 3600})

        with patch("cleepwheel.soundcloud_auth.request.urlopen", side_effect=fake_urlopen):
            tokens = refresh_access_token(
                client_id="client-id",
                refresh_token="refresh",
            )

        self.assertEqual(tokens.access_token, "new")
        self.assertIn("grant_type=refresh_token", captured["body"])
        self.assertIn("refresh_token=refresh", captured["body"])

    def test_saves_tokens_with_private_permissions_and_client_can_load_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "token.json"
            saved = save_tokens(
                SoundCloudTokens(
                    access_token="access",
                    refresh_token="refresh",
                    expires_in=3600,
                    obtained_at=100,
                ),
                path,
            )

            self.assertEqual(saved, path)
            self.assertEqual(oct(path.stat().st_mode & 0o777), "0o600")
            self.assertEqual(load_tokens(path).access_token, "access")
            self.assertEqual(SoundCloudClient.from_token_file(path).access_token, "access")
