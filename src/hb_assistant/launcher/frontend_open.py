"""Frontend readiness wait + browser open helpers (pure stdlib, no new deps).

These back the ``launcher <env> --open`` flow. ``wait_for_frontend`` polls a LOCAL
frontend URL until it answers (any HTTP response counts) or a bounded timeout
elapses — it never requires internet access. ``open_browser`` opens the resolved
URL in the default browser via the cross-platform ``webbrowser`` module; failure is
non-fatal and surfaced as a warning rather than raising.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
import webbrowser


def wait_for_frontend(
    url: str, *, timeout_seconds: int = 30, interval_seconds: float = 1.0
) -> tuple[bool, list[str]]:
    """Poll ``url`` until it is reachable or ``timeout_seconds`` elapses.

    Any HTTP response (including 4xx/5xx) means the server is up and is treated as
    reachable. Connection refusals/timeouts are swallowed and retried every
    ``interval_seconds``. Returns ``(reachable, warnings)``. Local-only: the caller
    passes a 127.0.0.1/localhost URL, so no external network is contacted.
    """
    warnings: list[str] = []
    deadline = time.monotonic() + max(0, timeout_seconds)
    while True:
        if _probe(url):
            return True, warnings
        if time.monotonic() >= deadline:
            warnings.append(
                f"frontend not reachable at {url} within {timeout_seconds}s; "
                "reporting intended URL only"
            )
            return False, warnings
        time.sleep(interval_seconds)


def _probe(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2.0):  # noqa: S310 — local URL only
            return True
    except urllib.error.HTTPError:
        # The server answered (4xx/5xx) — it is up.
        return True
    except (urllib.error.URLError, ConnectionError, OSError, ValueError):
        return False


def open_browser(url: str) -> tuple[bool, str, list[str]]:
    """Open ``url`` in the default browser. Non-blocking; failure is non-fatal.

    Returns ``(opened, method, warnings)``. ``webbrowser.open`` spawns the browser
    without blocking the launcher process.
    """
    warnings: list[str] = []
    try:
        opened = webbrowser.open(url, new=2)
    except Exception as exc:  # pragma: no cover - platform-specific
        warnings.append(f"failed to open browser for {url}: {exc}")
        return False, "browser", warnings
    if not opened:
        warnings.append(f"no browser available to open {url}")
    return opened, "browser", warnings
