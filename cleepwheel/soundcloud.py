from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


API_BASE_URL = "https://api.soundcloud.com"


class SoundCloudAPIError(RuntimeError):
    def __init__(self, status: int, message: str, retry_after: str | None = None):
        super().__init__(f"SoundCloud API error {status}: {message}")
        self.status = status
        self.message = message
        self.retry_after = retry_after


@dataclass(frozen=True)
class SoundCloudPage:
    collection: list[dict[str, Any]]
    next_href: str | None = None


class SoundCloudClient:
    def __init__(
        self,
        access_token: str,
        *,
        api_base_url: str = API_BASE_URL,
        timeout_seconds: float = 15.0,
        max_retries: int = 3,
        backoff_seconds: float = 0.5,
    ):
        if not access_token.strip():
            raise ValueError("access_token is required")
        self.access_token = access_token
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

    def search_tracks(self, query: str, limit: int = 20) -> SoundCloudPage:
        return self.get_page(
            "/tracks",
            {
                "q": query,
                "limit": str(limit),
                "linked_partitioning": "true",
            },
        )

    def my_tracks(self, limit: int = 50, sort: str | None = None) -> SoundCloudPage:
        params = {
            "limit": str(limit),
            "linked_partitioning": "true",
        }
        if sort:
            params["sort"] = sort
        return self.get_page("/me/tracks", params)

    def get_related_artists(self, user_urn: str, limit: int = 10) -> SoundCloudPage:
        return self.get_page(
            f"/users/{parse.quote(user_urn, safe='')}/related",
            {
                "limit": str(limit),
                "linked_partitioning": "true",
            },
        )

    def get_related_tracks(self, track_urn: str, limit: int = 10) -> SoundCloudPage:
        return self.get_page(
            f"/tracks/{parse.quote(track_urn, safe='')}/related",
            {
                "limit": str(limit),
                "access": "playable",
                "linked_partitioning": "true",
            },
        )

    def resolve_url(self, soundcloud_url: str) -> dict[str, Any]:
        payload = self.get_json("/resolve", {"url": soundcloud_url})
        if not isinstance(payload, dict):
            raise SoundCloudAPIError(502, "resolve endpoint returned a non-object payload")
        return payload

    def update_track_metadata(
        self,
        track_urn: str,
        *,
        title: str | None = None,
        description: str | None = None,
        genre: str | None = None,
        tag_list: str | None = None,
        label_name: str | None = None,
        release: str | None = None,
        release_date: str | None = None,
        isrc: str | None = None,
        license: str | None = None,
        sharing: str | None = None,
        streamable: bool | None = None,
        downloadable: bool | None = None,
        commentable: bool | None = None,
        reveal_stats: bool | None = None,
        reveal_comments: bool | None = None,
    ) -> dict[str, Any]:
        fields = {
            "track[title]": title,
            "track[description]": description,
            "track[genre]": genre,
            "track[tag_list]": tag_list,
            "track[label_name]": label_name,
            "track[release]": release,
            "track[release_date]": release_date,
            "track[isrc]": isrc,
            "track[license]": license,
            "track[sharing]": sharing,
            "track[streamable]": streamable,
            "track[downloadable]": downloadable,
            "track[commentable]": commentable,
            "track[reveal_stats]": reveal_stats,
            "track[reveal_comments]": reveal_comments,
        }
        payload = {key: value for key, value in fields.items() if value is not None}
        if not payload:
            raise ValueError("at least one track metadata field is required")
        result = self.request_json(
            "PUT",
            f"/tracks/{parse.quote(track_urn, safe='')}",
            json_body=payload,
        )
        if not isinstance(result, dict):
            raise SoundCloudAPIError(502, "track update returned a non-object payload")
        return result

    def get_page(self, path_or_url: str, params: dict[str, str] | None = None) -> SoundCloudPage:
        payload = self.get_json(path_or_url, params)
        if isinstance(payload, dict) and "collection" in payload:
            collection = payload.get("collection")
            if not isinstance(collection, list):
                raise SoundCloudAPIError(502, "collection is not a list")
            return SoundCloudPage(
                collection=[item for item in collection if isinstance(item, dict)],
                next_href=payload.get("next_href") if isinstance(payload.get("next_href"), str) else None,
            )
        if isinstance(payload, list):
            return SoundCloudPage(collection=[item for item in payload if isinstance(item, dict)])
        raise SoundCloudAPIError(502, "expected a paginated SoundCloud response")

    def get_all_pages(
        self,
        path_or_url: str,
        params: dict[str, str] | None = None,
        *,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        if max_pages <= 0:
            raise ValueError("max_pages must be greater than zero")
        items: list[dict[str, Any]] = []
        page = self.get_page(path_or_url, params)
        items.extend(page.collection)
        pages_read = 1
        while page.next_href and pages_read < max_pages:
            page = self.get_page(page.next_href)
            items.extend(page.collection)
            pages_read += 1
        return items

    def get_json(self, path_or_url: str, params: dict[str, str] | None = None) -> Any:
        return self.request_json("GET", path_or_url, params)

    def request_json(
        self,
        method: str,
        path_or_url: str,
        params: dict[str, str] | None = None,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        url = self._build_url(path_or_url, params)
        data = json.dumps(json_body).encode("utf-8") if json_body is not None else None
        last_error: SoundCloudAPIError | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with request.urlopen(self._request(url, method, data), timeout=self.timeout_seconds) as response:
                    raw = response.read().decode("utf-8")
                    return json.loads(raw) if raw else {}
            except error.HTTPError as exc:
                api_error = self._http_error(exc)
                if api_error.status != 429 or attempt >= self.max_retries:
                    raise api_error from exc
                last_error = api_error
                time.sleep(self.backoff_seconds * (2**attempt))
            except error.URLError as exc:
                raise SoundCloudAPIError(0, str(exc.reason)) from exc
            except json.JSONDecodeError as exc:
                raise SoundCloudAPIError(502, "invalid JSON response") from exc
        if last_error:
            raise last_error
        raise SoundCloudAPIError(0, "request failed")

    def _request(self, url: str, method: str = "GET", data: bytes | None = None) -> request.Request:
        headers = {
            "Accept": "application/json",
            "Authorization": f"OAuth {self.access_token}",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        return request.Request(
            url,
            data=data,
            headers=headers,
            method=method,
        )

    def _build_url(self, path_or_url: str, params: dict[str, str] | None = None) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            base = path_or_url
        else:
            path = path_or_url if path_or_url.startswith("/") else f"/{path_or_url}"
            base = f"{self.api_base_url}{path}"
        if not params:
            return base
        separator = "&" if parse.urlparse(base).query else "?"
        return f"{base}{separator}{parse.urlencode(params)}"

    @staticmethod
    def _http_error(exc: error.HTTPError) -> SoundCloudAPIError:
        body = exc.read().decode("utf-8", errors="replace")
        message = body.strip() or exc.reason or "request failed"
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            message = str(payload.get("error") or payload.get("message") or message)
        return SoundCloudAPIError(exc.code, message, exc.headers.get("Retry-After"))
