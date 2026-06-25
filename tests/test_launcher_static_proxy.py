"""Production-launcher static + reverse-proxy server.

Proves the repo-owned server (replacing bare ``python -m http.server``) forwards backend API requests
to the FastAPI backend while serving the built SPA. Uses a stdlib fake backend + the real proxy on
ephemeral 127.0.0.1 ports and a temp dist dir — no Vite, no network.
"""

from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from hb_assistant.launcher import static_proxy


def _serve(server: ThreadingHTTPServer) -> None:
    threading.Thread(target=server.serve_forever, daemon=True).start()


def _make_backend(captured: dict[str, object]) -> ThreadingHTTPServer:
    class _Backend(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args: object) -> None:
            return

        def _record_and_reply(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            captured["method"] = self.command
            captured["path"] = self.path
            captured["role"] = self.headers.get("X-HB-UI-Role")
            captured["body"] = body
            if self.path.startswith("/api/forecast/generation/projects"):
                payload = json.dumps(
                    {"surface": "x", "projects": [{"project_key": "tropical"}], "guardrails": {}}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            elif self.path == "/api/echo":
                self.send_response(201)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()

        def do_GET(self) -> None:
            self._record_and_reply()

        def do_POST(self) -> None:
            self._record_and_reply()

    return ThreadingHTTPServer(("127.0.0.1", 0), _Backend)


def _request(
    port: int,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


@pytest.fixture
def proxy_env(tmp_path: Path) -> Iterator[tuple[int, dict[str, object]]]:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>HB</title><div id=root></div>")
    (dist / "assets" / "app.js").write_text("console.log('hb')")
    # A sibling file OUTSIDE dist used to prove the traversal guard.
    (tmp_path / "secret.txt").write_text("TOP SECRET")

    captured: dict[str, object] = {}
    backend = _make_backend(captured)
    backend_port = backend.server_address[1]
    _serve(backend)

    proxy = static_proxy.build_server(port=0, directory=str(dist), backend_port=backend_port)
    proxy_port = proxy.server_address[1]
    _serve(proxy)
    try:
        yield proxy_port, captured
    finally:
        proxy.shutdown()
        proxy.server_close()
        backend.shutdown()
        backend.server_close()


def test_proxy_forwards_api_json_and_preserves_role(
    proxy_env: tuple[int, dict[str, object]],
) -> None:
    port, captured = proxy_env
    status, data = _request(
        port, "GET", "/api/forecast/generation/projects", {"X-HB-UI-Role": "viewer"}
    )
    assert status == 200
    payload = json.loads(data)
    assert payload["projects"][0]["project_key"] == "tropical"
    # The backend saw the forwarded request with the preserved role header and path.
    assert captured["method"] == "GET"
    assert captured["path"] == "/api/forecast/generation/projects"
    assert captured["role"] == "viewer"


def test_proxy_preserves_method_body_and_status(
    proxy_env: tuple[int, dict[str, object]],
) -> None:
    port, captured = proxy_env
    body = json.dumps({"hello": "world"}).encode()
    status, data = _request(
        port,
        "POST",
        "/api/echo",
        {
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
            "X-HB-UI-Role": "operator",
        },
        body,
    )
    assert status == 201  # non-200 status passes through
    assert json.loads(data) == {"hello": "world"}  # body round-trips
    assert captured["method"] == "POST"
    assert captured["role"] == "operator"
    assert captured["body"] == body


def test_static_root_spa_fallback_and_assets(
    proxy_env: tuple[int, dict[str, object]],
) -> None:
    port, _ = proxy_env
    s_root, root = _request(port, "GET", "/")
    assert s_root == 200 and b"id=root" in root
    # Unknown (client-side) route → SPA fallback to index.html, not 404.
    s_spa, spa = _request(port, "GET", "/forecasting/some-id")
    assert s_spa == 200 and b"id=root" in spa
    # A real built asset is served byte-for-byte.
    s_asset, asset = _request(port, "GET", "/assets/app.js")
    assert s_asset == 200 and b"console.log('hb')" in asset


def test_traversal_outside_dist_is_refused(
    proxy_env: tuple[int, dict[str, object]],
) -> None:
    port, _ = proxy_env
    status, data = _request(port, "GET", "/../secret.txt")
    assert b"TOP SECRET" not in data  # the out-of-dist file is never served
    assert status == 404
