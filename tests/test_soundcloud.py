import json
import unittest
from io import BytesIO
from urllib import error
from unittest.mock import patch

from cleepwheel.soundcloud import SoundCloudAPIError, SoundCloudClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class SoundCloudClientTest(unittest.TestCase):
    def test_search_tracks_uses_oauth_header_and_linked_partitioning(self):
        captured = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["headers"] = dict(req.header_items())
            captured["timeout"] = timeout
            return FakeResponse(
                {
                    "collection": [{"title": "demo"}],
                    "next_href": "https://api.soundcloud.com/tracks?page=2",
                }
            )

        with patch("cleepwheel.soundcloud.request.urlopen", side_effect=fake_urlopen):
            page = SoundCloudClient("token").search_tracks("ambient song", limit=5)

        self.assertEqual(page.collection, [{"title": "demo"}])
        self.assertEqual(page.next_href, "https://api.soundcloud.com/tracks?page=2")
        self.assertIn("q=ambient+song", captured["url"])
        self.assertIn("linked_partitioning=true", captured["url"])
        self.assertEqual(captured["headers"]["Authorization"], "OAuth token")
        self.assertEqual(captured["timeout"], 15.0)

    def test_related_helpers_encode_urns_and_request_expected_params(self):
        urls = []

        def fake_urlopen(req, timeout):
            urls.append(req.full_url)
            return FakeResponse({"collection": []})

        client = SoundCloudClient("token")
        with patch("cleepwheel.soundcloud.request.urlopen", side_effect=fake_urlopen):
            client.get_related_artists("soundcloud:users:948745750")
            client.get_related_tracks("soundcloud:tracks:308946187")

        self.assertIn("/users/soundcloud%3Ausers%3A948745750/related", urls[0])
        self.assertIn("linked_partitioning=true", urls[0])
        self.assertIn("/tracks/soundcloud%3Atracks%3A308946187/related", urls[1])
        self.assertIn("access=playable", urls[1])

    def test_get_all_pages_follows_next_href_until_absent(self):
        responses = [
            FakeResponse(
                {
                    "collection": [{"id": 1}],
                    "next_href": "https://api.soundcloud.com/tracks?page=2",
                }
            ),
            FakeResponse({"collection": [{"id": 2}]}),
        ]

        with patch("cleepwheel.soundcloud.request.urlopen", side_effect=responses):
            items = SoundCloudClient("token").get_all_pages("/tracks", max_pages=4)

        self.assertEqual(items, [{"id": 1}, {"id": 2}])

    def test_http_errors_are_clear_and_include_status(self):
        body = BytesIO(b'{"message":"rate limited"}')
        exc = error.HTTPError(
            "https://api.soundcloud.com/tracks",
            429,
            "Too Many Requests",
            {"Retry-After": "2"},
            body,
        )

        with patch("cleepwheel.soundcloud.request.urlopen", side_effect=exc):
            with self.assertRaises(SoundCloudAPIError) as caught:
                SoundCloudClient("token", max_retries=0).search_tracks("x")

        self.assertEqual(caught.exception.status, 429)
        self.assertEqual(caught.exception.retry_after, "2")
        self.assertIn("rate limited", str(caught.exception))

    def test_requires_access_token(self):
        with self.assertRaises(ValueError):
            SoundCloudClient(" ")
