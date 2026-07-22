from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import stat
import time
import webbrowser
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from .soundcloud import SoundCloudAPIError


AUTHORIZE_URL = "https://secure.soundcloud.com/authorize"
TOKEN_URL = "https://secure.soundcloud.com/oauth/token"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8765/callback"


@dataclass(frozen=True)
class PKCEPair:
    verifier: str
    challenge: str


@dataclass(frozen=True)
class SoundCloudTokens:
    access_token: str
    refresh_token: str | None
    expires_in: int
    token_type: str = "OAuth"
    scope: str = ""
    obtained_at: int = 0

    @property
    def expires_at(self) -> int:
        return self.obtained_at + self.expires_in

    def expires_within(self, seconds: int) -> bool:
        return int(time.time()) + seconds >= self.expires_at


def default_token_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "cleepwheel" / "soundcloud-token.json"


def generate_pkce_pair() -> PKCEPair:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return PKCEPair(verifier=verifier, challenge=challenge)


def build_authorize_url(
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    state: str,
    *,
    scope: str | None = None,
) -> str:
    _require_value(client_id, "client_id")
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    if scope:
        params["scope"] = scope
    return f"{AUTHORIZE_URL}?{parse.urlencode(params)}"


def exchange_authorization_code(
    *,
    client_id: str,
    redirect_uri: str,
    code: str,
    code_verifier: str,
    client_secret: str | None = None,
    token_url: str = TOKEN_URL,
) -> SoundCloudTokens:
    body = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code": code,
        "code_verifier": code_verifier,
    }
    if client_secret:
        body["client_secret"] = client_secret
    return _token_request(token_url, body)


def refresh_access_token(
    *,
    client_id: str,
    refresh_token: str,
    client_secret: str | None = None,
    token_url: str = TOKEN_URL,
) -> SoundCloudTokens:
    body = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }
    if client_secret:
        body["client_secret"] = client_secret
    return _token_request(token_url, body)


def load_tokens(path: Path | None = None) -> SoundCloudTokens:
    token_path = path or default_token_path()
    payload = json.loads(token_path.read_text(encoding="utf-8"))
    return SoundCloudTokens(
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token"),
        expires_in=int(payload.get("expires_in", 0)),
        token_type=payload.get("token_type", "OAuth"),
        scope=payload.get("scope", ""),
        obtained_at=int(payload.get("obtained_at", 0)),
    )


def save_tokens(tokens: SoundCloudTokens, path: Path | None = None) -> Path:
    token_path = path or default_token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(json.dumps(asdict(tokens), indent=2) + "\n", encoding="utf-8")
    token_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return token_path


def login_with_pkce(
    *,
    client_id: str,
    redirect_uri: str = DEFAULT_REDIRECT_URI,
    client_secret: str | None = None,
    scope: str | None = None,
    token_path: Path | None = None,
    open_browser: bool = True,
    timeout_seconds: int = 180,
) -> Path:
    pkce = generate_pkce_pair()
    state = secrets.token_urlsafe(24)
    code = capture_authorization_code(
        build_authorize_url(client_id, redirect_uri, pkce.challenge, state, scope=scope),
        redirect_uri,
        state,
        open_browser=open_browser,
        timeout_seconds=timeout_seconds,
    )
    tokens = exchange_authorization_code(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        code=code,
        code_verifier=pkce.verifier,
    )
    return save_tokens(tokens, token_path)


def capture_authorization_code(
    authorize_url: str,
    redirect_uri: str,
    expected_state: str,
    *,
    open_browser: bool = True,
    timeout_seconds: int = 180,
) -> str:
    parsed = parse.urlparse(redirect_uri)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost"):
        raise ValueError("redirect_uri must be a local http URL")
    if not parsed.port:
        raise ValueError("redirect_uri must include a port")
    callback_path = parsed.path or "/callback"
    result: dict[str, str] = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            request_path = parse.urlparse(self.path)
            params = parse.parse_qs(request_path.query)
            if request_path.path != callback_path:
                self.send_error(404)
                return
            if params.get("state", [""])[0] != expected_state:
                result["error"] = "OAuth state mismatch"
                self._reply("OAuth state mismatch. Return to CleepWheel.", status=400)
                return
            if "error" in params:
                result["error"] = params.get("error_description", params["error"])[0]
                self._reply("SoundCloud authorization failed. Return to CleepWheel.", status=400)
                return
            code = params.get("code", [""])[0]
            if not code:
                result["error"] = "missing authorization code"
                self._reply("Missing authorization code. Return to CleepWheel.", status=400)
                return
            result["code"] = code
            self._reply("SoundCloud connected. You can close this tab.")

        def _reply(self, message: str, status: int = 200) -> None:
            body = f"<html><body><h1>{message}</h1></body></html>".encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer((parsed.hostname, parsed.port), CallbackHandler)
    server.timeout = 1
    try:
        if open_browser:
            webbrowser.open(authorize_url)
        deadline = time.monotonic() + timeout_seconds
        while "code" not in result and "error" not in result and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if "code" in result:
        return result["code"]
    if "error" in result:
        raise RuntimeError(result["error"])
    raise TimeoutError("timed out waiting for SoundCloud authorization")


def _token_request(token_url: str, body: dict[str, str]) -> SoundCloudTokens:
    data = parse.urlencode(body).encode("utf-8")
    req = request.Request(
        token_url,
        data=data,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise _token_error(exc) from exc
    except error.URLError as exc:
        raise SoundCloudAPIError(0, str(exc.reason)) from exc
    except json.JSONDecodeError as exc:
        raise SoundCloudAPIError(502, "invalid token response") from exc
    return _tokens_from_payload(payload)


def _tokens_from_payload(payload: dict[str, Any]) -> SoundCloudTokens:
    access_token = str(payload.get("access_token", ""))
    if not access_token:
        raise SoundCloudAPIError(502, "token response did not include access_token")
    return SoundCloudTokens(
        access_token=access_token,
        refresh_token=payload.get("refresh_token"),
        expires_in=int(payload.get("expires_in", 3600)),
        token_type=str(payload.get("token_type", "OAuth")),
        scope=str(payload.get("scope", "")),
        obtained_at=int(time.time()),
    )


def _token_error(exc: error.HTTPError) -> SoundCloudAPIError:
    body = exc.read().decode("utf-8", errors="replace")
    exc.close()
    message = body.strip() or exc.reason or "token request failed"
    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError:
        payload = {}
    if isinstance(payload, dict):
        message = str(payload.get("error_description") or payload.get("error") or message)
    return SoundCloudAPIError(exc.code, message, exc.headers.get("Retry-After"))


def _require_value(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} is required")
