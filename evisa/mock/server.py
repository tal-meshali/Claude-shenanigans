"""A deliberately tiny HTTP framework (stdlib only) for the mock portals."""

from __future__ import annotations

import html
import re
import secrets
import threading
from dataclasses import dataclass, field
from email.parser import BytesParser
from email.policy import default as email_policy
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode, urlparse


@dataclass
class Upload:
    filename: str
    content: bytes
    content_type: str


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, str]
    form: dict[str, str]
    files: dict[str, Upload]
    cookies: dict[str, str]
    session: dict[str, Any] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)


@dataclass
class Response:
    body: str = ""
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def redirect(cls, location: str, status: int = 303) -> "Response":
        return cls("", status, {"Location": location})


Handler = Callable[[Request], Response]


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def with_query(url: str, **params: str) -> str:
    return f"{url}{'&' if '?' in url else '?'}{urlencode(params)}"


def _parse_multipart(content_type: str, body: bytes) -> tuple[dict[str, str], dict[str, Upload]]:
    msg = BytesParser(policy=email_policy).parsebytes(f"Content-Type: {content_type}\r\n\r\n".encode() + body)
    form: dict[str, str] = {}
    files: dict[str, Upload] = {}
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename is not None:
            if filename:
                files[name] = Upload(filename, payload, part.get_content_type())
        else:
            form[name] = payload.decode("utf-8", "replace")
    return form, files


class MockApp:
    """Routes + cookie sessions. Subclasses register handlers in __init__."""

    session_cookie = "mock_session"

    def __init__(self) -> None:
        self._routes: list[tuple[str, re.Pattern[str], Handler]] = []
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self.base_url = ""

    def route(self, method: str, pattern: str, handler: Handler) -> None:
        self._routes.append((method, re.compile(f"^{pattern}$"), handler))

    def dispatch(self, method: str, raw_path: str, headers: dict[str, str], body: bytes) -> tuple[Response, str | None]:
        parsed = urlparse(raw_path)
        query = {k: v[0] for k, v in parse_qs(parsed.query, keep_blank_values=True).items()}
        form: dict[str, str] = {}
        files: dict[str, Upload] = {}
        ctype = headers.get("content-type", "")
        if method == "POST":
            if ctype.startswith("multipart/form-data"):
                form, files = _parse_multipart(ctype, body)
            else:
                form = {k: v[0] for k, v in parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True).items()}
        jar = SimpleCookie(headers.get("cookie", ""))
        cookies = {k: m.value for k, m in jar.items()}
        sid = cookies.get(self.session_cookie)
        new_sid = None
        with self._lock:
            if not sid or sid not in self._sessions:
                sid = new_sid = secrets.token_urlsafe(16)
                self._sessions[sid] = {}
            session = self._sessions[sid]
        req = Request(method, parsed.path, query, form, files, cookies, session)
        for m, pattern, handler in self._routes:
            match = pattern.match(parsed.path)
            if m == method and match:
                req.params = match.groupdict()
                return handler(req), new_sid
        return Response("<h1>404 Not Found</h1>", 404), new_sid


def serve(app: MockApp, host: str = "127.0.0.1", port: int = 0, *, public_host: str | None = None) -> ThreadingHTTPServer:
    """Serve `app` in a daemon thread. `public_host` is the hostname put in its URLs
    (e.g. "localhost" for the payment gateway, so it is a different host than the portal)."""
    class _Handler(BaseHTTPRequestHandler):
        def _handle(self) -> None:
            length = int(self.headers.get("content-length") or 0)
            body = self.rfile.read(length) if length else b""
            headers = {k.lower(): v for k, v in self.headers.items()}
            resp, new_sid = app.dispatch(self.command, self.path, headers, body)
            data = resp.body.encode("utf-8")
            self.send_response(resp.status)
            self.send_header("Content-Type", resp.headers.pop("Content-Type", "text/html; charset=utf-8"))
            self.send_header("Content-Length", str(len(data)))
            for key, value in resp.headers.items():
                self.send_header(key, value)
            if new_sid:
                self.send_header("Set-Cookie", f"{app.session_cookie}={new_sid}; Path=/; HttpOnly; SameSite=Lax")
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = _handle

        def log_message(self, *args: Any) -> None:  # keep test output clean
            pass

    server = ThreadingHTTPServer((host, port), _Handler)
    server.daemon_threads = True
    app.base_url = f"http://{public_host or host}:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
