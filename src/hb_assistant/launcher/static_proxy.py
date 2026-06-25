"""Local static-file + reverse-proxy server for the production launcher frontend.

Serves the built SPA (``frontend/dist``) on ``127.0.0.1:<port>`` and forwards backend API/status
requests (``/api`` and ``/health`` by default) to the FastAPI backend on
``127.0.0.1:<backend_port>``. This is what makes the production launcher work without Vite: the built
frontend issues *relative* ``/api/...`` calls, and this server proxies them to the backend (same
origin, so no CORS is required), while serving everything else as static assets with an
``index.html`` SPA fallback.

Stdlib only (no third-party dependency); local-only (binds ``127.0.0.1``). Run as a module:

    python -m hb_assistant.launcher.static_proxy --port 5173 --directory <dist> \
        --backend-host 127.0.0.1 --backend-port 8000
"""

from __future__ import annotations

import argparse
import http.client
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

_HOST = "127.0.0.1"
# Backend path prefixes proxied to the API by default. Mirrors the Vite dev proxy (/api) and adds the
# backend health route; extend via --api-prefix if a real frontend need appears.
_DEFAULT_PREFIXES: tuple[str, ...] = ("/api", "/health")
# Hop-by-hop headers must not be forwarded (RFC 7230 §6.1); Host is rewritten for the backend.
_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
    }
)


def _path_only(target: str) -> str:
    return target.split("?", 1)[0]


def _is_proxied(target: str, prefixes: tuple[str, ...]) -> bool:
    path = _path_only(target)
    return any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes)


def _within_or_equal(child: Path, parent: Path) -> bool:
    if child == parent:
        return True
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _make_handler(
    dist: Path, backend_host: str, backend_port: int, prefixes: tuple[str, ...]
) -> type[BaseHTTPRequestHandler]:
    dist_root = dist.resolve()
    index = dist_root / "index.html"

    class _Handler(BaseHTTPRequestHandler):
        server_version = "HBLauncherProxy/1"
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
            return  # quiet: launcher captures child stdout/stderr to a logfile

        # All methods route through one dispatcher: proxy backend prefixes, else serve static.
        def _handle(self) -> None:
            if _is_proxied(self.path, prefixes):
                self._proxy()
            elif self.command in ("GET", "HEAD"):
                self._serve_static()
            else:
                self._send_plain(HTTPStatus.NOT_FOUND, "Not found")

        def do_GET(self) -> None:
            self._handle()

        def do_HEAD(self) -> None:
            self._handle()

        def do_POST(self) -> None:
            self._handle()

        def do_PUT(self) -> None:
            self._handle()

        def do_PATCH(self) -> None:
            self._handle()

        def do_DELETE(self) -> None:
            self._handle()

        def do_OPTIONS(self) -> None:
            self._handle()

        def _proxy(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length > 0 else None
            fwd_headers = {
                key: value
                for key, value in self.headers.items()
                if key.lower() not in _HOP_BY_HOP
            }
            fwd_headers["Host"] = f"{backend_host}:{backend_port}"
            conn = http.client.HTTPConnection(backend_host, backend_port, timeout=120)
            try:
                conn.request(self.command, self.path, body=body, headers=fwd_headers)
                resp = conn.getresponse()
                payload = resp.read()
                status = resp.status
                headers = resp.getheaders()
            except OSError:
                # Backend not reachable — coded, internals-free.
                self._send_plain(HTTPStatus.BAD_GATEWAY, "Backend unavailable")
                return
            finally:
                conn.close()

            self.send_response(status)
            for key, value in headers:
                lowered = key.lower()
                if lowered in _HOP_BY_HOP or lowered == "content-length":
                    continue
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)

        def _serve_static(self) -> None:
            rel = unquote(_path_only(self.path)).lstrip("/")
            target = (dist_root / rel).resolve() if rel else dist_root
            # Traversal guard: a resolved path that escapes dist is refused outright.
            if not _within_or_equal(target, dist_root):
                self._send_plain(HTTPStatus.NOT_FOUND, "Not found")
                return
            # Real file → serve it; otherwise SPA fallback to index.html.
            if not target.is_file():
                target = index
            if not target.is_file():
                self._send_plain(HTTPStatus.NOT_FOUND, "Not found")
                return
            data = target.read_bytes()
            ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def _send_plain(self, status: HTTPStatus, message: str) -> None:
            data = message.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

    return _Handler


def build_server(
    *,
    port: int,
    directory: str | Path,
    backend_host: str = _HOST,
    backend_port: int,
    prefixes: tuple[str, ...] = _DEFAULT_PREFIXES,
) -> ThreadingHTTPServer:
    """Build (but don't start) the local static+proxy server. ``port=0`` binds an ephemeral port."""
    handler = _make_handler(Path(directory), backend_host, backend_port, tuple(prefixes))
    return ThreadingHTTPServer((_HOST, port), handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Local static + reverse-proxy server for the production launcher frontend.",
    )
    parser.add_argument("--port", type=int, required=True, help="frontend port to bind on 127.0.0.1")
    parser.add_argument("--directory", required=True, help="path to the built frontend (dist) dir")
    parser.add_argument("--backend-host", default=_HOST)
    parser.add_argument("--backend-port", type=int, required=True, help="FastAPI backend port")
    parser.add_argument(
        "--api-prefix",
        action="append",
        default=None,
        help="path prefix proxied to the backend (repeatable; default: /api and /health)",
    )
    args = parser.parse_args(argv)
    prefixes = tuple(args.api_prefix) if args.api_prefix else _DEFAULT_PREFIXES
    server = build_server(
        port=args.port,
        directory=args.directory,
        backend_host=args.backend_host,
        backend_port=args.backend_port,
        prefixes=prefixes,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
